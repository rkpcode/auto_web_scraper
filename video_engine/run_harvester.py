"""
CLI tool for running the harvester.
Usage: python run_harvester.py <website_url> [options]
"""
import sys
import argparse
from harvester import harvest_and_save
from core.logger import logger


def main():
    parser = argparse.ArgumentParser(
        description='Harvest video URLs from a website and add to database'
    )
    
    parser.add_argument(
        'url',
        help='Website homepage URL (e.g., https://example.com)'
    )
    
    parser.add_argument(
        '--method',
        choices=['auto', 'sitemap', 'generic'],
        default='auto',
        help='Harvesting method (default: auto - tries sitemap first)'
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=10,
        help='Maximum pages to crawl for generic method (default: 10)'
    )
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("HARVESTER - Auto URL Discovery")
    logger.info("="*60)
    logger.info(f"Target: {args.url}")
    logger.info(f"Method: {args.method}")
    logger.info(f"Max Pages: {args.max_pages}")
    logger.info("="*60)
    
    try:
        new_count = harvest_and_save(
            args.url,
            method=args.method,
            max_pages=args.max_pages
        )
        
        print("\n" + "="*60)
        print(f"✅ SUCCESS: Added {new_count} new video URLs to database")
        print("="*60)
        print("\nNext steps:")
        print("1. Review URLs: python -c 'from database import db; print(db.get_pending_urls())'")
        print("2. Start pipeline: python main.py")
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        logger.error(f"Harvester failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
