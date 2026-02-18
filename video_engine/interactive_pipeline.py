"""
Interactive Video Scraper Pipeline
Prompts user for website URL and scraping options before starting.
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
    print("\n" + "=" * 60)
    print("🎬 INTERACTIVE VIDEO SCRAPER PIPELINE")
    print("=" * 60)


def get_user_choice():
    """Get user's choice for input method."""
    print("\n📋 How do you want to provide video URLs?")
    print("1. Enter a website URL (auto-discover videos)")
    print("2. Enter individual video URLs manually")
    print("3. Load from links.txt file")
    
    while True:
        choice = input("\nEnter your choice (1/2/3): ").strip()
        if choice in ['1', '2', '3']:
            return choice
        print("❌ Invalid choice. Please enter 1, 2, or 3.")


def harvest_from_website():
    """Interactive harvester mode."""
    print("\n" + "=" * 60)
    print("🔍 AUTO-DISCOVERY MODE")
    print("=" * 60)
    
    # Get website URL
    website_url = input("\n🌐 Enter website URL (e.g., https://example.com): ").strip()
    
    if not website_url.startswith('http'):
        print("❌ Invalid URL. Must start with http:// or https://")
        return []
    
    # Get method
    print("\n📊 Discovery method:")
    print("1. Auto (try sitemap first, then crawl)")
    print("2. Sitemap only")
    print("3. Generic crawling")
    
    method_choice = input("Enter choice (1/2/3) [default: 1]: ").strip() or '1'
    method_map = {'1': 'auto', '2': 'sitemap', '3': 'generic'}
    method = method_map.get(method_choice, 'auto')
    
    # Get max pages for crawling
    if method in ['auto', 'generic']:
        max_pages_input = input("\n📄 Max pages to crawl [default: 10]: ").strip()
        max_pages = int(max_pages_input) if max_pages_input.isdigit() else 10
        
        # New: Start Page option
        start_page_input = input("⏩ Start from page [default: 1]: ").strip()
        start_page = int(start_page_input) if start_page_input.isdigit() else 1
    else:
        max_pages = 10
        start_page = 1
    
    print(f"\n🚀 Starting discovery from: {website_url}")
    print(f"   Method: {method}")
    print(f"   Start page: {start_page}")
    print(f"   Max pages: {max_pages}")
    
    try:
        new_count = harvest_and_save(website_url, method=method, max_pages=max_pages, start_page=start_page)
        print(f"\n✅ Discovered {new_count} new video URLs")
        return db.get_pending_urls()
    except Exception as e:
        print(f"\n❌ Discovery failed: {e}")
        return []


def manual_url_entry():
    """Manual URL entry mode."""
    print("\n" + "=" * 60)
    print("✍️  MANUAL URL ENTRY")
    print("=" * 60)
    print("\nEnter video URLs (one per line)")
    print("Press Enter twice when done\n")
    
    urls = []
    while True:
        url = input("URL: ").strip()
        if not url:
            if urls:
                break
            else:
                continue
        
        if url.startswith('http'):
            urls.append(url)
            db.insert_video(url)
            print(f"  ✅ Added ({len(urls)} total)")
        else:
            print("  ❌ Invalid URL (must start with http)")
    
    return urls


def load_from_file():
    """Load URLs from links.txt."""
    print("\n📂 Loading from links.txt...")
    
    urls_file = os.path.join(os.path.dirname(__file__), "..", "links.txt")
    
    if not os.path.exists(urls_file):
        print(f"❌ File not found: {urls_file}")
        return []
    
    with open(urls_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    for url in urls:
        db.insert_video(url)
    
    print(f"✅ Loaded {len(urls)} URLs")
    return urls


def confirm_processing(url_count):
    """Ask user to confirm processing."""
    print("\n" + "=" * 60)
    print(f"📊 Ready to process {url_count} video(s)")
    print(f"⚙️  Workers: {MAX_WORKERS}")
    print("=" * 60)
    
    confirm = input("\n🚀 Start processing? (y/n) [default: y]: ").strip().lower()
    return confirm in ['', 'y', 'yes']


def run_pipeline(urls):
    """Run the processing pipeline."""
    print("\n" + "=" * 60)
    print("🎬 STARTING PIPELINE")
    print("=" * 60 + "\n")
    
    logger.info("=" * 60)
    logger.info("Starting Video Ingestion Pipeline (Interactive Mode)")
    logger.info("=" * 60)
    
    # Show current stats
    stats = db.get_stats()
    logger.info(f"Current status distribution: {stats}")
    logger.info(f"Processing {len(urls)} URLs with {MAX_WORKERS} workers")
    
    # Process videos concurrently
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_video, url): url for url in urls}
        
        for future in as_completed(futures):
            url = futures[future]
            try:
                future.result()
            except Exception as e:
                logger.error(f"Unhandled error for {url}: {e}")
    
    # Final stats
    logger.info("=" * 60)
    logger.info("Pipeline Complete")
    final_stats = db.get_stats()
    logger.info(f"Final status distribution: {final_stats}")
    logger.info("=" * 60)
    
    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\n📊 Final Results:")
    for status, count in final_stats.items():
        print(f"   {status:12s}: {count:3d}")
    print()


def main():
    """Main interactive flow."""
    print_banner()
    
    # Initialize database
    db._init_db()
    
    # Reset stale statuses
    stale_count = db.reset_stale_statuses()
    if stale_count > 0:
        print(f"\n🔄 Reset {stale_count} stale statuses from previous run")
    
    # Get user choice
    choice = get_user_choice()
    
    # Get URLs based on choice
    if choice == '1':
        urls = harvest_from_website()
    elif choice == '2':
        urls = manual_url_entry()
    else:
        urls = load_from_file()
    
    if not urls:
        print("\n❌ No URLs to process. Exiting.")
        return
    
    # Confirm and process
    if confirm_processing(len(urls)):
        run_pipeline(urls)
    else:
        print("\n❌ Processing cancelled by user.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
        raise
