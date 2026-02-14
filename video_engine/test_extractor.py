"""
Quick test script for ViralkandExtractor.
Tests extraction from thekamababa.com sample URL.
"""
import sys
sys.path.insert(0, '.')

from extractors import get_extractor

# Test URL from kb_links.txt
test_url = "https://www.thekamababa.com/sexy-boobed-indian-village-lady-blowjob-sex/"

print(f"Testing extraction from: {test_url}\n")

try:
    extractor = get_extractor(test_url)
    print(f"[OK] Selected extractor: {extractor.__class__.__name__}")
    
    video_url, title = extractor.extract(test_url)
    
    print(f"\n[TITLE] {title}")
    print(f"[VIDEO] {video_url[:80]}...")
    print(f"\n[SUCCESS] Extraction successful!")
    
except Exception as e:
    print(f"\n[FAILED] Extraction failed: {e}")
    import traceback
    traceback.print_exc()
