import os
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from core.logger import logger
from config import BUNNY_API_KEY, BUNNY_LIBRARY_ID, BUNNY_BASE_URL
from core.exceptions import UploadError, ConfigurationError


class BunnyUploader:
    """
    Bunny Stream API wrapper with retry logic.
    Handles video creation and binary upload.
    """
    
    def __init__(self):
        self.api_key = BUNNY_API_KEY
        self.library_id = BUNNY_LIBRARY_ID
        self.base_url = BUNNY_BASE_URL
        
        if not self.api_key or not self.library_id:
            raise ConfigurationError("BUNNY_API_KEY and BUNNY_LIBRARY_ID must be set in environment")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def create_video(self, title):
        """
        Step 1: Create a video object in Bunny Stream.
        
        Args:
            title: Video title
            
        Returns:
            str: GUID of the new video
        """
        url = f"{self.base_url}/{self.library_id}/videos"
        headers = {
            "AccessKey": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {"title": title}
        
        logger.info(f"📝 Creating Bunny video: {title}")
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            raise UploadError(f"Failed to create video (HTTP {response.status_code})", 
                            details=response.text[:200])
        
        data = response.json()
        guid = data.get("guid")
        logger.info(f"✅ Video created with GUID: {guid}")
        return guid
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=20))
    def upload_binary(self, guid, file_path):
        """
        Step 2: Upload the binary file to Bunny Stream.
        
        Args:
            guid: Video GUID from create_video()
            file_path: Path to video file
            
        Returns:
            bool: True if successful
        """
        url = f"{self.base_url}/{self.library_id}/videos/{guid}"
        headers = {
            "AccessKey": self.api_key,
            "Content-Type": "application/octet-stream"
        }
        
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        logger.info(f"⬆️  Uploading {file_size_mb:.2f}MB to Bunny (GUID: {guid})")
        
        with open(file_path, 'rb') as f:
            response = requests.put(url, data=f, headers=headers)
        
        if response.status_code != 200:
            raise UploadError(f"Failed to upload binary (HTTP {response.status_code})", 
                            details=response.text[:200])
        
        logger.info(f"✅ Upload complete: {guid}")
        return True
    
    def get_video_info(self, guid):
        """
        Get video information (useful for checking transcode status).
        
        Args:
            guid: Video GUID
            
        Returns:
            dict: Video information
        """
        url = f"{self.base_url}/{self.library_id}/videos/{guid}"
        headers = {
            "AccessKey": self.api_key,
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return None



