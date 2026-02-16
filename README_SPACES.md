# Video Scraper Pipeline - Hugging Face Spaces

Automated video discovery, download, and upload pipeline with Gradio UI.

## 🚀 Features

- **Two-Phase Processing:** Separate Discovery (Harvester) and Processing (Workers) phases
- **Pagination Support:** Auto-crawls multiple pages with rate limiting
- **Persistent State:** Supabase (PostgreSQL) database survives Space restarts
- **Non-Blocking UI:** Background threading keeps interface responsive
- **HF Spaces Optimized:** Memory-efficient (2 workers, 16GB RAM limit)

## 📋 Setup Instructions

### 1. Create Supabase Database

1. Go to [Supabase](https://supabase.com) and create a new project
2. In SQL Editor, run the schema from `schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    original_url TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'PENDING',
    bunny_guid TEXT,
    local_filename TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_status ON videos(status);
CREATE INDEX idx_created_at ON videos(created_at);
```

3. Get your connection string: Settings > Database > Connection String (URI)

### 2. Set Environment Variables

In Hugging Face Spaces Settings > Variables and Secrets, add:

- `DATABASE_URL`: Your Supabase connection string (PostgreSQL URI)
- `BUNNY_API_KEY`: Bunny Stream API key
- `BUNNY_LIBRARY_ID`: Bunny Stream library ID

### 3. Deploy to HF Spaces

1. Create a new Space (Gradio SDK)
2. Upload all files from this repository
3. The app will auto-start via `startup.sh`

## 🎯 How to Use

### Phase A: Discovery

1. Enter website URL (e.g., `https://example.com`)
2. Set max pages to crawl (default: 5)
3. Click **🔍 Start Discovery**
4. Harvester will:
   - Crawl pages using pagination (`?page=n`)
   - Auto-stop when no new links found
   - Seed URLs to Supabase database

### Phase B: Processing

1. Click **🚀 Start Processing**
2. Workers will:
   - Fetch PENDING videos from database
   - Download using yt-dlp
   - Upload to Bunny Stream
   - Update status to COMPLETED

### Live Dashboard

- Auto-refreshes every 5 seconds
- Shows status distribution (PENDING, COMPLETED, FAILED)
- Displays current phase status

## 🛠️ Architecture

### Database Layer

- **Supabase (PostgreSQL)** for persistent state
- Context managers prevent connection leaks
- `INSERT ... ON CONFLICT` for deduplication

### Harvester Module

- **LinkHarvester:** Pagination-based discovery
- Auto-stop on 2 consecutive zero-link pages
- Random delay (2-5s) between pages to avoid IP bans

### Processing Pipeline

- **ThreadPoolExecutor** with 2 workers (HF optimized)
- Guaranteed cleanup with `finally` blocks
- Crash recovery via `reset_stale_statuses()`

## 📊 Memory Management

**HF Spaces Free Tier: 16GB RAM**

| Component | RAM Usage |
|-----------|-----------|
| Gradio App | ~1GB |
| Harvester (Playwright) | ~800MB |
| Workers (2) | ~1GB |
| **Total** | **~2.8GB** ✅ Safe |

⚠️ **CRITICAL:** Discovery and Processing run separately to avoid OOM crashes.

## 🐛 Troubleshooting

### "Too many clients" Error

- **Cause:** Supabase connection leak
- **Fix:** Restart the Space. All connections use context managers to auto-close.

### Exit Code 137 (OOM)

- **Cause:** Out of Memory
- **Fix:** Ensure MAX_WORKERS=2 (hardcoded in config.py)

### No Links Found

- **Cause:** Website structure incompatible or no videos
- **Fix:** Try different URL or check if site has videos

### Discovery Stuck

- **Cause:** Browser instance not closed
- **Fix:** Restart Space. Harvester includes cleanup in `finally` block.

## 📁 Project Structure

```
web_scrapper/
├── app.py                          # Gradio UI (main entry point)
├── schema.sql                      # Supabase database schema
├── startup.sh                      # HF Spaces startup script
├── requirements.txt                # Python dependencies
├── video_engine/
│   ├── config.py                   # Configuration (MAX_WORKERS=2)
│   ├── database_supabase.py        # Supabase manager
│   ├── harvester.py                # LinkHarvester with pagination
│   ├── main_twophase.py            # Two-phase CLI version
│   ├── core/
│   │   ├── downloader.py           # yt-dlp wrapper
│   │   ├── uploader.py             # Bunny Stream API
│   │   └── logger.py               # Logging setup
│   └── extractors/                 # Site-specific extractors
```

## 🔒 Security Notes

- Never commit `.env` files with secrets
- Use HF Spaces Secrets for sensitive variables
- Supabase connection string contains credentials

## 📝 License

MIT License - See LICENSE file

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Test locally with Supabase
4. Submit pull request

## 🙏 Credits

- **yt-dlp:** Video downloading
- **Playwright:** Browser automation
- **Gradio:** Web interface
- **Supabase:** PostgreSQL database
- **Bunny Stream:** Video hosting
