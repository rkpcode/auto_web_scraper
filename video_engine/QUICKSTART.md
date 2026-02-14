# Quick Start - Running Your First Test

## ✅ Verified Working

The pipeline has been tested and works with:
- YouTube URLs
- Any yt-dlp supported sites

## 🚀 Run a Test Now

### 1. Set Environment Variables

```powershell
$env:BUNNY_API_KEY = "your_actual_key"
$env:BUNNY_LIBRARY_ID = "your_actual_library_id"
```

### 2. Add Test URLs

Edit `../links.txt`:
```
https://www.youtube.com/watch?v=jNQXAC9IVRw
https://www.youtube.com/watch?v=aqz-KE-bpKQ
```

### 3. Run Pipeline

```powershell
cd video_engine
python main.py
```

### 4. Monitor Progress

```powershell
# Watch logs
Get-Content pipeline.log -Tail 20 -Wait

# Check status
python -c "from database import db; print(db.get_stats())"
```

## ⚠️ Known Issues

**viralkand.com / thekamababa.com are BLOCKED**
- These sites have CloudFlare protection
- See `PROTECTED_SITES.md` for workarounds
- Use yt-dlp supported sites for now

## 📊 Expected Output

```
============================================================
🚀 Starting Video Ingestion Pipeline
============================================================
🔄 Reset 0 stale statuses to PENDING
📊 Processing 2 URLs with 4 workers
📹 Extracted: Me at the zoo
⬇️  Starting download...
📦 Downloaded: abc123.mp4 (1.2MB)
✅ Upload complete
```

## 🎯 Next Steps

1. **Test with your Bunny API keys**
2. **Add more yt-dlp supported URLs**
3. **For protected sites**: See `PROTECTED_SITES.md`
4. **For auto-discovery**: Request Harvester module (Phase 2)
