"""
Quick test of harvester functionality.
"""
import sys
sys.path.insert(0, '.')

from harvester import GenericHarvester, SitemapHarvester

# Test URL - YouTube (has sitemap)
test_url = "https://www.youtube.com/feed/trending"

print("="*60)
print("Testing Harvester Module")
print("="*60)
print(f"Target: {test_url}\n")

# Test 1: Sitemap Harvester
print("[1/2] Testing SitemapHarvester...")
try:
    sitemap_harvester = SitemapHarvester(test_url)
    urls = sitemap_harvester.discover()
    print(f"  Found {len(urls)} URLs via sitemap")
except Exception as e:
    print(f"  Sitemap failed (expected): {e}")

# Test 2: Generic Harvester (limited crawl)
print("\n[2/2] Testing GenericHarvester...")
try:
    generic_harvester = GenericHarvester(test_url)
    urls = generic_harvester.discover(max_pages=2)
    print(f"  Found {len(urls)} URLs via generic crawl")
    
    if urls:
        print(f"\n  Sample URLs:")
        for url in list(urls)[:5]:
            print(f"    - {url}")
except Exception as e:
    print(f"  Generic failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Harvester test complete!")
print("="*60)
