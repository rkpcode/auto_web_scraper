# 🎬 Colab Setup - Copy-Paste Ready

## Quick Setup (Copy each cell to Colab)

### Cell 1: Mount Drive & Install
```python
# Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# Navigate to project
%cd /content/drive/MyDrive/video_engine

# Install dependencies
!pip install -q -r requirements.txt
!playwright install chromium

print("✅ Setup complete!")
```

### Cell 2: Set Environment Variables
```python
import os

# Set your Bunny Stream credentials
os.environ['BUNNY_API_KEY'] = 'YOUR_API_KEY_HERE'
os.environ['BUNNY_LIBRARY_ID'] = 'YOUR_LIBRARY_ID_HERE'

print("✅ Environment variables set!")
```

### Cell 3: Run Interactive Pipeline
```python
!python colab_interactive.py
```

---

## Alternative: Auto-run from links.txt

### Cell 1 & 2: Same as above

### Cell 3: Create links.txt
```python
# Create links.txt with your URLs
with open('links.txt', 'w') as f:
    f.write('''https://example.com/video1
https://example.com/video2
https://example.com/video3
''')

print("✅ links.txt created!")
```

### Cell 4: Run Auto Pipeline
```python
!python run_colab.py
```

---

## Fix Database Lock (if needed)
```python
!python fix_db_lock.py
```

---

## View Logs
```python
!tail -50 pipeline.log
```

---

## Check Database Status
```python
import sqlite3

conn = sqlite3.connect('video_tracker.db')
cursor = conn.cursor()
cursor.execute("SELECT status, COUNT(*) FROM videos GROUP BY status")
stats = cursor.fetchall()
conn.close()

print("📊 Database Status:")
for status, count in stats:
    print(f"   {status:12s}: {count:3d}")
```
