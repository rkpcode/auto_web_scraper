"""
Colab Interactive Pipeline
User-friendly interface for Google Colab with input widgets
Discovers videos from website, downloads, and uploads to Bunny Stream
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MAX_WORKERS
from database import db
from core.logger import logger
from harvester import harvest_and_save
from main import process_video
from concurrent.futures import ThreadPoolExecutor, as_completed


def print_banner():
    """Print welcome banner."""
    print("\n" + "=" * 70)
    print("COLAB INTERACTIVE VIDEO SCRAPER PIPELINE")
    print("=" * 70)


def get_website_input():
    """Get website URL from user in Colab."""
    print("\n[*] WEBSITE VIDEO DISCOVERY")
    print("-" * 70)
    print("Enter a website URL to automatically discover and download videos")
    print("Example: https://viralkand.com or https://example.com")
    print("-" * 70)
    
    website_url = input("\n[>] Enter website URL: ").strip()
    
    if not website_url:
        print("[X] No URL provided. Exiting.")
        return None
    
    if not website_url.startswith('http'):
        print("[X] Invalid URL. Must start with http:// or https://")
        return None
    
    return website_url


def get_discovery_options():
    """Get discovery method and options."""
    print("\n[*] Discovery Options:")
    print("1. Auto (try sitemap first, then crawl)")
    print("2. Sitemap only")
    print("3. Generic crawling")
    
    method_choice = input("\nEnter choice (1/2/3) [default: 1]: ").strip() or '1'
    method_map = {'1': 'auto', '2': 'sitemap', '3': 'generic'}
    method = method_map.get(method_choice, 'auto')
    
    # Get max pages for crawling
    if method in ['auto', 'generic']:
        max_pages_input = input("[>] Max pages to crawl [default: 10]: ").strip()
        max_pages = int(max_pages_input) if max_pages_input.isdigit() else 10
    else:
        max_pages = 10
    
    return method, max_pages


def discover_videos(website_url, method='auto', max_pages=10):
    """Discover videos from website and save to database."""
    print("\n" + "=" * 70)
    print("🔍 DISCOVERING VIDEOS")
    print("=" * 70)
    print(f"🌐 Website: {website_url}")
    print(f"📊 Method: {method}")
    print(f"📄 Max pages: {max_pages}")
    print("-" * 70)
    
    try:
        new_count = harvest_and_save(website_url, method=method, max_pages=max_pages)
        print(f"\n✅ Discovered {new_count} new video URLs")
        return new_count
    except Exception as e:
        print(f"\n❌ Discovery failed: {e}")
        logger.error(f"Discovery failed for {website_url}: {e}")
        return 0


def show_stats():
    """Show current database statistics."""
    stats = db.get_stats()
    if stats:
        print("\n📊 Current Database Status:")
        print("-" * 70)
        for status, count in stats.items():
            print(f"   {status:12s}: {count:3d}")
        print("-" * 70)
    return stats


def confirm_processing(url_count):
    """Ask user to confirm processing."""
    print("\n" + "=" * 70)
    print(f"📊 Ready to process {url_count} video(s)")
    print(f"⚙️  Workers: {MAX_WORKERS}")
    print(f"🎯 Action: Download → Upload to Bunny Stream")
    print("=" * 70)
    
    confirm = input("\n🚀 Start processing? (y/n) [default: y]: ").strip().lower()
    return confirm in ['', 'y', 'yes']


def process_videos(urls):
    """Process all discovered videos."""
    print("\n" + "=" * 70)
    print("🎬 STARTING VIDEO PROCESSING")
    print("=" * 70)
    
    logger.info("=" * 60)
    logger.info("Starting Video Processing (Colab Interactive Mode)")
    logger.info("=" * 60)
    logger.info(f"Processing {len(urls)} URLs with {MAX_WORKERS} workers")
    
    # Process videos concurrently
    completed = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_video, url): url for url in urls}
        
        for i, future in enumerate(as_completed(futures), 1):
            url = futures[future]
            try:
                future.result()
                completed += 1
                print(f"✅ [{i}/{len(urls)}] Processed successfully")
            except Exception as e:
                failed += 1
                print(f"❌ [{i}/{len(urls)}] Failed: {str(e)[:50]}")
                logger.error(f"Unhandled error for {url}: {e}")
    
    # Final stats
    logger.info("=" * 60)
    logger.info("Pipeline Complete")
    final_stats = db.get_stats()
    logger.info(f"Final status distribution: {final_stats}")
    logger.info("=" * 60)
    
    print("\n" + "=" * 70)
    print("✅ PIPELINE COMPLETE")
    print("=" * 70)
    print(f"\n📊 Final Results:")
    for status, count in final_stats.items():
        print(f"   {status:12s}: {count:3d}")
    print()


def main():
    """Main interactive flow for Colab."""
    print_banner()
    
    # Initialize database
    db._init_db()
    
    # Reset stale statuses
    stale_count = db.reset_stale_statuses()
    if stale_count > 0:
        print(f"\n🔄 Reset {stale_count} stale statuses from previous run")
    
    # Show current stats
    show_stats()
    
    # Get website URL from user
    website_url = get_website_input()
    if not website_url:
        return
    
    # Get discovery options
    method, max_pages = get_discovery_options()
    
    # Discover videos
    new_count = discover_videos(website_url, method, max_pages)
    
    if new_count == 0:
        print("\n⚠️  No new videos discovered.")
        
        # Check if there are pending videos in database
        pending_urls = db.get_pending_urls()
        if pending_urls:
            print(f"\n💡 Found {len(pending_urls)} pending videos in database.")
            process_existing = input("Process existing pending videos? (y/n) [default: n]: ").strip().lower()
            if process_existing == 'y':
                if confirm_processing(len(pending_urls)):
                    process_videos(pending_urls)
        else:
            print("\n❌ No videos to process. Exiting.")
        return
    
    # Get pending URLs
    pending_urls = db.get_pending_urls()
    
    if not pending_urls:
        print("\n❌ No pending URLs found. Exiting.")
        return
    
    # Confirm and process
    if confirm_processing(len(pending_urls)):
        process_videos(pending_urls)
    else:
        print("\n❌ Processing cancelled by user.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user")
        logger.info("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
