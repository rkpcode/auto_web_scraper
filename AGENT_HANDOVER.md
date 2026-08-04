# Agent Handover & Project Status Context
**Date:** August 2026
**Project:** Auto Web Scraper (Video Processing Pipeline)

## Recent Bug Fixes and Updates (Important for Future Agents)

### 1. SeekStreaming "Missing ID" Bug Fixed
- **Issue:** 2,992 videos were successfully uploading to SeekStreaming but showing as `PENDING`/`FAILED` in the Supabase database.
- **Root Cause:** A `NameError: name 'title' is not defined` inside `video_engine/core/free_host_uploader.py`. The `_tus_upload_single` and `_tus_upload_chunked` methods were calling `self.set_metadata(filecode, title, description)` but `title` and `description` were not passed into their function signatures. The script crashed *after* upload but *before* saving the ID to the database.
- **Fix Applied:** Updated the function signatures and passing of `title` and `description` in `video_engine/core/free_host_uploader.py`. The database was manually patched (2,992 rows updated to `COMPLETED`) to prevent duplicate processing.

### 2. BrowserExtractor Enabled for New Domains (`viralmms.site`)
- **Issue:** `yt-dlp` was failing with `DownloadError: yt-dlp download failed: ERROR: Unsupported URL` for URLs from `viralmms.site`.
- **Root Cause:** `yt-dlp`'s `GenericExtractor` cannot handle dynamic/protected tube sites properly. The system has a robust Playwright-based `BrowserExtractor`, but it was hardcoded to only run on `viralkand.com` and `thekamababa.com`.
- **Fix Applied:** Edited `video_engine/extractors/__init__.py` to include `viralmms.site` and `urduchudai.com` in the list of domains that trigger the `BrowserExtractor`. 

### 3. SeekStreaming as Primary Target
- The user has mandated that **SeekStreaming is the compulsory/primary upload provider**.
- Backups (like Doodstream or Lulustream) will be handled separately via a dedicated button, and the main pipeline should focus strictly on SeekStreaming.

### 4. Git & Hugging Face Syncing
- All recent changes have been pushed to both `origin` (GitHub) and `hf` (Hugging Face Spaces) remotes.
- When making backend changes, ensure they are pushed to the `hf` remote (`git push hf main`) so the live Hugging Face Space is immediately updated.

## Harvester Behavior Notes
- The harvester automatically skips duplicate URLs. If the logs show `Successfully added X new URLs (skipped Y duplicates)`, it means `Y` URLs were already in the `videos` table (`original_url` is a UNIQUE constraint). This is normal and expected behavior.
