"""
Custom extractor for viralkand.com and thekamababa.com.
These sites embed videos via iframe with base64 encoded video URLs.
"""
import requests
import base64
import urllib.parse
from bs4 import BeautifulSoup
from extractors.base_extractor import BaseExtractor
from core.logger import logger
from core.exceptions import ExtractionError


class ViralkandExtractor(BaseExtractor):
    """
    Extractor for viralkand.com and thekamababa.com.
    
    These sites use a common pattern:
    1. Page contains iframe with src="player-x.php?q=BASE64_ENCODED_DATA"
    2. Decode base64 to get HTML snippet
    3. Parse snippet to find <source> tag with MP4 URL
    """
    
    SUPPORTED_DOMAINS = ['viralkand.com', 'thekamababa.com']
    
    def extract(self, url):
        """
        Extract direct video URL from viralkand/kamababa pages.
        
        Args:
            url: Page URL containing the video
            
        Returns:
            tuple: (direct_video_url, title)
        """
        try:
            logger.info(f"🔍 Extracting from {self._get_domain(url)}")
            
            # Fetch page with realistic browser headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = soup.find('title')
            title = title.text.strip() if title else 'Untitled'
            
            # Find iframe with q parameter (relaxed check)
            target_iframe = None
            found_iframes = []
            
            for iframe in soup.find_all('iframe'):
                src = iframe.get('src', '')
                found_iframes.append(src)
                
                # Check for q parameter (core mechanism)
                if 'q=' in src:
                    # If we find the standard player-x.php, use it immediately
                    if 'player-x.php' in src:
                        target_iframe = src
                        break
                    
                    # Otherwise, keep the first 'q=' iframe found as a fallback
                    if target_iframe is None:
                        target_iframe = src
            
            if not target_iframe:
                # Log found iframes to help debugging
                iframe_summary = ', '.join([fstr[:50] for fstr in found_iframes[:3]])
                raise ExtractionError(
                    "No player iframe found", 
                    url=url, 
                    details=f"Scanned {len(found_iframes)} iframes. None had 'q=' param. Found: [{iframe_summary}]"
                )
            
            logger.info(f"📺 Found video player iframe")
            
            # Extract q parameter
            parsed_url = urllib.parse.urlparse(target_iframe)
            qs = urllib.parse.parse_qs(parsed_url.query)
            q_param = qs.get('q', [''])[0]
            
            if not q_param:
                raise ExtractionError("No 'q' parameter in iframe", url=url)
            
            # Decode base64 (add padding if needed)
            missing_padding = len(q_param) % 4
            if missing_padding:
                q_param += '=' * (4 - missing_padding)
            
            decoded_bytes = base64.b64decode(q_param)
            decoded_html = decoded_bytes.decode('utf-8', errors='ignore')
            
            # Parse decoded HTML to find video source
            soup_snippet = BeautifulSoup(decoded_html, 'html.parser')
            sources = soup_snippet.find_all('source')
            
            # Find MP4 source
            video_url = None
            for source in sources:
                src = source.get('src')
                type_ = source.get('type')
                if src and ('.mp4' in src or 'video/mp4' in str(type_)):
                    video_url = src
                    break  # Take first (usually highest quality)
            
            if not video_url:
                raise ExtractionError(
                    "No MP4 source found in decoded content", 
                    url=url,
                    details=f"Decoded {len(sources)} source tags"
                )
            
            logger.info(f"✅ Extracted direct video URL: {video_url[:60]}...")
            return video_url, title
        
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Unexpected error: {str(e)}", url=url)
    
    def _get_domain(self, url):
        """Helper to extract domain from URL."""
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc
