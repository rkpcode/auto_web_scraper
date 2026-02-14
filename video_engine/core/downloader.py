import os
import yt_dlp
from tenacity import retry, stop_after_attempt, wait_exponential
from core.logger import logger
from core.utils import get_random_user_agent, generate_uuid_filename
from config import TEMP_STORAGE_DIR, PROXY_URL
from core.exceptions import DownloadError


class VideoDownloader:
    """
    yt-dlp wrapper with proxy support and progress tracking.
    Uses yt_dlp.YoutubeDL class (not subprocess) for better control.
    """
    
    def __init__(self, proxy_url=None):
        self.proxy_url = proxy_url or PROXY_URL
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def download(self, url, original_page_url=None):
        """
        Downloads video using yt-dlp to TEMP_STORAGE_DIR.
        
        Args:
            url: Direct video URL or yt-dlp compatible URL
            original_page_url: Original page URL for referer header
            
        Returns:
            tuple: (filename, full_path)
        """
        file_uuid = generate_uuid_filename(extension="%(ext)s")
        output_template = os.path.join(TEMP_STORAGE_DIR, file_uuid)
        
        # Build headers
        headers = {}
        if original_page_url:
            headers['Referer'] = original_page_url
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'user_agent': get_random_user_agent(),
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 3,
            'http_headers': headers,
        }
        
        # Add proxy if configured
        if self.proxy_url:
            ydl_opts['proxy'] = self.proxy_url
            logger.info(f"🌐 Using proxy: {self.proxy_url}")
        
        # Progress hook
        def progress_hook(d):
            if d['status'] == 'downloading':
                percent = d.get('_percent_str', 'N/A')
                speed = d.get('_speed_str', 'N/A')
                logger.debug(f"⬇️  {percent} at {speed}")
            elif d['status'] == 'finished':
                logger.info(f"✅ Download complete: {d['filename']}")
        
        ydl_opts['progress_hooks'] = [progress_hook]
        
        try:
            logger.info(f"⬇️  Starting download: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
                # Find the actual downloaded file
                for filename in os.listdir(TEMP_STORAGE_DIR):
                    if filename.startswith(file_uuid.split('.')[0]):
                        filepath = os.path.join(TEMP_STORAGE_DIR, filename)
                        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
                        logger.info(f"📦 Downloaded: {filename} ({file_size_mb:.2f}MB)")
                        return filename, filepath
                
                raise DownloadError("File not found after download", url=url)
        
        except yt_dlp.utils.DownloadError as e:
            raise DownloadError(f"yt-dlp download failed: {str(e)}", url=url)
        except Exception as e:
            raise DownloadError(f"Unexpected download error: {str(e)}", url=url)
