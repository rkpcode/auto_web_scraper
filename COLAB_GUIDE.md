# 🎬 Video Scraper Pipeline - Colab Interactive Mode

## 📋 Overview
Automatically discover, download, and upload videos to Bunny Stream from any website using Google Colab.

---

## 🚀 Quick Start (Google Colab)

### **Step 1: Upload to Google Drive**
Upload the entire `video_engine` folder to your Google Drive:
```
/content/drive/MyDrive/video_engine/
```

### **Step 2: Install Dependencies**
```python
# Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# Navigate to project
%cd /content/drive/MyDrive/video_engine

# Install requirements
!pip install -q -r requirements.txt
!playwright install chromium
```

### **Step 3: Setup Environment Variables**
Create a `.env` file in the `video_engine` folder with your Bunny Stream credentials:
```bash
BUNNY_API_KEY=your_api_key_here
BUNNY_LIBRARY_ID=your_library_id_here
```

Or set them in Colab:
```python
import os
os.environ['BUNNY_API_KEY'] = 'your_api_key_here'
os.environ['BUNNY_LIBRARY_ID'] = 'your_library_id_here'
```

### **Step 4: Run Interactive Pipeline**
```python
!python colab_interactive.py
```

---

## 🎯 Usage Flow

When you run `colab_interactive.py`, it will:

1. **Ask for Website URL**
   ```
   🌐 Enter website URL: https://example.com
   ```

2. **Choose Discovery Method**
   - Option 1: Auto (sitemap first, then crawl)
   - Option 2: Sitemap only
   - Option 3: Generic crawling

3. **Set Max Pages** (for crawling)
   ```
   📄 Max pages to crawl [default: 10]: 20
   ```

4. **Discover Videos**
   - Automatically finds all video URLs on the website
   - Saves them to database

5. **Confirm Processing**
   ```
   🚀 Start processing? (y/n) [default: y]: y
   ```

6. **Process Videos**
   - Downloads each video
   - Uploads to Bunny Stream
   - Shows real-time progress

---

## 📊 Available Scripts

### **1. `colab_interactive.py`** ✅ **RECOMMENDED**
Interactive mode with website URL input
```python
!python colab_interactive.py
```

**Features:**
- ✅ Takes website URL as input
- ✅ Auto-discovers videos
- ✅ Downloads and uploads to Bunny
- ✅ Real-time progress
- ✅ User-friendly prompts

---

### **2. `run_colab.py`**
Automatic mode using `links.txt`
```python
!python run_colab.py
```

**Features:**
- ✅ Loads URLs from `links.txt`
- ✅ No user input needed
- ✅ Good for batch processing

---

### **3. `main.py`**
Original pipeline (non-interactive)
```python
!python main.py
```

---

### **4. `fix_db_lock.py`**
Fix database locking issues
```python
!python fix_db_lock.py
```

**Use when:**
- Database is locked error appears
- Pipeline crashes mid-run

---

## 🛠️ Troubleshooting

### **Database is locked**
```python
!python fix_db_lock.py
```

### **Browser timeout errors**
- Increase timeout in `config.py`
- Some websites block automated access
- Try different discovery method

### **Out of memory (Colab)**
- Reduce `MAX_WORKERS` in config
- Process fewer videos at once
- Use Colab Pro for more RAM

### **No videos discovered**
- Check if website has videos
- Try different discovery method
- Check website's robots.txt

---

## 📁 Project Structure

```
video_engine/
├── colab_interactive.py    # 🎯 Colab interactive pipeline
├── run_colab.py            # Auto-run from links.txt
├── main.py                 # Original pipeline
├── interactive_pipeline.py # Local interactive mode
├── fix_db_lock.py          # Database fix utility
├── harvester.py            # Video URL discovery
├── database.py             # SQLite database manager
├── config.py               # Configuration
├── requirements.txt        # Python dependencies
├── core/
│   ├── downloader.py       # yt-dlp video downloader
│   ├── uploader.py         # Bunny Stream uploader
│   ├── logger.py           # Logging setup
│   ├── exceptions.py       # Custom exceptions
│   └── utils.py            # Utility functions
└── extractors/
    ├── base_extractor.py   # Base extractor class
    ├── browser_extractor.py # Playwright browser extractor
    ├── generic_extractor.py # Generic video extractor
    └── viralkand_extractor.py # Site-specific extractor
```

---

## 🎨 Example Session

```
🎬 COLAB INTERACTIVE VIDEO SCRAPER PIPELINE
======================================================================

📋 WEBSITE VIDEO DISCOVERY
----------------------------------------------------------------------
🌐 Enter website URL: https://viralkand.com

📊 Discovery Options:
1. Auto (try sitemap first, then crawl)
2. Sitemap only
3. Generic crawling

Enter choice (1/2/3) [default: 1]: 1
📄 Max pages to crawl [default: 10]: 20

======================================================================
🔍 DISCOVERING VIDEOS
======================================================================
🌐 Website: https://viralkand.com
📊 Method: auto
📄 Max pages: 20
----------------------------------------------------------------------

✅ Discovered 15 new video URLs

======================================================================
📊 Ready to process 15 video(s)
⚙️  Workers: 2
🎯 Action: Download → Upload to Bunny Stream
======================================================================

🚀 Start processing? (y/n) [default: y]: y

======================================================================
🎬 STARTING VIDEO PROCESSING
======================================================================
✅ [1/15] Processed successfully
✅ [2/15] Processed successfully
❌ [3/15] Failed: Timeout
✅ [4/15] Processed successfully
...

======================================================================
✅ PIPELINE COMPLETE
======================================================================

📊 Final Results:
   COMPLETED   :  12
   FAILED      :   3
```

---

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Workers (concurrent downloads)
MAX_WORKERS = 2  # Reduced for Colab

# Browser settings
USE_BROWSER_FOR_PROTECTED_SITES = True
BROWSER_HEADLESS = True

# Disk space
MIN_FREE_DISK_GB = 5
```

---

## 📝 Database Status Tracking

Videos go through these statuses:
- `PENDING` - Waiting to be processed
- `EXTRACTING` - Extracting video URL
- `DOWNLOADING` - Downloading video
- `UPLOADING` - Uploading to Bunny
- `COMPLETED` - Successfully uploaded
- `FAILED` - Error occurred

---

## 🔐 Security Notes

- Never commit `.env` file to Git
- Keep your Bunny API key secret
- Use environment variables in Colab

---

## 📞 Support

For issues:
1. Check logs in `pipeline.log`
2. Run `fix_db_lock.py` if database locked
3. Check Bunny Stream dashboard for uploads

---

## ✨ Features

✅ Automatic video discovery (sitemap + crawling)  
✅ Multi-threaded downloads  
✅ Bunny Stream integration  
✅ Crash recovery  
✅ Database status tracking  
✅ Browser-based extraction (Playwright)  
✅ Retry logic with exponential backoff  
✅ User-agent rotation  
✅ Colab-optimized  

---

**Happy Scraping! 🎬**
