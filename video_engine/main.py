"""
Main entry point for the scalable video ingestion pipeline.
Uses ThreadPoolExecutor for concurrent processing with production-grade error handling.
"""
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MAX_WORKERS, MIN_FREE_DISK_GB
from database import db
from core.logger import logger
from core.downloader import VideoDownloader
from core.uploader import BunnyUploader
from core.utils import cleanup_file, check_disk_space
from extractors import get_extractor
from core.exceptions import (
    PipelineException, ExtractionError, DownloadError, 
    UploadError, DiskSpaceError
)


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


def load_urls_from_file(file_path):
    """Load URLs from a text file (one URL per line)."""
    if not os.path.exists(file_path):
        logger.warning(f"URL file not found: {file_path}")
        return []
    
    with open(file_path, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    logger.info(f"Loaded {len(urls)} URLs from {file_path}")
    return urls


def main():
    """
    Main execution function with crash recovery and concurrency.
    """
    logger.info("=" * 60)
    logger.info("Starting Video Ingestion Pipeline")
    logger.info("=" * 60)
    
    # Initialize database
    db._init_db()
    
    # CRITICAL: Reset zombie threads from previous crashes
    stale_count = db.reset_stale_statuses()
    if stale_count > 0:
        logger.info(f"Reset {stale_count} stale statuses to PENDING")
    
    # Get pending/failed URLs from database
    pending_urls = db.get_pending_urls()
    
    if not pending_urls:
        logger.info("No pending URLs in database")
        
        # Optionally load from file if database is empty
        urls_file = os.path.join(os.path.dirname(__file__), "..", "links.txt")
        if os.path.exists(urls_file):
            file_urls = load_urls_from_file(urls_file)
            for url in file_urls:
                db.insert_video(url)
            pending_urls = db.get_pending_urls()
    
    logger.info(f"Processing {len(pending_urls)} URLs with {MAX_WORKERS} workers")
    
    # Show current stats
    stats = db.get_stats()
    logger.info(f"Current status distribution: {stats}")
    
    # Concurrency: Process multiple videos in parallel
    # Note: MAX_WORKERS tuned for I/O bound tasks
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        futures = {executor.submit(process_video, url): url for url in pending_urls}
        
        # Process results as they complete
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


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
