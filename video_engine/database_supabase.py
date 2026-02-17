"""
Supabase (PostgreSQL) Database Manager
Replaces SQLite with enterprise-grade PostgreSQL for persistent state across HF Spaces restarts.

CRITICAL: Uses context managers to prevent "Too many clients" error.
"""
import psycopg2
from psycopg2 import sql, errors
from contextlib import contextmanager
from datetime import datetime
import os
from core.logger import logger


class SupabaseManager:
    """
    Thread-safe PostgreSQL database manager with connection leak prevention.
    
    Key Features:
    - Context manager pattern to guarantee connection closure
    - INSERT ... ON CONFLICT for deduplication
    - Optimized for Supabase free tier connection limits
    """
    
    def __init__(self, database_url=None):
        """
        Initialize Supabase connection manager.
        
        Args:
            database_url: PostgreSQL connection string from Supabase
                         Format: postgresql://user:pass@host:port/dbname
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL environment variable must be set. "
                "Get it from Supabase: Settings > Database > Connection String (URI)"
            )
        
        # Test connection on init
        self._init_db()
        logger.info("✅ Supabase connection established")
    
    @contextmanager
    def get_cursor(self):
        """
        Context manager for database operations.
        ALWAYS use this to prevent connection leaks.
        
        Usage:
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM videos")
                results = cursor.fetchall()
        
        The connection is automatically committed and closed.
        """
        conn = None
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _init_db(self):
        """
        Create videos table with UNIQUE constraint on original_url.
        Idempotent - safe to run multiple times.
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id SERIAL PRIMARY KEY,
                    original_url TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    bunny_guid TEXT,
                    local_filename TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
            
            # Create indexes for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON videos(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON videos(created_at)
            """)
    
    def bulk_seed_links(self, links, status='PENDING'):
        """
        Bulk insert URLs with automatic deduplication using ON CONFLICT.
        
        Args:
            links: List or set of URLs to insert
            status: Initial status (default: PENDING)
        
        Returns:
            int: Number of NEW URLs inserted (duplicates are ignored)
        
        Example:
            count = db.bulk_seed_links(['url1', 'url2', 'url1'])
            # Returns: 2 (url1 deduplicated)
        """
        if not links:
            logger.warning("bulk_seed_links called with empty list")
            return 0
        
        links_list = list(set(links))  # Deduplicate in Python first
        logger.info(f"[SUPABASE] Inserting {len(links_list)} URLs (batch mode)...")
        
        with self.get_cursor() as cursor:
            # Use executemany for batch insert
            # ON CONFLICT ensures duplicates are silently ignored
            insert_query = """
                INSERT INTO videos (original_url, status, created_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (original_url) DO NOTHING
            """
            
            data = [(url, status) for url in links_list]
            cursor.executemany(insert_query, data)
            
            # rowcount gives number of inserted rows (excluding duplicates)
            inserted_count = cursor.rowcount
        
        logger.info(f"[SUPABASE] Successfully added {inserted_count} new URLs (skipped {len(links_list) - inserted_count} duplicates)")
        logger.info(f"[SUPABASE] Successfully added {inserted_count} new URLs (skipped {len(links_list) - inserted_count} duplicates)")
        return inserted_count
    
    def insert_videos_batch(self, links, status='PENDING'):
        """
        Alias for bulk_seed_links to maintain compatibility with Harvester.
        """
        return self.bulk_seed_links(links, status)
    
    def get_pending_videos(self):
        """
        Get all URLs with status PENDING or FAILED for processing.
        
        Returns:
            list: URLs to process
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT original_url 
                FROM videos 
                WHERE status IN ('PENDING', 'FAILED')
                ORDER BY created_at ASC
            """)
            urls = [row[0] for row in cursor.fetchall()]
        
        return urls
    
    def get_video_status(self, url):
        """
        Check processing status of a specific video.
        
        Args:
            url: Video page URL
        
        Returns:
            str: Status or None if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT status FROM videos WHERE original_url = %s",
                (url,)
            )
            result = cursor.fetchone()
        
        return result[0] if result else None
    
    def insert_video(self, url, status='PENDING'):
        """
        Insert a single video record.
        
        Args:
            url: Video page URL
            status: Initial status
        
        Returns:
            bool: True if inserted, False if duplicate
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO videos (original_url, status, created_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                """, (url, status))
            return True
        except errors.UniqueViolation:
            # Duplicate URL - already exists
            logger.debug(f"Skipping duplicate URL: {url}")
            return False
    
    def update_status(self, url, status, **kwargs):
        """
        Thread-safe status update with dynamic kwargs.
        
        Args:
            url: Video page URL
            status: New status
            **kwargs: Additional fields to update (bunny_guid, local_filename, etc.)
        
        Example:
            db.update_status(url, 'COMPLETED', bunny_guid='xxx', local_filename='yyy')
        """
        with self.get_cursor() as cursor:
            # Build dynamic UPDATE query
            set_clauses = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
            params = [status]
            
            for key, value in kwargs.items():
                set_clauses.append(f"{key} = %s")
                params.append(value)
            
            query = f"UPDATE videos SET {', '.join(set_clauses)} WHERE original_url = %s"
            params.append(url)
            
            cursor.execute(query, params)
    
    def log_error(self, url, error_msg):
        """
        Mark video as FAILED with error details.
        
        Args:
            url: Video page URL
            error_msg: Error message to store
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE videos 
                SET status = 'FAILED', 
                    error_message = %s, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE original_url = %s
            """, (error_msg, url))
    
    def reset_stale_statuses(self):
        """
        Reset zombie threads from previous crashes.
        DOWNLOADING/UPLOADING/EXTRACTING → PENDING
        
        Call this on app startup to recover from HF Space restarts.
        
        Returns:
            int: Number of videos reset
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE videos 
                SET status = 'PENDING', 
                    updated_at = CURRENT_TIMESTAMP
                WHERE status IN ('DOWNLOADING', 'UPLOADING', 'EXTRACTING')
            """)
            affected = cursor.rowcount
        
        if affected > 0:
            logger.info(f"♻️  Reset {affected} stale videos to PENDING")
        
        return affected
    
    def get_stats(self):
        """
        Get status distribution for monitoring dashboard.
        
        Returns:
            dict: Status counts (e.g., {'PENDING': 45, 'COMPLETED': 12})
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM videos 
                GROUP BY status
            """)
            stats = dict(cursor.fetchall())
        
        return stats
    
    def get_total_count(self):
        """Get total number of videos in database."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM videos")
            return cursor.fetchone()[0]


# Singleton instance
db = SupabaseManager()
