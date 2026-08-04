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
        
        # SeekStreaming is the primary compulsory provider, followed by backup hosts
        providers_to_upload = ['seekstreaming', 'doodstream', 'lulustream']
        
        # Check if SeekStreaming is already uploaded
        seek_id = upload_details.get('seekstreaming_id')
        if seek_id:
            logger.info(f"Skipping {url} (already COMPLETED on SeekStreaming: {seek_id})")
            db.update_status(url, 'COMPLETED')
            return
            
        logger.info(f"Processing {url} for primary upload to SeekStreaming...")
        
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
        db.update_status(url, 'EXTRACTING', title=title, description=description, unique_id=unique_id)
        
        # 4. Download
        db.update_status(url, 'DOWNLOADING')
        downloader = VideoDownloader()
        filename, filepath = downloader.download(video_url, original_page_url=url)
        
        # Validate video file before uploading
        from core.utils import validate_video_file
        validate_video_file(filepath)
        
        try:
            # 5. Upload to SeekStreaming (Primary) first, then backup hosts
            success_count = 0
            provider_ids = {}
            
            for provider in providers_to_upload:
                prov_col = f"{provider}_id"
                
                # Re-fetch to handle concurrent runs or previous iterations
                current_details = db.get_all_upload_ids(url) or {}
                if current_details.get(prov_col):
                    logger.info(f"Skipping {url} for {provider} (already uploaded with ID: {current_details[prov_col]})")
                    provider_ids[provider] = current_details[prov_col]
                    success_count += 1
                    continue
                    
                logger.info(f"Uploading {url} to {provider}...")
                db.update_status(url, 'UPLOADING', local_filename=filename, upload_provider=provider)
                
                try:
                    uploader = get_uploader(provider=provider)
                    video_title = title or filename
                    upload_id = uploader.upload(video_title, filepath, description=description)
                    
                    # Save this provider's ID to database immediately
                    db.update_status(url, 'UPLOADING', **{prov_col: upload_id}, local_filename=filename, upload_provider=provider)
                    
                    provider_ids[provider] = upload_id
                    logger.info(f"SUCCESS: {url} -> {provider.upper()} ID: {upload_id}")
                    success_count += 1
                except Exception as upload_err:
                    logger.error(f"FAILED to upload to {provider}: {str(upload_err)}")
                    if provider == 'seekstreaming':
                        # SeekStreaming is compulsory, re-raise error to handle status in outer except/evaluation
                        raise upload_err
                    else:
                        # Backup providers (doodstream/lulustream) failures are logged as warnings
                        db.log_error(url, f"Backup upload to {provider} failed: {str(upload_err)}", provider=provider)
            
            # 6. Final Status Evaluation
            current_details = db.get_all_upload_ids(url) or {}
            seek_upload_id = provider_ids.get('seekstreaming') or current_details.get('seekstreaming_id')
            
            if seek_upload_id:
                db.save_successful_upload(
                    url=url,
                    title=title,
                    seek_id=seek_upload_id,
                    dood_id=provider_ids.get('doodstream') or current_details.get('doodstream_id'),
                    lulu_id=provider_ids.get('lulustream') or current_details.get('lulustream_id')
                )
                logger.info(f"✅ COMPLETED on SeekStreaming: {url} ({success_count}/{len(providers_to_upload)} platforms complete)")
            else:
                db.update_status(url, 'PENDING')
                logger.warning(f"⚠️ SeekStreaming upload missing for {url}. Status set to PENDING.")
        
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


def process_backup_video(url):
    """
    Backup upload workflow: Downloads video and uploads ONLY to missing backup platforms (DoodStream, LuluStream)
    for videos that are already COMPLETED on SeekStreaming.
    """
    filepath = None
    try:
        import config
        if getattr(config, "STOP_PROCESSING", False):
            logger.info(f"Stop requested. Skipping backup for {url}")
            return

        upload_details = db.get_all_upload_ids(url) or {}
        missing_providers = []
        if not upload_details.get('doodstream_id'):
            missing_providers.append('doodstream')
        if not upload_details.get('lulustream_id'):
            missing_providers.append('lulustream')

        if not missing_providers:
            logger.info(f"Skipping backup for {url} (already uploaded to all backup hosts)")
            return

        logger.info(f"Processing backup uploads for {url} -> missing hosts: {missing_providers}")

        if not check_disk_space(MIN_FREE_DISK_GB):
            logger.warning(f"Low disk space, pausing backup processing for {url}")
            time.sleep(10)
            if not check_disk_space(MIN_FREE_DISK_GB):
                raise DiskSpaceError(f"Insufficient disk space (< {MIN_FREE_DISK_GB}GB)", url=url)

        extractor = get_extractor(url)
        video_url, title, description = extractor.extract(url)

        if not video_url:
            raise ExtractionError("Failed to extract video URL for backup upload", url=url)

        from core.utils import clean_metadata
        title, description = clean_metadata(title, description)

        downloader = VideoDownloader()
        filename, filepath = downloader.download(video_url, original_page_url=url)

        from core.utils import validate_video_file
        validate_video_file(filepath)

        try:
            for provider in missing_providers:
                logger.info(f"Uploading backup {url} to {provider}...")
                uploader = get_uploader(provider=provider)
                video_title = title or filename
                upload_id = uploader.upload(video_title, filepath, description=description)

                prov_col = f"{provider}_id"
                db.update_status(url, 'COMPLETED', **{prov_col: upload_id})
                logger.info(f"✅ BACKUP SUCCESS: {url} -> {provider.upper()} ID: {upload_id}")
        finally:
            cleanup_file(filepath)

    except Exception as e:
        logger.error(f"Backup processing failed for {url}: {e}")
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
