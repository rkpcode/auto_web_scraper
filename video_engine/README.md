# Video Engine - Scalable Video Ingestion Pipeline

Production-ready video scraper with concurrent processing and crash recovery.

## Architecture

```
video_engine/
├── main.py                    # Entry point with ThreadPoolExecutor
├── config.py                  # Configuration (auto-detects Colab Drive mount)
├── database.py                # Thread-safe SQLite with zombie thread recovery
├── requirements.txt           # Python dependencies
├── core/                      # Core components
│   ├── logger.py             # Persistent logging
│   ├── downloader.py         # yt-dlp wrapper with proxy support
│   ├── uploader.py           # Bunny Stream API client
│   ├── utils.py              # Utilities (cleanup, disk check, etc.)
│   └── exceptions.py         # Custom exceptions (auto-logging)
└── extractors/               # Site-specific extractors (factory pattern)
    ├── __init__.py           # Factory: get_extractor(url)
    ├── base_extractor.py     # Abstract base class
    └── generic_extractor.py  # Fallback (uses yt-dlp)
```

## Features

- **Concurrency**: ThreadPoolExecutor for parallel download+upload (no bottlenecks)
- **Crash Recovery**: Granular status tracking (PENDING → EXTRACTING → DOWNLOADING → UPLOADING → COMPLETED)
- **Thread Safety**: `threading.Lock()` prevents SQLite conflicts
- **Persistent Storage**: Auto-detects Google Drive mount for logs and database
- **Disk Management**: Monitors free space before downloads
- **Proxy Support**: Optional proxy configuration for yt-dlp
- **Custom Exceptions**: Auto-logging exception classes for better error tracking

## Setup

### 1. Install Dependencies
```bash
cd video_engine
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
export BUNNY_API_KEY="your_api_key_here"
export BUNNY_LIBRARY_ID="your_library_id_here"
```

### 3. (Optional) Mount Google Drive (Colab)
```python
from google.colab import drive
drive.mount('/content/drive')
```

## Usage

### Add URLs to Process
Create a `links.txt` file in the parent directory with one URL per line.

### Run Pipeline
```bash
python main.py
```

### Check Status
```python
from database import db
print(db.get_stats())
```

## Configuration

Edit `config.py` to customize:
- `MAX_WORKERS`: Number of concurrent downloads (default: 4)
- `MIN_FREE_DISK_GB`: Minimum free disk space (default: 5GB)
- `PROXY_URL`: Proxy for yt-dlp (default: None)

## Production Notes

1. **Zombie Thread Recovery**: On startup, the pipeline resets stale DOWNLOADING/UPLOADING statuses to PENDING
2. **Database Lock Prevention**: All DB writes use `threading.Lock()`
3. **Guaranteed Cleanup**: Files are deleted in `finally` blocks even on errors
4. **Disk Pressure**: Pipeline pauses if free space < 5GB
