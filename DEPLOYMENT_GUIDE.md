# 🚀 Complete Deployment Guide - Option 3
## GitHub Actions + Hugging Face Spaces

This guide will help you deploy the complete automated video scraping pipeline.

---

## 📋 Prerequisites

Before starting, make sure you have:

- ✅ GitHub account
- ✅ Hugging Face account
- ✅ Bunny Stream API credentials
- ✅ Git installed on your machine
- ✅ All project files ready

---

## 🎯 Architecture Overview

```
┌─────────────────────┐
│  GitHub Actions     │ ← Runs every 6 hours
│  (Automated Scraper)│
└──────────┬──────────┘
           │
           ├─────────────────────────────────┐
           │                                 │
           ▼                                 ▼
┌──────────────────────┐         ┌──────────────────────┐
│   Bunny Stream       │         │  HF Dataset          │
│   (Video Storage)    │         │  (Database Backup)   │
└──────────────────────┘         └──────────┬───────────┘
                                            │
                                            ▼
                                 ┌──────────────────────┐
                                 │  HF Spaces           │
                                 │  (Web UI)            │
                                 └──────────────────────┘
```

---

## 📦 PHASE 1: Prepare Repository

### Step 1.1: Create .gitignore

Create `.gitignore` file:

```bash
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
*.egg-info/
dist/
build/

# Environment
.env
.env.local

# Database
*.db
*.db-wal
*.db-shm

# Logs
*.log
pipeline.log

# Temp files
temp_storage/
downloads/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

### Step 1.2: Create README for HF Spaces

Create `README_SPACES.md`:

```markdown
---
title: Video Scraper Pipeline
emoji: 🎬
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
---

# 🎬 Video Scraper Pipeline

Automatically discover, download, and upload videos to Bunny Stream from any website.

## Features

- 🔍 Auto-discover videos from websites
- 📥 Download videos using yt-dlp
- ☁️ Upload to Bunny Stream
- 📊 Track processing status
- 🎨 User-friendly Gradio interface

## How to Use

1. Enter a website URL
2. Choose discovery method (Auto recommended)
3. Set max pages to crawl
4. Click "Start Scraping"
5. Monitor progress in real-time

## Configuration

Set these secrets in Space settings:
- `BUNNY_API_KEY`: Your Bunny Stream API key
- `BUNNY_LIBRARY_ID`: Your Bunny Stream library ID

## Limitations

- Free tier: 16GB RAM
- Recommended: 2 workers max
- Process 50 videos at a time

## GitHub Repository

[View Source Code](https://github.com/YOUR_USERNAME/web_scrapper)
```

---

## 🐙 PHASE 2: GitHub Setup

### Step 2.1: Initialize Git Repository

```bash
cd c:\DataScience_AI_folder\Portfolio\web_scrapper

# Initialize Git
git init

# Add all files
git add .

# First commit
git commit -m "Initial commit: Video scraper pipeline with HF and GitHub Actions support"
```

### Step 2.2: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `web_scrapper` (or your choice)
3. Description: "Automated video scraping pipeline with Bunny Stream integration"
4. Visibility: **Private** (recommended) or Public
5. **Don't** initialize with README (we already have one)
6. Click "Create repository"

### Step 2.3: Push to GitHub

```bash
# Add remote
git remote add origin https://github.com/YOUR_USERNAME/web_scrapper.git

# Push
git branch -M main
git push -u origin main
```

### Step 2.4: Add GitHub Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these secrets:

| Name | Value |
|------|-------|
| `BUNNY_API_KEY` | Your Bunny Stream API key |
| `BUNNY_LIBRARY_ID` | Your Bunny Stream library ID |
| `HF_TOKEN` | Your Hugging Face token (optional) |

**To get HF Token:**
- Go to https://huggingface.co/settings/tokens
- Click "New token"
- Name: `video-scraper`
- Role: `write`
- Copy the token

---

## 🤗 PHASE 3: Hugging Face Spaces Setup

### Step 3.1: Create HF Space

1. Go to https://huggingface.co/spaces
2. Click **"Create new Space"**
3. Fill in details:
   - **Owner**: Your username
   - **Space name**: `video-scraper-pipeline`
   - **License**: MIT
   - **Select the SDK**: Gradio
   - **Space hardware**: CPU basic (free)
   - **Visibility**: Public or Private
4. Click **"Create Space"**

### Step 3.2: Clone HF Space

```bash
# Clone your space
git clone https://huggingface.co/spaces/YOUR_USERNAME/video-scraper-pipeline
cd video-scraper-pipeline
```

### Step 3.3: Copy Files to HF Space

```bash
# Copy main app
cp ../web_scrapper/huggingface_app.py app.py

# Copy video_engine folder
cp -r ../web_scrapper/video_engine .

# Copy requirements
cp ../web_scrapper/requirements_hf.txt requirements.txt

# Copy packages
cp ../web_scrapper/packages.txt .

# Copy README
cp ../web_scrapper/README_SPACES.md README.md

# Create .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*.db
*.db-wal
*.db-shm
*.log
temp_storage/
.env
EOF
```

### Step 3.4: Add HF Secrets

1. Go to your Space settings
2. Click **"Settings"** → **"Variables and secrets"**
3. Click **"New secret"**
4. Add these secrets:

| Name | Value |
|------|-------|
| `BUNNY_API_KEY` | Your Bunny Stream API key |
| `BUNNY_LIBRARY_ID` | Your Bunny Stream library ID |

### Step 3.5: Push to HF Spaces

```bash
git add .
git commit -m "Deploy video scraper to HF Spaces"
git push
```

### Step 3.6: Wait for Build

- HF Spaces will automatically build your app
- Check the "Logs" tab for build progress
- Once built, your app will be live!

---

## 🧪 PHASE 4: Testing & Verification

### Step 4.1: Test GitHub Actions

1. Go to your GitHub repository
2. Click **Actions** tab
3. Click **"Automated Video Scraping"** workflow
4. Click **"Run workflow"** → **"Run workflow"**
5. Monitor the workflow execution
6. Check artifacts after completion

### Step 4.2: Test HF Spaces

1. Go to your Space URL:
   ```
   https://huggingface.co/spaces/YOUR_USERNAME/video-scraper-pipeline
   ```
2. Enter a test website URL (e.g., `https://viralkand.com`)
3. Click "Start Scraping"
4. Monitor the logs
5. Check "View Database" tab for stats

### Step 4.3: Verify Bunny Stream

1. Go to Bunny Stream dashboard
2. Check if videos are being uploaded
3. Verify video playback

### Step 4.4: Check HF Dataset (Optional)

If you set up HF_TOKEN:

1. Go to https://huggingface.co/datasets/YOUR_USERNAME/video-scraper-data
2. Check if database file is uploaded
3. Download and verify

---

## 📊 Monitoring & Maintenance

### View GitHub Actions Logs

```bash
# Go to your repository
https://github.com/YOUR_USERNAME/web_scrapper/actions
```

### View HF Spaces Logs

```bash
# Go to your Space
https://huggingface.co/spaces/YOUR_USERNAME/video-scraper-pipeline
# Click "Logs" tab
```

### Download Database from HF Dataset

```bash
# Install huggingface_hub
pip install huggingface_hub

# Download database
python -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='YOUR_USERNAME/video-scraper-data',
    filename='video_tracker.db',
    repo_type='dataset',
    local_dir='.'
)
"
```

---

## 🔧 Troubleshooting

### GitHub Actions fails

**Check:**
- Secrets are set correctly
- Workflow file syntax is correct
- Check logs in Actions tab

**Fix:**
```bash
# Re-run workflow
# Go to Actions → Failed workflow → Re-run jobs
```

### HF Spaces not building

**Check:**
- `requirements.txt` is correct
- `packages.txt` has chromium
- Check build logs

**Fix:**
```bash
# Update requirements
git add requirements.txt
git commit -m "Fix requirements"
git push
```

### Database locked error

**Fix:**
```bash
# Run locally
python video_engine/fix_db_lock.py
```

### No videos discovered

**Check:**
- Website URL is correct
- Website has videos
- Try different discovery method

---

## 🎯 Final URLs

After deployment, you'll have:

1. **GitHub Repository:**
   ```
   https://github.com/YOUR_USERNAME/web_scrapper
   ```

2. **HF Spaces (Web UI):**
   ```
   https://huggingface.co/spaces/YOUR_USERNAME/video-scraper-pipeline
   ```

3. **HF Dataset (Database Backup):**
   ```
   https://huggingface.co/datasets/YOUR_USERNAME/video-scraper-data
   ```

4. **GitHub Actions (Automation):**
   ```
   https://github.com/YOUR_USERNAME/web_scrapper/actions
   ```

---

## 🎉 Success!

Your automated video scraping pipeline is now live!

**What happens now:**
- ✅ GitHub Actions runs every 6 hours automatically
- ✅ Videos are scraped and uploaded to Bunny Stream
- ✅ Database is backed up to HF Dataset
- ✅ You can monitor via HF Spaces web UI
- ✅ Manual scraping available via HF Spaces

---

## 📞 Support

- GitHub Issues: Create issue in your repo
- HF Community: https://huggingface.co/spaces/YOUR_USERNAME/video-scraper-pipeline/discussions
- Documentation: Check README files

---

**Happy Scraping! 🎬**
