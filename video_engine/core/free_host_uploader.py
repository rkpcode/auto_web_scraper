import os
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from core.logger import logger
from core.exceptions import UploadError, ConfigurationError
from core.uploader import BaseUploader

class FreeHostBaseUploader(BaseUploader):
    """
    Base uploader for free host services like DoodStream, SeekStreaming, and LuluStream.
    These platforms use a common 2-step uploading pattern:
    1. GET {api_base}/api/upload/server?key={api_key} -> returns upload server URL
    2. POST {upload_server_url} with multipart form-data (file, key/api_key) -> returns filecode
    """

    def __init__(self, provider_name, api_key, base_url, key_param_name="key"):
        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.key_param_name = key_param_name

        if not self.api_key:
            raise ConfigurationError(f"{self.provider_name.upper()}_API_KEY must be set in environment")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get_upload_server(self):
        """
        Step 1: Get the upload server URL.
        """
        url = f"{self.base_url}/api/upload/server"
        params = {"key": self.api_key}
        logger.info(f"🛰️  [Step 1] Requesting upload server from {self.provider_name}...")
        
        try:
            response = requests.get(url, params=params, timeout=30)
        except Exception as e:
            raise UploadError(f"Failed to connect to {self.provider_name} API", details=str(e))

        if response.status_code != 200:
            raise UploadError(
                f"Failed to get upload server from {self.provider_name} (HTTP {response.status_code})",
                details=response.text[:200]
            )

        try:
            data = response.json()
        except ValueError:
            raise UploadError(f"Failed to parse JSON response from {self.provider_name}", details=response.text[:200])

        if data.get("status") != 200 or data.get("msg") != "OK":
            raise UploadError(
                f"{self.provider_name} API returned error: {data.get('msg')}",
                details=str(data)
            )

        # Support both 'result' and 'server_url' keys
        server_url = data.get("result") or data.get("server_url")
        if not server_url:
            raise UploadError(f"No upload server URL found in response from {self.provider_name}", details=str(data))

        logger.info(f"✅ Received upload server URL for {self.provider_name}: {server_url}")
        return server_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=20))
    def _upload_to_server(self, server_url, filepath):
        """
        Step 2: Upload binary to the server.
        """
        logger.info(f"⬆️  [Step 2] Uploading binary to {self.provider_name}...")
        
        if not os.path.exists(filepath):
            raise UploadError(f"File not found: {filepath}")

        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logger.info(f"📂 File size: {file_size_mb:.2f}MB")

        # Prepare multipart fields
        # Note: DoodStream requires 'api_key', SeekStreaming/LuluStream require 'key'
        fields = {self.key_param_name: self.api_key}

        try:
            with open(filepath, 'rb') as f:
                files = {'file': (os.path.basename(filepath), f, 'video/mp4')}
                response = requests.post(server_url, files=files, data=fields, timeout=600)  # long timeout for uploads
        except Exception as e:
            raise UploadError(f"Upload request to {self.provider_name} server failed", details=str(e))

        if response.status_code != 200:
            raise UploadError(
                f"Failed to upload file to {self.provider_name} (HTTP {response.status_code})",
                details=response.text[:200]
            )

        try:
            data = response.json()
        except ValueError:
            raise UploadError(f"Failed to parse JSON upload response from {self.provider_name}", details=response.text[:200])

        # Parse filecode from response
        # Typically response is like {"status":200,"msg":"OK","result":[{"filecode":"...","fn":"...","status":"OK"}]}
        if not data or ("result" not in data and "filecode" not in data):
            raise UploadError(f"Invalid upload response from {self.provider_name}", details=str(data))

        result = data.get("result")
        filecode = None

        if isinstance(result, list) and len(result) > 0:
            filecode = result[0].get("filecode")
        elif isinstance(result, dict):
            filecode = result.get("filecode")
        else:
            filecode = result

        if not filecode:
            filecode = data.get("filecode")

        if not filecode:
            raise UploadError(f"Could not extract filecode from {self.provider_name} response", details=str(data))

        logger.info(f"🎉 Upload to {self.provider_name} successful! Filecode: {filecode}")
        return filecode

    def upload(self, title, filepath):
        """
        Main upload entry point.
        """
        server_url = self._get_upload_server()
        filecode = self._upload_to_server(server_url, filepath)
        return filecode


class DoodStreamUploader(FreeHostBaseUploader):
    def __init__(self):
        from config import DOODSTREAM_API_KEY, DOODSTREAM_BASE_URL
        super().__init__(
            provider_name="doodstream",
            api_key=DOODSTREAM_API_KEY,
            base_url=DOODSTREAM_BASE_URL,
            key_param_name="api_key"  # DoodStream POST param is api_key
        )


class SeekStreamingUploader(FreeHostBaseUploader):
    def __init__(self):
        from config import SEEKSTREAMING_API_KEY, SEEKSTREAMING_BASE_URL
        super().__init__(
            provider_name="seekstreaming",
            api_key=SEEKSTREAMING_API_KEY,
            base_url=SEEKSTREAMING_BASE_URL,
            key_param_name="key"      # SeekStreaming POST param is key
        )


class LuluStreamUploader(FreeHostBaseUploader):
    def __init__(self):
        from config import LULUSTREAM_API_KEY, LULUSTREAM_BASE_URL
        super().__init__(
            provider_name="lulustream",
            api_key=LULUSTREAM_API_KEY,
            base_url=LULUSTREAM_BASE_URL,
            key_param_name="key"      # LuluStream POST param is key
        )
