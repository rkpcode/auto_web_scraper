from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """
    Abstract base class for video extractors.
    Each site-specific extractor must implement the extract() method.
    """
    
    @abstractmethod
    def extract(self, url):
        """
        Extract direct video URL and title from a page URL.
        
        Args:
            url: Page URL containing the video
            
        Returns:
            tuple: (direct_video_url, title)
                   - direct_video_url: Direct link to MP4/M3U8
                   - title: Video title (can be None)
        """
        pass
    
    def get_site_name(self):
        """Return the site name this extractor handles."""
        return self.__class__.__name__.replace('Extractor', '')
