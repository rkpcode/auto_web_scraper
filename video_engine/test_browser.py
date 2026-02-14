"""
Test BrowserExtractor with protected site.
"""
import sys
import os
sys.path.insert(0, '.')

# Set environment to use browser
os.environ['USE_BROWSER'] = 'true'

from extractors import get_extractor

# Test URL from thekamababa.com
test_url = "https://www.thekamababa.com/sexy-boobed-indian-village-lady-blowjob-sex/"

print(f"Testing BrowserExtractor with: {test_url}\n")
print("="*60)

try:
    extractor = get_extractor(test_url)
    print(f"[OK] Selected extractor: {extractor.__class__.__name__}")
    
    print("\n[BROWSER] Starting extraction...")
    print("[NOTE] This may take 15-30 seconds...\n")
    
    video_url, title = extractor.extract(test_url)
    
    print("\n" + "="*60)
    print("[SUCCESS] Extraction Complete!")
    print("="*60)
    print(f"Title: {title}")
    print(f"Video URL: {video_url[:100]}...")
    
except Exception as e:
    print("\n" + "="*60)
    print("[FAILED] Extraction failed")
    print("="*60)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
