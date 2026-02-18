"""
Browser-based extractor using Playwright with stealth mode.
Bypasses CloudFlare/WAF protection via network request interception.

This is the "pro-level" solution for heavily protected sites like:
- viralkand.com
- thekamababa.com
"""
import re
from playwright.sync_api import sync_playwright
# removed broken playwright-stealth dependency
from extractors.base_extractor import BaseExtractor
from core.logger import logger
from core.exceptions import ExtractionError


class BrowserExtractor(BaseExtractor):
    """
    Extractor that uses headless browser to bypass bot protection.
    
    Features:
    - Manual Stealth Implementation (hides automation fingerprints)
    - Network Request Interception (captures video URLs)
    - Popup/Ad Blocking
    """
    
    SUPPORTED_DOMAINS = ['viralkand.com', 'thekamababa.com']
    
    def __init__(self, headless=True, timeout=30000):
        """
        Args:
            headless: Run browser in headless mode (required for Colab)
            timeout: Page load timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
    
    def _apply_stealth(self, page):
        """
        Apply stealth scripts to hide automation.
        Replaces playwright-stealth to avoid import errors.
        """
        # 1. Override navigator.webdriver
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        # 2. Mock chrome object
        page.add_init_script("""
            window.chrome = {
                app: { isInstalled: false },
                runtime: { 
                    OnInstalledReason: { INSTALL: 'install' },
                    PlatformOs: { WIN: 'win' }
                }
            };
        """)
        
        # 3. Pass plugins check
        page.add_init_script("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3]
            });
        """)
        
        # 4. Pass languages check
        page.add_init_script("""
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        # 5. Permission overrides
        page.add_init_script("""
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: 'denied' }) :
                originalQuery(parameters)
            );
        """)

    def extract(self, url):
        """
        Extract video URL using browser automation + network interception.
        
        Args:
            url: Page URL containing the video
            
        Returns:
            tuple: (direct_video_url, title)
        """
        # FAST FAIL: Check URL patterns before launching browser
        # This saves significant resources by avoiding browser launch for junk URLs
        skip_patterns = ['/tags/', '/tag/', '/category/', '/search/', '/page/', '/login', '/register', '/user/']
        if any(pattern in url.lower() for pattern in skip_patterns):
             raise ExtractionError(
                "Skipping non-video page (Fast Fail)", 
                url=url, 
                details=f"URL contains non-video pattern. Skipped."
            )

        video_url = None
        title = "Untitled Video"
        browser = None
        
        try:
            logger.info(f"[BROWSER] Launching headless browser for {url}")
            
            with sync_playwright() as p:
                # Launch browser with autoplay enabled
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--autoplay-policy=no-user-gesture-required',
                        '--mute-audio',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process'
                    ]
                )
                
                # Create context with realistic fingerprint
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US',
                    timezone_id='America/New_York',
                    device_scale_factor=1,
                )
                
                page = context.new_page()
                
                # Apply manual stealth
                self._apply_stealth(page)
                
                # Network request interception
                intercepted_urls = []
                
                def handle_response(response):
                    """Capture video file requests"""
                    try:
                        url_lower = response.url.lower()
                        # Check for video patterns
                        if any(pattern in url_lower for pattern in ['.mp4', '.m3u8', '.ts', 'master.json', 'manifest']):
                            # 1. Generic Exclusion
                            if not any(bad in url_lower for bad in ['analytics', 'pixel', 'track', 'ad.', 'ads.', 'favicon']):
                                # 2. Explicit Domain Blacklist
                                if any(bad_domain in url_lower for bad_domain in ['dscgirls.live', 'aucdn.net', 'tsyndicate', 'storagexhd', 'b.b.js']):
                                    return

                                # 3. Stronger Ad Filter
                                if any(x in url_lower for x in ['300x250', 'banner', 'preview', 'intro', 'outros']):
                                    return

                                # Deduplicate
                                if response.url not in intercepted_urls:
                                    intercepted_urls.append(response.url)
                                    logger.info(f"[INTERCEPT] Found: {response.url[:100]}...")
                    except Exception:
                        pass
                
                page.on("response", handle_response)
                
                # Navigate to page
                logger.info(f"[BROWSER] Navigating to page...")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                except Exception as e:
                    logger.warning(f"[BROWSER] Navigation warning: {str(e)}")
                
                # Capture Title Immediately (Safe Fallback)
                try:
                    title = page.title()
                except Exception:
                    title = "Untitled Video"

                # Smart Interaction Loop (Early Exit + Overlay Killer)
                import time
                
                play_selectors = [
                    "button[aria-label='Play']", 
                    ".vjs-big-play-button", 
                    ".jw-display-icon-display", 
                    ".jw-display-icon-container",
                    ".fp-ui",
                    ".play-button",
                    "#play-button",
                    "div[class*='play']",
                    "a.thumb-link",
                    "video",
                    "iframe"
                ]

                start_time = time.time()
                
                while time.time() - start_time < 15:
                    # A. Early Exit: Did we get the video?
                    if intercepted_urls:
                        # Select the best URL (simple approach for early exit)
                        # We prioritize the first valid one found
                        video_url = intercepted_urls[0]
                        logger.info(f"🚀 [BROWSER] Video found! Exiting monitoring loop ({len(intercepted_urls)} intercepted)")
                        break
                    
                    # B. Try Clicking with JavaScript
                    for selector in play_selectors:
                        try:
                            page.evaluate(f"""() => {{
                                const el = document.querySelector("{selector}");
                                if (el) {{
                                    el.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}));
                                    if (el.tagName === 'VIDEO') el.play();
                                }}
                            }}""", timeout=1000)
                        except Exception:
                            continue
                    
                    page.wait_for_timeout(1000)
                
                # Validation after loop
                if not video_url:
                     # One last check in case it came in at the last second
                     if intercepted_urls:
                         video_url = intercepted_urls[0]
                     else:
                         raise ExtractionError("No video URLs intercepted after 15s interaction", url=url)

                logger.info(f"[SUCCESS] Extracted: {video_url[:100]}...")
                return video_url, title

        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Browser extraction failed: {str(e)}", url=url)
        finally:
            # Guaranteed Cleanup
            if browser:
                try:
                    browser.close()
                    logger.info("🧹 Browser cleaned up successfully.")
                except Exception as e:
                     logger.warning(f"Error closing browser: {e}")
