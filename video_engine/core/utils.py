import os
import uuid
import random
import shutil
import subprocess
import json
from core.logger import logger


MIN_VIDEO_DURATION_SECONDS = 1.0


def get_random_user_agent():
    """Rotate user agents to avoid bot detection."""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
    ]
    return random.choice(user_agents)


def generate_uuid_filename(extension="mp4"):
    """Generate UUID-based filename."""
    return f"{uuid.uuid4()}.{extension}"


def cleanup_file(filepath):
    """
    Guaranteed file deletion with existence check.
    Critical: prevents FileNotFoundError in finally blocks.
    """
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
            logger.info(f"🗑️  Cleaned up: {os.path.basename(filepath)}")
        except Exception as e:
            logger.warning(f"Failed to delete {filepath}: {e}")


def get_video_duration(filepath):
    """
    Get video duration in seconds using ffprobe.
    Returns 0.0 if ffprobe fails or video is corrupted.
    """
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'json', filepath
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data.get('format', {}).get('duration', 0))
            return duration
        else:
            logger.warning(f"ffprobe failed for {filepath}: {result.stderr}")
            return 0.0
    except Exception as e:
        logger.warning(f"Could not get video duration for {filepath}: {e}")
        return 0.0


def get_disk_free_space_gb(path=None):
    """
    Get free disk space in GB.
    Uses TEMP_STORAGE_DIR if available, otherwise falls back to cross-platform root.
    """
    if path is None:
        try:
            from config import TEMP_STORAGE_DIR
            path = TEMP_STORAGE_DIR
        except Exception:
            # Cross-platform fallback: use current drive root on Windows, "/" on Linux
            path = os.path.splitdrive(os.path.abspath(__file__))[0] + os.sep if os.name == 'nt' else "/"
    stat = shutil.disk_usage(path)
    return stat.free / (1024 ** 3)


def check_disk_space(min_gb=5):
    """
    Check if sufficient disk space is available.
    Returns True if enough space, False otherwise.
    """
    free_gb = get_disk_free_space_gb()
    if free_gb < min_gb:
        logger.warning(f"⚠️  Low disk space: {free_gb:.2f}GB remaining (minimum: {min_gb}GB)")
        return False
    return True


def validate_video_file(filepath, min_duration_seconds=1.0):
    """
    Validate video file has valid duration and is not corrupted.
    Uses ffprobe (part of ffmpeg) to check duration.
    
    Args:
        filepath: Path to video file
        min_duration_seconds: Minimum acceptable duration (default 1 second)
    
    Returns:
        float: Video duration in seconds
    
    Raises:
        UploadError: If video is too short, corrupted, or ffprobe fails
    """
    import subprocess
    from core.exceptions import UploadError
    
    if not os.path.exists(filepath):
        raise UploadError(f"Video file not found: {filepath}")
    
    file_size = os.path.getsize(filepath)
    if file_size == 0:
        raise UploadError(f"Video file is empty (0 bytes): {filepath}")
    
    # Check file size - if less than 100KB, likely corrupted
    if file_size < 100 * 1024:
        raise UploadError(f"Video file too small ({file_size} bytes), likely corrupted: {filepath}")
    
    try:
        # Use ffprobe to get duration
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            # ffprobe failed - might be corrupted or not a video
            raise UploadError(f"ffprobe failed for {filepath}: {result.stderr}")
        
        duration_str = result.stdout.strip()
        if not duration_str:
            raise UploadError(f"Could not determine video duration for {filepath}")
        
        duration = float(duration_str)
        
        if duration < min_duration_seconds:
            raise UploadError(f"Video duration too short: {duration:.2f}s (minimum: {min_duration_seconds}s)")
        
        logger.info(f"✅ Video validation passed: {os.path.basename(filepath)} - Duration: {duration:.2f}s, Size: {file_size / (1024*1024):.2f}MB")
        return duration
        
    except subprocess.TimeoutExpired:
        raise UploadError(f"ffprobe timeout for {filepath}")
    except ValueError:
        raise UploadError(f"Invalid duration output from ffprobe for {filepath}: {result.stdout}")
    except Exception as e:
        if isinstance(e, UploadError):
            raise
        raise UploadError(f"Video validation failed for {filepath}: {str(e)}")


def clean_metadata(title, description):
    """
    Cleans title and description by replacing competitor domain names with our brand name.
    Also ensures description is full and appends SEO tags.
    """
    import re
    
    brand_name = "viral hawas"
    domains_to_replace = [
        r'viralkand\.com', r'viralkand', 
        r'uruduchudai\.com', r'uruduchudai',
        r'thekamababa\.com', r'thekamababa',
        r'kamababa'
    ]
    
    # 1. Clean Title
    if title:
        for domain in domains_to_replace:
            title = re.sub(domain, brand_name, title, flags=re.IGNORECASE)
    else:
        title = f"Latest {brand_name} video"
            
    # 2. Clean Description & expand if too short
    if description:
        for domain in domains_to_replace:
            description = re.sub(domain, brand_name, description, flags=re.IGNORECASE)
    else:
        description = ""
        
    # If description is too short (truncated meta), use the title to make a full SEO friendly description
    if len(description) < 50:
        description = f"{title} - Watch the full viral video exclusively on {brand_name}. We bring you the latest trending, leaked, and viral MMS videos daily. Enjoy high-quality streaming of {brand_name} content.\n\n{description}"
        
    # 3. Generate SEO tags
    # Extract some words from title to use as tags
    words = [w for w in re.split(r'\W+', title.lower()) if len(w) > 3]
    tags_list = ['viralhawas', 'desibhabhi', 'viralvideo', 'trending', 'leaked', 'mms'] + words[:5]
    # Remove duplicates while preserving order
    seen = set()
    tags_list = [x for x in tags_list if not (x in seen or seen.add(x))]
    
    tags_str = " ".join([f"#{tag}" for tag in tags_list])
    
    # Append tags to description
    if "#viralhawas" not in description:
        description = f"{description}\n\nTags: {tags_str}"
        
    return title.strip(), description.strip()
