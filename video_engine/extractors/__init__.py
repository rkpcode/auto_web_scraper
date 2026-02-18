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
    # Protected sites that need browser automation
    # Protected sites (viralkand, kamababa)
    if "viralkand.com" in url or "thekamababa.com" in url:
        # User requested to prioritise ViralkandExtractor (lighter/faster than browser)
        from extractors.viralkand_extractor import ViralkandExtractor
        return ViralkandExtractor()

        # Fallback to BrowserExtractor if needed (commented out for now)
        # if USE_BROWSER_FOR_PROTECTED_SITES:
        #     from extractors.browser_extractor import BrowserExtractor
        #     return BrowserExtractor()
    
    # Default: Use GenericExtractor (yt-dlp fallback)
    return GenericExtractor()
