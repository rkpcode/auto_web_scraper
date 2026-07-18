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
import uuid

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MAX_WORKERS, MIN_FREE_DISK_GB, DEFAULT_MAX_PAGES
from database_supabase import db
from core.logger import logger
from core.downloader import VideoDownloader
from core.uploader import get_uploader
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
    current_provider = None
    
    try:
        # 1. Check if already processed or stop requested
        import config
        if getattr(config, "STOP_PROCESSING", False):
            logger.info(f"Stop requested. Skipping {url}")
            return
            
        current_provider = config.UPLOAD_PROVIDER
        
        # Get all upload details to support simultaneous multi-provider uploads
        upload_details = db.get_all_upload_ids(url) or {}
        providers_to_upload = ['doodstream', 'seekstreaming', 'lulustream']
        
        # Check how many providers are already uploaded
        completed_providers = 0
        for provider in providers_to_upload:
            prov_col = f"{provider}_id"
            if upload_details.get(prov_col):
                completed_providers += 1
                
        # If all platforms have an ID, mark COMPLETED and skip
        if completed_providers == len(providers_to_upload):
            logger.info(f"Skipping {url} (already fully COMPLETED across all {len(providers_to_upload)} platforms)")
            db.update_status(url, 'COMPLETED')
            return
            
        logger.info(f"Processing {url} ({completed_providers}/{len(providers_to_upload)} platforms complete)")
        
        unique_id = str(uuid.uuid4())
        
        if not upload_details:
            db.insert_video(url)
        
        # 2. Check disk space before proceeding
        if not check_disk_space(MIN_FREE_DISK_GB):
            logger.warning(f"Low disk space, pausing processing for {url}")
            time.sleep(10)  # Wait for uploads to finish
            if not check_disk_space(MIN_FREE_DISK_GB):
                raise DiskSpaceError(f"Insufficient disk space (< {MIN_FREE_DISK_GB}GB)", url=url)
        
        # 3. Extract video URL, title, and description
        db.update_status(url, 'EXTRACTING')
        extractor = get_extractor(url)
        video_url, title, description = extractor.extract(url)
        
        if not video_url:
            raise ExtractionError("Failed to extract video URL", url=url)
            
        from core.utils import clean_metadata
        title, description = clean_metadata(title, description)
            
        # Assign unique_id if not already assigned, save title/desc
        db.update_status(url, 'EXTRACTING', title=title, description=description)
        # We also want to save unique_id, let's do it safely (only if it doesn't have one).
        # We will just unconditionally set it if we want, or fetch it. Since `url` is UNIQUE, we can set unique_id.
        # But wait, it's safer to only set unique_id if it's a new scrape. Let's just update it here.
        db.update_status(url, 'EXTRACTING', unique_id=unique_id)
        
        # 4. Download
        db.update_status(url, 'DOWNLOADING')
        downloader = VideoDownloader()
        filename, filepath = downloader.download(video_url, original_page_url=url)
        
        # Validate video file before uploading
        from core.utils import validate_video_file
        validate_video_file(filepath)
        
        try:
            # 5. Upload to all configured providers sequentially
            success_count = 0
            provider_ids = {}
            
            # Get fresh upload details at start
            upload_details = db.get_all_upload_ids(url) or {}
            
            for provider in providers_to_upload:
                # Check if already uploaded to this provider (refresh from DB each iteration for safety)
                prov_col = f"{provider}_id"
                
                # Re-fetch to handle concurrent runs or previous iterations in this same run
                current_details = db.get_all_upload_ids(url) or {}
                if current_details.get(prov_col):
                    logger.info(f"Skipping {url} for {provider} (already COMPLETED with ID: {current_details[prov_col]})")
                    provider_ids[provider] = current_details[prov_col]
                    success_count += 1
                    continue
                    
                logger.info(f"Uploading {url} to {provider}...")
                db.update_status(url, 'UPLOADING', local_filename=filename, upload_provider=provider)
                
                try:
                    uploader = get_uploader(provider=provider)
                    video_title = title or filename
                    upload_id = uploader.upload(video_title, filepath, description=description)
                    
                    # IMMEDIATELY save this provider's ID to database so it's not lost on partial failure
                    db.update_status(url, 'UPLOADING', **{prov_col: upload_id}, local_filename=filename, upload_provider=provider)
                    
                    provider_ids[provider] = upload_id
                    logger.info(f"SUCCESS: {url} -> {provider.upper()} ID: {upload_id}")
                    success_count += 1
                except Exception as upload_err:
                    logger.error(f"FAILED to upload to {provider}: {str(upload_err)}")
                    db.log_error(url, f"Upload to {provider} failed: {str(upload_err)}", provider=provider)
                    # We continue to the next provider instead of failing the whole process
            
            # 6. Final Status Evaluation
            if success_count == len(providers_to_upload):
                db.save_successful_upload(
                    url=url,
                    title=title,
                    seek_id=provider_ids.get('seekstreaming'),
                    dood_id=provider_ids.get('doodstream'),
                    lulu_id=provider_ids.get('lulustream')
                )
                logger.info(f"✅ FULLY COMPLETED: {url} across all platforms")
            else:
                db.update_status(url, 'PENDING')
                logger.warning(f"⚠️ PARTIAL SUCCESS: {url} ({success_count}/{len(providers_to_upload)}). Returning to PENDING.")
        
        finally:
            # GUARANTEED cleanup (even if upload fails)
            cleanup_file(filepath)
    
    except PipelineException as e:
        # Already logged by exception __init__
        db.log_error(url, str(e), provider=current_provider)
        if filepath:
            cleanup_file(filepath)
    
    except Exception as e:
        logger.error(f"FAILED: {url}")
        logger.error(f"   Error: {str(e)}")
        db.log_error(url, str(e), provider=current_provider)
        
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
    
    # Get pending URLs (we pass None to get all pending since we're doing multi-provider)
    import config
    pending_urls = db.get_pending_videos(current_provider=None)
    
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
