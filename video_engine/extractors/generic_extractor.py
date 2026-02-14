import yt_dlp
from extractors.base_extractor import BaseExtractor
from core.logger import logger


class GenericExtractor(BaseExtractor):
    """
    Generic fallback extractor using yt-dlp.
    Works for most sites that yt-dlp supports (YouTube, many others).
    """
    
    def extract(self, url):
        """
        Use yt-dlp to extract video info.
        
        Args:
            url: Video page URL
            
        Returns:
            tuple: (video_url, title)
                   For yt-dlp supported sites, this returns the original URL
                   since yt-dlp will handle download directly.
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Untitled')
                
                # For yt-dlp supported sites, just return the original URL
                # The downloader will handle it
                logger.info(f"📹 Extracted: {title}")
                return url, title
        
        except Exception as e:
            logger.warning(f"Generic extraction failed: {e}")
            # Fallback: return URL as-is and hope downloader can handle it
            return url, None
