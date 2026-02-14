import os
import uuid
import random
import shutil
from core.logger import logger


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


def get_disk_free_space_gb(path="/"):
    """Get free disk space in GB."""
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
