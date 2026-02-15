# 🚀 Deploy Video Scraper to Hugging Face Spaces

## 📋 Prerequisites

- Hugging Face account
- Bunny Stream API credentials
- Git installed locally

---

## 🎯 Deployment Steps

### **Step 1: Create Hugging Face Space**

1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Fill in details:
   - **Space name**: `video-scraper-pipeline`
   - **License**: MIT
   - **SDK**: Gradio
   - **Hardware**: CPU basic (free)
4. Click "Create Space"

---

### **Step 2: Clone Your Space**

```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/video-scraper-pipeline
cd video-scraper-pipeline
```

---

### **Step 3: Copy Files**

Copy these files to your Space directory:

```bash
# Copy main app
cp huggingface_app.py app.py

# Copy video_engine folder
cp -r video_engine/ .

# Copy requirements
cp requirements_hf.txt requirements.txt

# Copy README
cp README.md .
```

**File structure should be:**
```
video-scraper-pipeline/
├── app.py                    # Main Gradio app
├── requirements.txt          # Dependencies
├── README.md                 # Documentation
└── video_engine/            # Scraper modules
    ├── __init__.py
    ├── main.py
    ├── database.py
    ├── harvester.py
    ├── config.py
    ├── core/
    │   ├── downloader.py
    │   ├── uploader.py
    │   ├── logger.py
    │   ├── exceptions.py
    │   └── utils.py
    └── extractors/
        ├── base_extractor.py
        ├── browser_extractor.py
        ├── generic_extractor.py
        └── viralkand_extractor.py
```

---

### **Step 4: Set Environment Variables**

1. Go to your Space settings
2. Click "Settings" → "Variables and secrets"
3. Add secrets:
   - **Name**: `BUNNY_API_KEY`, **Value**: `your_api_key_here`
   - **Name**: `BUNNY_LIBRARY_ID`, **Value**: `your_library_id_here`

---

### **Step 5: Push to Hugging Face**

```bash
git add .
git commit -m "Initial deployment"
git push
```

---

### **Step 6: Install Playwright (Important!)**

Create a file named `packages.txt` in your Space root:

```bash
# packages.txt
chromium
chromium-driver
```

This will install Chromium browser for Playwright.

---

### **Step 7: Access Your App**

Your app will be available at:
```
https://huggingface.co/spaces/YOUR_USERNAME/video-scraper-pipeline
```

---

## 🎨 Using the App

1. **Enter Website URL**: e.g., `https://viralkand.com`
2. **Choose Discovery Method**: Auto (recommended)
3. **Set Max Pages**: 10-20 for testing
4. **Set Workers**: 2 (recommended for free tier)
5. **Click "Start Scraping"**
6. **Monitor Progress**: Real-time logs will show progress
7. **Check Stats**: View database statistics in "View Database" tab

---

## ⚠️ Limitations

### **Hugging Face Spaces Free Tier:**
- 16GB RAM
- 2 vCPU cores
- 50GB storage
- CPU-only (no GPU)
- Sleeps after 48h inactivity

### **Recommendations:**
- Use 2 workers maximum
- Process max 50 videos at a time
- Avoid very large websites

---

## 🔄 Alternative: GitHub Actions + Hugging Face

You can also use GitHub Actions to trigger scraping and store results on Hugging Face:

### **Workflow:**
```
GitHub Actions → Run Scraper → Upload to Bunny → Update HF Dataset
```

Create `.github/workflows/scrape.yml`:

```yaml
name: Scheduled Scraping

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  scrape:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install-deps
          playwright install chromium
      
      - name: Run scraper
        env:
          BUNNY_API_KEY: ${{ secrets.BUNNY_API_KEY }}
          BUNNY_LIBRARY_ID: ${{ secrets.BUNNY_LIBRARY_ID }}
        run: python video_engine/main.py
      
      - name: Upload database to HF
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          pip install huggingface_hub
          python -c "
          from huggingface_hub import HfApi
          api = HfApi()
          api.upload_file(
              path_or_fileobj='video_engine/video_tracker.db',
              path_in_repo='video_tracker.db',
              repo_id='YOUR_USERNAME/video-scraper-data',
              repo_type='dataset',
              token='$HF_TOKEN'
          )
          "
```

---

## 🎯 Best Approach Comparison

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **HF Spaces + Gradio** | ✅ Web UI<br>✅ Free hosting<br>✅ Easy to use | ⚠️ Limited resources<br>⚠️ Sleeps after inactivity | Interactive scraping, demos |
| **GitHub Actions** | ✅ Automated<br>✅ Scheduled runs<br>✅ Free 2000 min/mo | ⚠️ No UI<br>⚠️ Limited runtime | Scheduled batch scraping |
| **GitHub Actions + HF** | ✅ Best of both<br>✅ Automated + Storage | ⚠️ More complex setup | Production workflows |

---

## 💡 Recommended Setup

**For your use case, I recommend:**

### **Option A: Hugging Face Spaces Only**
- Deploy Gradio app
- Users manually trigger scraping
- Good for: On-demand scraping

### **Option B: GitHub Actions + HF Dataset** (BEST)
- GitHub Actions runs scraper every 6 hours
- Uploads database to HF Dataset
- Gradio app on HF Spaces shows results
- Good for: Automated continuous scraping

---

## 🛠️ Troubleshooting

### **App not starting:**
- Check if `packages.txt` has chromium
- Verify environment variables are set

### **Out of memory:**
- Reduce workers to 1
- Process fewer videos at once

### **Database locked:**
- Refresh the page
- Run fix_db_lock.py locally

---

## 📞 Support

- [Hugging Face Docs](https://huggingface.co/docs/hub/spaces)
- [Gradio Docs](https://gradio.app/docs/)
- [GitHub Actions Docs](https://docs.github.com/en/actions)

---

**Happy Scraping! 🎬**
