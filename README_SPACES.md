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

[View Source Code](https://github.com/rkpcode/web_scrapper)
