import os

# ============================================================================
# DATABASE CONFIGURATION (Supabase PostgreSQL)
# ============================================================================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable must be set. "
        "Get it from Supabase: Settings > Database > Connection String (URI)"
    )

# CRITICAL: Add connection timeout to handle HF Spaces latency spikes
# Supabase shared environment can have variable latency
if "connect_timeout" not in DATABASE_URL:
    import logging
    logging.warning(
        "[WARN] DATABASE_URL missing connect_timeout parameter. "
        "Add '?connect_timeout=10' to prevent hanging connections."
    )

# ============================================================================
# BUNNY STREAM API CONFIGURATION
# ============================================================================
BUNNY_API_KEY = os.getenv("BUNNY_API_KEY", "")
BUNNY_LIBRARY_ID = os.getenv("BUNNY_LIBRARY_ID", "")
BUNNY_BASE_URL = "https://video.bunnycdn.com/library"

# ============================================================================
# PROJECT PATHS
# ============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Temporary storage for downloads (cleaned after upload)
TEMP_STORAGE_DIR = os.path.join(BASE_DIR, "temp_storage")
os.makedirs(TEMP_STORAGE_DIR, exist_ok=True)

# Logging
LOG_FILE_PATH = os.path.join(BASE_DIR, "pipeline.log")

# ============================================================================
# CONCURRENCY SETTINGS (HF Spaces Optimized)
# ============================================================================
# CRITICAL: HF Spaces Free Tier has 16GB RAM limit
# Formula: Total RAM ≈ Gradio (1GB) + Harvester×Browser (800MB) + Workers×Cache (500MB each)
# 
# With MAX_WORKERS=2: ~1GB + 800MB + 1GB = 2.8GB (Safe)
# With MAX_WORKERS=4: ~1GB + 800MB + 2GB = 3.8GB (Risky during discovery)

MAX_WORKERS = 2  # HARD LIMIT for HF Spaces

# Override from environment (but cap at 2 for safety)
_MAX_WORKERS_ENV = int(os.getenv("MAX_WORKERS", "2"))
if _MAX_WORKERS_ENV > 2:
    import logging
    logging.warning(f"[WARN] MAX_WORKERS={_MAX_WORKERS_ENV} exceeds safe limit. Capping at 2 for HF Spaces.")
    MAX_WORKERS = 2
else:
    MAX_WORKERS = _MAX_WORKERS_ENV

# ============================================================================
# BROWSER EXTRACTOR SETTINGS
# ============================================================================
USE_BROWSER_FOR_PROTECTED_SITES = os.getenv("USE_BROWSER", "true").lower() == "true"
BROWSER_HEADLESS = True  # Always True for production/HF Spaces

# ============================================================================
# HARVESTER PAGINATION SETTINGS
# ============================================================================
DEFAULT_MAX_PAGES = int(os.getenv("DEFAULT_MAX_PAGES", "5"))
PAGINATION_DELAY_MIN = float(os.getenv("PAGINATION_DELAY_MIN", "2.0"))
PAGINATION_DELAY_MAX = float(os.getenv("PAGINATION_DELAY_MAX", "5.0"))

# ============================================================================
# PROXY SETTINGS (Optional)
# ============================================================================
PROXY_URL = os.getenv("PROXY_URL", None)

# ============================================================================
# DISK MANAGEMENT
# ============================================================================
MIN_FREE_DISK_GB = 5  # Minimum free disk space in GB

# ============================================================================
# HF SPACES DETECTION
# ============================================================================
IS_HF_SPACES = bool(os.getenv("SPACE_ID"))
if IS_HF_SPACES:
    import logging
    logging.warning("🚀 Running on Hugging Face Spaces - Optimizations enabled")
    logging.warning(f"   MAX_WORKERS: {MAX_WORKERS}")
    logging.warning(f"   Database: Supabase (PostgreSQL)")
