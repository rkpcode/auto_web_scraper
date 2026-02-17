"""
Browser-based extractor using Playwright with stealth mode.
Bypasses CloudFlare/WAF protection via network request interception.

This is the "pro-level" solution for heavily protected sites like:
- viralkand.com
- thekamababa.com
"""
import re
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from extractors.base_extractor import BaseExtractor
from core.logger import logger
from core.exceptions import ExtractionError


class BrowserExtractor(BaseExtractor):
    """
    Extractor that uses headless browser to bypass bot protection.
    
    Features:
    - Playwright Stealth (hides automation fingerprints)
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
    
    def extract(self, url):
        """
        Extract video URL using browser automation + network interception.
        
        Args:
            url: Page URL containing the video
            
        Returns:
            tuple: (direct_video_url, title)
        """
        video_url = None
        title = None
        
        try:
            logger.info(f"[BROWSER] Launching headless browser for {url}")
            
            with sync_playwright() as p:
                # Launch browser with stealth
                browser = p.chromium.launch(headless=self.headless)
                
                # Create context with realistic fingerprint
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US',
                    timezone_id='America/New_York'
                )
                
                page = context.new_page()
                
                # Apply stealth patches to hide automation
                # Apply stealth patches to hide automation
                stealth_sync(page)
                
                # Network request interception
                intercepted_urls = []
                
                def handle_response(response):
                    """Capture video file requests"""
                    url_lower = response.url.lower()
                    
                    # Check for video patterns
                    if any(pattern in url_lower for pattern in ['.mp4', '.m3u8', '/stream', '/video', '.ts']):
                        # Filter out ads and tracking
                        if not any(bad in url_lower for bad in ['analytics', 'pixel', 'track', 'ad.', 'ads.']):
                            intercepted_urls.append(response.url)
                            logger.info(f"[INTERCEPT] Found: {response.url[:80]}...")
                
                page.on("response", handle_response)
                
                # Block ads and popups
                page.route("**/*", lambda route: (
                    route.abort() if any(ad in route.request.url for ad in 
                        ['doubleclick', 'googlesyndication', 'adserver', 'popads'])
                    else route.continue_()
                ))
                
                # Navigate to page
                logger.info(f"[BROWSER] Navigating to page...")
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                
                # Extract title
                try:
                    title = page.title()
                except:
                    title = "Untitled"
                
                # Wait for video player to load and trigger requests
                logger.info(f"[BROWSER] Waiting for video player...")
                page.wait_for_timeout(5000)  # Give JS time to load video
                
                # Try to click play button if exists (triggers video load)
                try:
                    play_button = page.locator('button:has-text("Play"), .play-button, #play-button').first
                    if play_button.is_visible(timeout=2000):
                        play_button.click()
                        page.wait_for_timeout(3000)
                except:
                    pass  # No play button or already playing
                
                browser.close()
                
                # Select best video URL
                if intercepted_urls:
                    # Prefer .mp4 over .m3u8
                    mp4_urls = [u for u in intercepted_urls if '.mp4' in u.lower()]
                    video_url = mp4_urls[0] if mp4_urls else intercepted_urls[0]
                    
                    logger.info(f"[SUCCESS] Extracted: {video_url[:80]}...")
                    return video_url, title
                else:
                    raise ExtractionError(
                        "No video URLs intercepted",
                        url=url,
                        details="Network monitoring found no .mp4/.m3u8 requests"
                    )
        
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Browser extraction failed: {str(e)}", url=url)
