"""
Interactive CLI for Video Scraper
User can input website URLs and the system will:
1. Auto-discover video URLs from the website
2. Process and download them
3. Upload to Bunny Stream
"""
import sys
import os

# Add video_engine to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'video_engine'))

from harvester import harvest_and_save
from database import db
from core.logger import logger
import subprocess


def print_banner():
    """Print welcome banner"""
    print("=" * 60)
    print("  VIDEO SCRAPER - Interactive Mode")
    print("=" * 60)
    print()


def get_website_input():
    """Get website URL from user"""
    print("Enter website URL to scrape (or 'quit' to exit):")
    print("Example: https://example.com")
    print()
    
    url = input("> ").strip()
    
    if url.lower() in ['quit', 'exit', 'q']:
        return None
    
    # Basic validation
    if not url.startswith('http'):
        url = 'https://' + url
    
    return url


def get_harvester_options():
    """Get harvester configuration from user"""
    print("\nHarvester Options:")
    print("1. Auto (try sitemap first, then crawl)")
    print("2. Sitemap only")
    print("3. Generic crawl")
    
    choice = input("\nSelect method [1-3] (default: 1): ").strip() or "1"
    
    method_map = {
        "1": "auto",
        "2": "sitemap",
        "3": "generic"
    }
    
    method = method_map.get(choice, "auto")
    
    # Get max pages for generic crawl
    max_pages = 10
    if method in ["auto", "generic"]:
        max_input = input("Max pages to crawl (default: 10): ").strip()
        if max_input.isdigit():
            max_pages = int(max_input)
    
    return method, max_pages


def show_discovered_urls():
    """Show URLs discovered and ask for confirmation"""
    pending = db.get_pending_urls()
    
    if not pending:
        print("\nNo URLs discovered!")
        return False
    
    print(f"\nDiscovered {len(pending)} video URLs:")
    print("-" * 60)
    
    # Show first 5
    for i, url in enumerate(pending[:5], 1):
        print(f"{i}. {url}")
    
    if len(pending) > 5:
        print(f"... and {len(pending) - 5} more")
    
    print("-" * 60)
    
    # Ask for confirmation
    confirm = input("\nProceed with download? [Y/n]: ").strip().lower()
    return confirm != 'n'


def run_pipeline():
    """Run the main pipeline"""
    print("\nStarting pipeline...")
    print("=" * 60)
    
    # Run main.py
    result = subprocess.run(
        [sys.executable, "main.py"],
        cwd=os.path.join(os.path.dirname(__file__), 'video_engine'),
        capture_output=False
    )
    
    print("=" * 60)
    
    if result.returncode == 0:
        print("\nPipeline completed successfully!")
    else:
        print(f"\nPipeline failed with exit code: {result.returncode}")
    
    return result.returncode == 0


def show_stats():
    """Show final statistics"""
    stats = db.get_stats()
    
    print("\nFinal Statistics:")
    print("-" * 60)
    for status, count in stats.items():
        print(f"{status}: {count}")
    print("-" * 60)


def main():
    """Main interactive loop"""
    print_banner()
    
    while True:
        # Get website URL
        website_url = get_website_input()
        
        if website_url is None:
            print("\nExiting...")
            break
        
        print(f"\nTarget: {website_url}")
        
        # Get harvester options
        method, max_pages = get_harvester_options()
        
        print(f"\nMethod: {method}")
        print(f"Max Pages: {max_pages}")
        print("\nStarting URL discovery...")
        print("=" * 60)
        
        # Run harvester
        try:
            new_count = harvest_and_save(
                website_url,
                method=method,
                max_pages=max_pages
            )
            
            print("=" * 60)
            print(f"\nDiscovered {new_count} new URLs")
            
            # Show discovered URLs and ask for confirmation
            if show_discovered_urls():
                # Run pipeline
                success = run_pipeline()
                
                # Show stats
                show_stats()
                
                if success:
                    print("\nAll done! ✓")
            else:
                print("\nSkipped processing.")
        
        except Exception as e:
            print(f"\nError: {e}")
            logger.error(f"Interactive mode error: {e}")
        
        # Ask if user wants to process another website
        print("\n" + "=" * 60)
        another = input("Process another website? [Y/n]: ").strip().lower()
        
        if another == 'n':
            print("\nExiting...")
            break
        
        print("\n" * 2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise
