#!/bin/bash
# Hugging Face Spaces Startup Script
# Installs Playwright browser and starts Gradio app

echo "🚀 Starting Video Scraper Pipeline..."

# Install Playwright Chromium (only if not cached)
if [ ! -d "/home/user/.cache/ms-playwright" ]; then
    echo "🔧 Installing Playwright Chromium..."
    playwright install chromium
    echo "✅ Playwright installed"
else
    echo "✅ Playwright already installed (cached)"
fi

# Start Gradio app
echo "🎬 Launching Gradio app..."
python app.py
