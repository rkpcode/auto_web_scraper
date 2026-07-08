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
from core.exceptions import ExtractionError

def backfill_video(url, needs_uuid, needs_metadata):
    updates = {}
    
    if needs_uuid:
        updates['unique_id'] = uuid.uuid4().hex
        
    if needs_metadata:
        try:
            logger.info(f"Extracting metadata for {url}")
            extractor = get_extractor(url)
            # The extractors return 3 values
            _, title, description = extractor.extract(url)
            updates['title'] = title
            updates['description'] = description
        except Exception as e:
            logger.error(f"Failed to extract metadata for {url}: {e}")
            
    if updates:
        # Since the status is already COMPLETED, we preserve it
        db.update_status(url, 'COMPLETED', **updates)
        logger.info(f"Updated {url}: {list(updates.keys())}")
        return True
    return False

def main():
    logger.info("=" * 60)
    logger.info("Starting Backfill of Metadata and Unique IDs")
    logger.info("=" * 60)
    
    # We query videos directly using db.get_cursor
    videos_to_process = []
    
    with db.get_cursor() as cursor:
        cursor.execute("""
            SELECT original_url, unique_id, title, description, status 
            FROM videos
            WHERE status = 'COMPLETED' AND 
                  (unique_id IS NULL OR title IS NULL OR description IS NULL)
        """)
        
        for row in cursor.fetchall():
            url = row[0]
            unique_id = row[1]
            title = row[2]
            description = row[3]
            
            needs_uuid = unique_id is None
            needs_metadata = title is None or description is None
            
            videos_to_process.append((url, needs_uuid, needs_metadata))
            
    logger.info(f"Found {len(videos_to_process)} completed videos needing updates.")
    
    # Process them concurrently
    success_count = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(backfill_video, url, needs_uuid, needs_meta): url for url, needs_uuid, needs_meta in videos_to_process}
        
        for future in as_completed(futures):
            url = futures[future]
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                logger.error(f"Unhandled error for {url}: {e}")
                
    logger.info("=" * 60)
    logger.info(f"Backfill Complete. Successfully updated {success_count}/{len(videos_to_process)} videos.")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
