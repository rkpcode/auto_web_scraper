import os

# Bunny Stream API Configuration
BUNNY_API_KEY = os.getenv("BUNNY_API_KEY", "")
BUNNY_LIBRARY_ID = os.getenv("BUNNY_LIBRARY_ID", "")
BUNNY_BASE_URL = "https://video.bunnycdn.com/library"

# Project Paths (Colab-compatible with Drive mount)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Check if running on Colab and Drive is mounted
if os.path.exists("/content/drive/MyDrive"):
    # Colab environment with Drive mounted
    DRIVE_BASE = "/content/drive/MyDrive/video_engine_data"
    os.makedirs(DRIVE_BASE, exist_ok=True)
    DB_PATH = os.path.join(DRIVE_BASE, "video_tracker.db")
    LOG_FILE_PATH = os.path.join(DRIVE_BASE, "pipeline.log")
else:
    # Local environment
    DB_PATH = os.path.join(BASE_DIR, "video_tracker.db")
    LOG_FILE_PATH = os.path.join(BASE_DIR, "pipeline.log")

TEMP_STORAGE_DIR = os.path.join(BASE_DIR, "temp_storage")
os.makedirs(TEMP_STORAGE_DIR, exist_ok=True)

# URLs to process
LINKS_FILE = os.path.join(BASE_DIR, "links.txt")

# Concurrency settings
_MAX_WORKERS_RAW = int(os.getenv("MAX_WORKERS", "4"))

# Browser extractor settings
USE_BROWSER_FOR_PROTECTED_SITES = os.getenv("USE_BROWSER", "true").lower() == "true"
BROWSER_HEADLESS = True  # Always True for Colab/production

# CRITICAL: Auto-reduce workers when browser is enabled to prevent OOM crashes
# Each browser instance uses 400-600MB RAM
# Colab Free tier: ~12GB RAM total
if USE_BROWSER_FOR_PROTECTED_SITES:
    MAX_WORKERS = min(_MAX_WORKERS_RAW, 2)  # Force max 2 workers with browser
    if _MAX_WORKERS_RAW > 2:
        import logging
        logging.warning(f"⚠️  MAX_WORKERS reduced from {_MAX_WORKERS_RAW} to {MAX_WORKERS} (browser mode enabled)")
else:
    MAX_WORKERS = _MAX_WORKERS_RAW

# Proxy settings (optional)
PROXY_URL = os.getenv("PROXY_URL", None)

# Disk management
MIN_FREE_DISK_GB = 5  # Minimum free disk space in GB
