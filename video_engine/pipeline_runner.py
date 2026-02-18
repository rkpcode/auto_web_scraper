"""
Two-Phase Video Ingestion Pipeline
Phase A: Discovery - Harvester scans pages and seeds database
Phase B: Processing - Workers process PENDING videos concurrently

Compatible with Supabase (PostgreSQL) for persistent state.
"""
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MAX_WORKERS, MIN_FREE_DISK_GB, DEFAULT_MAX_PAGES
from database_supabase import db
from core.logger import logger
from core.downloader import VideoDownloader
from core.uploader import BunnyUploader
from core.utils import cleanup_file, check_disk_space
from extractors import get_extractor
from core.exceptions import (
    PipelineException, ExtractionError, DownloadError, 
    UploadError, DiskSpaceError
)
from harvester import harvest_and_save


def process_video(url):
    """
    Complete workflow for a single video with granular status tracking.
    Includes bulletproof cleanup even on failure.
    
    Args:
        url: Video page URL
    """
    filepath = None
    
    try:
        # 1. Check if already processed
        status = db.get_video_status(url)
        if status == 'COMPLETED':
            logger.info(f"Skipping {url} (already COMPLETED)")
            return
        
        # Insert if new
        if status is None:
            db.insert_video(url)
        
        # 2. Check disk space before proceeding
        if not check_disk_space(MIN_FREE_DISK_GB):
            logger.warning(f"Low disk space, pausing processing for {url}")
            time.sleep(10)  # Wait for uploads to finish
            if not check_disk_space(MIN_FREE_DISK_GB):
                raise DiskSpaceError(f"Insufficient disk space (< {MIN_FREE_DISK_GB}GB)", url=url)
        
        # 3. Extract video URL and title
        db.update_status(url, 'EXTRACTING')
        extractor = get_extractor(url)
        video_url, title = extractor.extract(url)
        
        if not video_url:
            raise ExtractionError("Failed to extract video URL", url=url)
        
        # 4. Download
        db.update_status(url, 'DOWNLOADING')
        downloader = VideoDownloader()
        filename, filepath = downloader.download(video_url, original_page_url=url)
        
        try:
            # 5. Upload to Bunny Stream
            db.update_status(url, 'UPLOADING', local_filename=filename)
            uploader = BunnyUploader()
            
            # Create video object
            video_title = title or filename
            guid = uploader.create_video(video_title)
            
            # Upload binary
            uploader.upload_binary(guid, filepath)
            
            # 6. Mark as completed
            db.update_status(url, 'COMPLETED', bunny_guid=guid)
            logger.info(f"SUCCESS: {url} -> GUID: {guid}")
        
        finally:
            # GUARANTEED cleanup (even if upload fails)
            cleanup_file(filepath)
    
    except PipelineException as e:
        # Already logged by exception __init__
        db.log_error(url, str(e))
        if filepath:
            cleanup_file(filepath)
    
    except Exception as e:
        logger.error(f"FAILED: {url}")
        logger.error(f"   Error: {str(e)}")
        db.log_error(url, str(e))
        
        # Cleanup on failure too
        if filepath:
            cleanup_file(filepath)


def phase_a_discovery(website_url, max_pages=None):
    """
    Phase A: Discovery Phase
    Harvester scans pages and seeds database.
    
    Args:
        website_url: Website to scrape
        max_pages: Maximum pages to crawl (default from config)
    
    Returns:
        dict: Discovery stats
    """
    max_pages = max_pages or DEFAULT_MAX_PAGES
    
    logger.info("=" * 60)
    logger.info("PHASE A: DISCOVERY")
    logger.info("=" * 60)
    logger.info(f"Website: {website_url}")
    logger.info(f"Max Pages: {max_pages}")
    
    # Run harvester
    stats = harvest_and_save(website_url, method='pagination', max_pages=max_pages)
    
    logger.info(f"✅ Found {stats['links_found']} links across {stats['pages_scanned']} pages")
    logger.info(f"✅ Seeding {stats['links_added']} new URLs to database...")
    
    return stats


def phase_b_processing(max_workers=None):
    """
    Phase B: Processing Phase
    Workers process PENDING videos from database.
    
    Args:
        max_workers: Number of concurrent workers (default from config)
    
    Returns:
        dict: Processing stats
    """
    max_workers = max_workers or MAX_WORKERS
    
    logger.info("=" * 60)
    logger.info("PHASE B: PROCESSING")
    logger.info("=" * 60)
    
    # Reset stale statuses from previous crashes
    stale_count = db.reset_stale_statuses()
    if stale_count > 0:
        logger.info(f"♻️  Reset {stale_count} stale videos to PENDING")
    
    # Get pending URLs
    pending_urls = db.get_pending_videos()
    
    if not pending_urls:
        logger.info("No pending URLs to process")
        return {'completed': 0, 'failed': 0}
    
    logger.info(f"Processing {len(pending_urls)} videos with {max_workers} workers")
    
    # Show current stats
    stats = db.get_stats()
    logger.info(f"Current status distribution: {stats}")
    
    # Process videos concurrently
    completed = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(process_video, url): url for url in pending_urls}
        
        # Process results as they complete
        for future in as_completed(futures):
            url = futures[future]
            try:
                future.result()
                completed += 1
            except Exception as e:
                logger.error(f"Unhandled error for {url}: {e}")
                failed += 1
    
    # Final stats
    logger.info("=" * 60)
    logger.info("PROCESSING COMPLETE")
    final_stats = db.get_stats()
    logger.info(f"Final status distribution: {final_stats}")
    logger.info("=" * 60)
    
    return {'completed': completed, 'failed': failed}


def main():
    """
    Interactive two-phase pipeline execution.
    """
    logger.info("=" * 60)
    logger.info("Video Ingestion Pipeline (Two-Phase Model)")
    logger.info("=" * 60)
    
    # Phase A: Discovery
    website_url = input("\n🔍 Enter website URL to scrape: ").strip()
    max_pages = input(f"📄 Max pages to crawl (default={DEFAULT_MAX_PAGES}): ").strip()
    max_pages = int(max_pages) if max_pages else DEFAULT_MAX_PAGES
    
    discovery_stats = phase_a_discovery(website_url, max_pages)
    
    if discovery_stats['links_added'] == 0:
        logger.warning("No new links found. Exiting.")
        return
    
    # Phase B: Processing
    proceed = input(f"\n🚀 Start processing {discovery_stats['links_added']} videos? (y/n): ").strip().lower()
    
    if proceed == 'y':
        processing_stats = phase_b_processing()
        logger.info(f"\n✅ Pipeline complete! Completed: {processing_stats['completed']}, Failed: {processing_stats['failed']}")
    else:
        logger.info("Processing skipped. Run again to process pending videos.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
