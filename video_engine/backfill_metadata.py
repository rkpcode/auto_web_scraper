import sys
import os
import uuid
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_supabase import db
from core.logger import logger
from extractors import get_extractor
from core.uploader import get_uploader

def sync_video_metadata(url, unique_id, db_title, db_description, seek_id, dood_id, lulu_id):
    """Extracts metadata if needed and syncs it across DB and providers."""
    updates = {}
    
    if not unique_id:
        updates['unique_id'] = uuid.uuid4().hex
        
    title = db_title
    description = db_description
    
    # 1. Force Extract / Re-extract metadata to ensure we have the best SEO version
    try:
        logger.info(f"Extracting metadata for {url}")
        extractor = get_extractor(url)
        _, ext_title, ext_desc = extractor.extract(url)
        
        # Only update if extraction yielded valid data
        if ext_title:
            title = ext_title
            updates['title'] = title
        if ext_desc:
            description = ext_desc
            updates['description'] = description
    except Exception as e:
        logger.error(f"Failed to extract metadata for {url}: {e}")
            
    # 2. Update Database if there's new metadata or UUID
    if updates:
        db.update_status(url, 'COMPLETED', **updates)
        logger.info(f"Updated DB for {url}: {list(updates.keys())}")
        
    # 3. Sync to all 3 platforms
    if title or description:
        video_title = title or "Untitled"
        video_desc = description or ""
        sync_success = False
        
        # Doodstream
        if dood_id:
            try:
                get_uploader('doodstream').set_metadata(dood_id, video_title, video_desc)
                logger.info(f"Synced metadata to Doodstream: {dood_id}")
                sync_success = True
            except Exception as e:
                logger.error(f"Doodstream sync failed for {dood_id}: {e}")
                
        # SeekStreaming
        if seek_id:
            try:
                get_uploader('seekstreaming').set_metadata(seek_id, video_title, video_desc)
                logger.info(f"Synced metadata to SeekStreaming: {seek_id}")
                sync_success = True
            except Exception as e:
                logger.error(f"SeekStreaming sync failed for {seek_id}: {e}")
                
        # LuluStream
        if lulu_id:
            try:
                get_uploader('lulustream').set_metadata(lulu_id, video_title, video_desc)
                logger.info(f"Synced metadata to LuluStream: {lulu_id}")
                sync_success = True
            except Exception as e:
                logger.error(f"LuluStream sync failed for {lulu_id}: {e}")
                
        # If successfully synced to at least one platform (or attempted all), mark as synced
        if sync_success or (not dood_id and not seek_id and not lulu_id):
            db.update_status(url, 'COMPLETED', metadata_synced=True)
                
    return True

def main():
    logger.info("=" * 60)
    logger.info("Starting Backfill & Sync of Metadata to 3 Providers")
    logger.info("=" * 60)
    
    videos_to_process = []
    
    with db.get_cursor() as cursor:
        cursor.execute("""
            SELECT original_url, unique_id, title, description, seekstreaming_id, doodstream_id, lulustream_id
            FROM videos
            WHERE status = 'COMPLETED' AND (metadata_synced IS NULL OR metadata_synced = FALSE)
        """)
        
        for row in cursor.fetchall():
            url = row[0]
            unique_id = row[1]
            title = row[2]
            description = row[3]
            seek_id = row[4]
            dood_id = row[5]
            lulu_id = row[6]
            
            videos_to_process.append((url, unique_id, title, description, seek_id, dood_id, lulu_id))
            
    logger.info(f"Found {len(videos_to_process)} completed videos to sync.")
    
    success_count = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(sync_video_metadata, url, unique_id, title, desc, seek_id, dood_id, lulu_id): url 
            for url, unique_id, title, desc, seek_id, dood_id, lulu_id in videos_to_process
        }
        
        for future in as_completed(futures):
            url = futures[future]
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                logger.error(f"Unhandled error for {url}: {e}")
                
    logger.info("=" * 60)
    logger.info(f"Sync Complete. Successfully processed {success_count}/{len(videos_to_process)} videos.")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
