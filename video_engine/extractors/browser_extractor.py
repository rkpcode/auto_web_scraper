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
        title = None
        
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
                                # 2. Explicit Domain Blacklist (User Requested)
                                # dscgirls.live = Live cam ads
                                # aucdn.net = Secondary ad stream
                                # tsyndicate = Ad network
                                # storagexhd = Ad storage
                                if any(bad_domain in url_lower for bad_domain in ['dscgirls.live', 'aucdn.net', 'tsyndicate', 'storagexhd', 'b.b.js']):
                                    # logger.debug(f"[FILTER] Ignored blacklisted domain: {response.url[:50]}...")
                                    return

                                # 3. Stronger Ad Filter: Skip common ad video sizes/names immediately
                                if any(x in url_lower for x in ['300x250', 'banner', 'preview', 'intro', 'outros']):
                                    # logger.debug(f"[FILTER] Ignored ad: {response.url[:50]}...")
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
                
                # 1. Check if video is already intercepted (Fast Success)
                page.wait_for_timeout(2000)
                if intercepted_urls:
                    logger.info(f"[BROWSER] Early video detection: {len(intercepted_urls)} found")

                # 2. Smart Interaction Loop (Early Exit + Overlay Killer)
                # Wait up to 15 seconds, but exit IMMEDIATELY if video is found
                import time
                
                # Extended Aggressive Selectors
                play_selectors = [
                    "button[aria-label='Play']", 
                    ".vjs-big-play-button", 
                    ".jw-display-icon-display", 
                    ".jw-display-icon-container",
                    ".fp-ui",
                    ".play-button",
                    "#play-button",
                    "div[class*='play']",   # Aggressive class matching
                    "a.thumb-link",
                    "video",
                    "iframe"
                ]

                start_time = time.time()
                video_url = None
                
                while time.time() - start_time < 15:
                    # A. Early Exit: Did we get the video?
                    if intercepted_urls:
                        video_url = intercepted_urls[0]
                        logger.info(f"🚀 [BROWSER] Video found! Exiting early ({len(intercepted_urls)} intercepted)")
                        
                        # Capture title BEFORE closing
                        try:
                            page_title = page.title()
                        except:
                            page_title = "Untitled Video"
                            
                        # CRITICAL: Close browser immediately to free RAM
                        browser.close()
                        return video_url, page_title
                    
                    # B. Try Clicking with JavaScript (Bypass Overlays)
                    for selector in play_selectors:
                        try:
                            # 1. Check existence first to avoid console noise
                            # 2. Dispatch 'click' event directly to element (ignores overlays)
                            # 3. Also try .play() if it's a media element
                            page.evaluate(f"""() => {{
                                const el = document.querySelector("{selector}");
                                if (el) {{
                                    el.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}));
                                    if (el.tagName === 'VIDEO') el.play();
                                }}
                            }}""", timeout=1000) # Short timeout for JS execution
                        except Exception:
                            continue
                    
                    # C. Wait a bit before retry
                    page.wait_for_timeout(1000)
                
                if not intercepted_urls:
                    logger.warning(f"[BROWSER] No video URLs intercepted after 15s interaction")
                
                # Extract title
                try:
                    title = page.title()
                except:
                    title = "Untitled"
                
                # --- FAST FAIL CHECK ---
                # Check if this is a Category/Archive page to avoid waiting 15s
                try:
                    # 1. Check body classes for archive markers
                    body_class = page.get_attribute("body", "class") or ""
                    if any(c in body_class.lower() for c in ['archive', 'category', 'tag', 'search-results']):
                        raise ExtractionError(f"Skipping non-video page (Body class: {body_class})", url=url)
                    
                    # 2. Check title for "Category" or "Tag"
                    if any(k in title.lower() for k in ['category', 'tag', 'archive', 'search']):
                        # Double check we don't have a player
                        if page.locator('video, iframe').count() == 0:
                            raise ExtractionError(f"Skipping non-video page (Title: {title})", url=url)
                except ExtractionError:
                    raise
                except Exception:
                    pass  # Continue if check fails
                
                # --- AGGRESSIVE VIDEO START LOGIC ---
                logger.info(f"[BROWSER] Attempting to trigger video playback...")
                
                # 1. Wait for common player containers
                try:
                    page.wait_for_selector('video, iframe, .player, #player', timeout=8000)
                except:
                    logger.warning("[BROWSER] No obvious player element found")

                # 2. Try clicking play buttons (generic + specific)
                play_selectors = [
                    'button[aria-label="Play"]', 
                    '.vjs-big-play-button', 
                    '.jw-display-icon-container',
                    '.mejs-overlay-play',
                    'button:has-text("Play")',
                    '.play-button',
                    '#play-button',
                    'video'
                ]
                
                for selector in play_selectors:
                    try:
                        elements = page.locator(selector).all()
                        for el in elements:
                            if el.is_visible():
                                logger.info(f"[BROWSER] Clicking play selector: {selector}")
                                el.click(timeout=1000)
                                page.wait_for_timeout(500)
                    except:
                        pass
                
                # 3. Iframe handling: Try to click inside iframes
                for frame in page.frames:
                    try:
                        if frame != page.main_frame:
                            play_btn = frame.locator('.vjs-big-play-button, button[aria-label="Play"]').first
                            if play_btn.is_visible():
                                logger.info("[BROWSER] Clicking play button in iframe")
                                play_btn.click(timeout=1000)
                    except:
                        pass

                # 4. Wait for network requests to populate
                # Reduced wait time to avoid "stuck" feeling, rely on interception
                logger.info(f"[BROWSER] Waiting 8s for media requests...")
                page.wait_for_timeout(8000)
                
                browser.close()
                
                # Select best video URL
                if intercepted_urls:
                    # Filter out obvious ad videos
                    valid_urls = []
                    for u in intercepted_urls:
                        u_lower = u.lower()
                        # Skip small ad videos or banners
                        if any(x in u_lower for x in ['300x250', 'banner', 'preview', 'intro', 'outros', 'b.b.js']):
                            logger.info(f"[FILTER] Ignoring ad/banner video: {u[:50]}...")
                            continue
                        valid_urls.append(u)

                    if not valid_urls:
                        raise ExtractionError("Only ad/banner videos found", url=url)

                    # Priority 1: .mp4 files that match the site domain (Highest confidence)
                    # This ensures we get the "main" video from the site's CDN, not a 3rd party ad
                    site_domain = url.split('/')[2].replace('www.', '').split('.')[0] # e.g. "thekamababa"
                    domain_mp4s = [u for u in valid_urls if '.mp4' in u.lower() and site_domain in u.lower()]
                    
                    # Priority 2: Any .mp4 file
                    mp4_urls = [u for u in valid_urls if '.mp4' in u.lower()]
                    
                    # Priority 3: .m3u8 files
                    m3u8_urls = [u for u in valid_urls if '.m3u8' in u.lower()]
                    
                    # Selection Logic
                    if domain_mp4s:
                        video_url = domain_mp4s[0]
                        logger.info(f"[SELECT] Prioritizing domain-matched video: {video_url[:100]}...")
                    elif mp4_urls:
                        video_url = mp4_urls[0]
                    elif m3u8_urls:
                        video_url = m3u8_urls[0]
                    else:
                        video_url = valid_urls[0]
                    
                    logger.info(f"[SUCCESS] Extracted: {video_url[:100]}...")
                    return video_url, title
                else:
                    raise ExtractionError(
                        "No video URLs intercepted",
                        url=url,
                        details="Network monitoring found no .mp4/.m3u8 requests after aggressive playback attempt"
                    )
        
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Browser extraction failed: {str(e)}", url=url)
