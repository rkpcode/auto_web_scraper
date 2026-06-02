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
        # LuluStream returns {"status":200,"msg":"OK","files":[{"filecode":"...","filename":"...","status":"OK"}]}
        if not data or ("result" not in data and "filecode" not in data and "files" not in data):
            raise UploadError(f"Invalid upload response from {self.provider_name}", details=str(data))

        result = data.get("result") or data.get("files")
        filecode = None

        if isinstance(result, list) and len(result) > 0:
            # Check if any file has an error status like "video is too short"
            file_status = result[0].get("status", "OK")
            if file_status != "OK":
                raise UploadError(
                    f"Upload rejected by {self.provider_name} server", 
                    details=str(result[0])
                )
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
        if not SEEKSTREAMING_API_KEY:
            raise ConfigurationError("SEEKSTREAMING_API_KEY or STREAMWISH_API_KEY must be set in environment")
        super().__init__(
            provider_name="seekstreaming",
            api_key=SEEKSTREAMING_API_KEY,
            base_url=SEEKSTREAMING_BASE_URL,
            key_param_name="key"      # SeekStreaming POST param is key
        )

    def upload(self, title, filepath):
        """
        Custom V2 TUS upload implementation for SeekStreaming.
        """
        url = f"{self.base_url}/api/v1/video/upload"
        headers = {"api-token": self.api_key}
        logger.info(f"🛰️  [SeekStreaming V2] Requesting TUS endpoints...")
        
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            raise UploadError(
                f"Failed to get TUS upload server from SeekStreaming (HTTP {response.status_code})",
                details=response.text[:200]
            )
            
        try:
            data = response.json()
        except ValueError:
            raise UploadError("Failed to parse JSON response from SeekStreaming", details=response.text[:200])
            
        tus_url = data.get("tusUrl")
        access_token = data.get("accessToken")
        
        if not tus_url or not access_token:
            raise UploadError("Invalid upload credentials received from SeekStreaming", details=str(data))
            
        logger.info(f"✅ TUS URL received: {tus_url}")
        
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        
        import base64
        b64_token = base64.b64encode(access_token.encode()).decode()
        b64_filename = base64.b64encode(filename.encode()).decode()
        b64_filetype = base64.b64encode(b"video/mp4").decode()
        
        metadata_str = f"accessToken {b64_token},filename {b64_filename},filetype {b64_filetype}"
        
        tus_headers = {
            "Tus-Resumable": "1.0.0",
            "Upload-Length": str(file_size),
            "Upload-Metadata": metadata_str,
            "metadata": f"accessToken={access_token},filename={filename},filetype=video/mp4"
        }
        
        logger.info(f"🛰️  [SeekStreaming V2] Initializing TUS session...")
        init_response = requests.post(tus_url, headers=tus_headers, timeout=60)
        
        if init_response.status_code not in (201, 200):
            raise UploadError(
                f"Failed to initialize TUS session (HTTP {init_response.status_code})",
                details=init_response.text[:200]
            )
            
        from urllib.parse import urljoin
        upload_url = init_response.headers.get("Location")
        if not upload_url:
            raise UploadError("TUS server did not return Location header for upload", details=str(init_response.headers))
        upload_url = urljoin(tus_url, upload_url)
            
        logger.info(f"✅ TUS upload session initialized successfully. URL: {upload_url}")
        
        logger.info(f"⬆️  [SeekStreaming V2] Uploading binary of size {file_size / (1024*1024):.2f}MB...")
        
        patch_headers = {
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
            "Upload-Metadata": metadata_str
        }
        
        try:
            with open(filepath, 'rb') as f:
                patch_response = requests.patch(upload_url, headers=patch_headers, data=f, timeout=1200)
        except Exception as e:
            raise UploadError("TUS patch request failed", details=str(e))
            
        if patch_response.status_code not in (204, 200):
            raise UploadError(
                f"TUS upload PATCH failed (HTTP {patch_response.status_code})",
                details=patch_response.text[:200]
            )
            
        logger.info("✅ TUS upload PATCH complete.")
        
        filecode = upload_url.rstrip("/").split("/")[-1]
        
        try:
            res_data = patch_response.json()
            if res_data and "filecode" in res_data:
                filecode = res_data.get("filecode")
            elif res_data and "id" in res_data:
                filecode = res_data.get("id")
        except Exception:
            pass
            
        if not filecode:
            raise UploadError("Failed to extract filecode from TUS upload session", details=upload_url)
            
        logger.info(f"🎉 SeekStreaming upload successful! Filecode: {filecode}")
        return filecode


class LuluStreamUploader(FreeHostBaseUploader):
    def __init__(self):
        from config import LULUSTREAM_API_KEY, LULUSTREAM_BASE_URL
        super().__init__(
            provider_name="lulustream",
            api_key=LULUSTREAM_API_KEY,
            base_url=LULUSTREAM_BASE_URL,
            key_param_name="key"      # LuluStream POST param is key
        )
