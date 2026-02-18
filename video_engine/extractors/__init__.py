"""
Factory function to get the appropriate extractor for a URL.
"""
from extractors.generic_extractor import GenericExtractor
from config import USE_BROWSER_FOR_PROTECTED_SITES


def get_extractor(url):
    """
    Factory pattern: Returns the appropriate extractor based on URL.
    
    Strategy:
    - Protected sites (viralkand, kamababa) → BrowserExtractor (if enabled)
    - Everything else → GenericExtractor (yt-dlp)
    
    Args:
        url: Video page URL
        
    Returns:
        BaseExtractor: Appropriate extractor instance
    """
    # Protected sites that need browser automation (viralkand, kamababa)
    # Using BrowserExtractor for all to ensure maximum reliability (as per user request)
    if USE_BROWSER_FOR_PROTECTED_SITES and ("viralkand.com" in url or "thekamababa.com" in url):
        from extractors.browser_extractor import BrowserExtractor
        return BrowserExtractor()
    
    # Default: Use GenericExtractor (yt-dlp fallback)
    return GenericExtractor()
