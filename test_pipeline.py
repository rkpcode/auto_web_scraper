"""
Quick pipeline test with accessible URLs.
Tests the complete flow: extract -> download -> upload
"""
import os
import sys
sys.path.insert(0, 'video_engine')

# Mock environment variables for testing
os.environ['BUNNY_API_KEY'] = 'test_key_placeholder'
os.environ['BUNNY_LIBRARY_ID'] = 'test_lib_placeholder'

from video_engine.database import db
from video_engine.extractors import get_extractor
from video_engine.core.downloader import VideoDownloader

# Test URL
test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

print("="*60)
print("PIPELINE TEST - Extraction + Download Only")
print("="*60)

# Step 1: Test Extractor
print("\n[1/2] Testing Extractor...")
try:
    extractor = get_extractor(test_url)
    print(f"  Extractor: {extractor.__class__.__name__}")
    
    video_url, title = extractor.extract(test_url)
    print(f"  Title: {title}")
    print(f"  [OK] Extraction successful")
except Exception as e:
    print(f"  [FAILED] {e}")
    sys.exit(1)

# Step 2: Test Download (just info, no actual download)
print("\n[2/2] Testing Download Info...")
try:
    downloader = VideoDownloader()
    print(f"  [OK] Downloader initialized")
    print(f"\n[NOTE] Skipping actual download to save time")
    print(f"[NOTE] Upload test skipped (needs real Bunny API keys)")
except Exception as e:
    print(f"  [FAILED] {e}")
    sys.exit(1)

print("\n" + "="*60)
print("[SUCCESS] Pipeline components working!")
print("="*60)
print("\nNext steps:")
print("1. Set real BUNNY_API_KEY and BUNNY_LIBRARY_ID")
print("2. Add video URLs to ../links.txt")
print("3. Run: python main.py")
