"""
Supabase (PostgreSQL) Database Manager
Replaces SQLite with enterprise-grade PostgreSQL for persistent state across HF Spaces restarts.

CRITICAL: Uses context managers to prevent "Too many clients" error.
"""
import psycopg2
from psycopg2 import sql, errors
from psycopg2.extras import execute_values
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
        logger.info("[OK] Supabase connection established")
    
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
                    upload_provider TEXT,
                    upload_id TEXT,
                    local_filename TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
            
            # Perform PostgreSQL migration to add columns if they do not exist
            cursor.execute("""
                ALTER TABLE videos 
                ADD COLUMN IF NOT EXISTS upload_provider TEXT,
                ADD COLUMN IF NOT EXISTS upload_id TEXT,
                ADD COLUMN IF NOT EXISTS doodstream_id TEXT,
                ADD COLUMN IF NOT EXISTS seekstreaming_id TEXT,
                ADD COLUMN IF NOT EXISTS lulustream_id TEXT
            """)
            
            # Create indexes for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON videos(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON videos(created_at)
            """)
            
            # Migrate any old streamwish entries to seekstreaming
            cursor.execute("""
                UPDATE videos 
                SET upload_provider = 'seekstreaming' 
                WHERE upload_provider = 'streamwish'
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
        
        try:
            with self.get_cursor() as cursor:
                # Use execute_values with RETURNING for accurate insert count
                # NOTE: executemany + ON CONFLICT DO NOTHING gives wrong rowcount
                insert_query = """
                    INSERT INTO videos (original_url, status, created_at)
                    VALUES %s
                    ON CONFLICT (original_url) DO NOTHING
                """
                
                data = [(url, status) for url in links_list]
                logger.debug(f"[SUPABASE] Executing batch insert for {len(data)} items...")
                execute_values(
                    cursor, 
                    insert_query,
                    data,
                    template="(%s, %s, CURRENT_TIMESTAMP)",
                    page_size=100
                )
                logger.debug("[SUPABASE] Batch insert execution complete.")
                
                # rowcount is accurate with execute_values
                inserted_count = cursor.rowcount
                logger.debug(f"[SUPABASE] Row count: {inserted_count}")
            
            logger.info(f"[SUPABASE] Successfully added {inserted_count} new URLs (skipped {len(links_list) - inserted_count} duplicates)")
            return inserted_count
            
        except Exception as e:
            logger.error(f"[SUPABASE] Error in bulk_seed_links: {e}")
            return 0
    
    def insert_videos_batch(self, links, status='PENDING'):
        """
        Alias for bulk_seed_links to maintain compatibility with Harvester.
        """
        return self.bulk_seed_links(links, status)
    
    def get_pending_videos(self, current_provider=None):
        """
        Get all URLs with status PENDING, FAILED, or COMPLETED where the specific provider's column is null.
        
        Args:
            current_provider (str, optional): The currently selected upload provider.
            
        Returns:
            list: URLs to process
        """
        with self.get_cursor() as cursor:
            if current_provider:
                provider = current_provider.strip().lower()
                prov_col = {
                    'doodstream': 'doodstream_id',
                    'seekstreaming': 'seekstreaming_id',
                    'lulustream': 'lulustream_id',
                    'bunny': 'bunny_guid'
                }.get(provider)
                
                if prov_col:
                    query = f"""
                        SELECT original_url 
                        FROM videos 
                        WHERE status IN ('PENDING', 'FAILED')
                           OR (status = 'COMPLETED' AND {prov_col} IS NULL)
                        ORDER BY created_at ASC
                    """
                    cursor.execute(query)
                else:
                    cursor.execute("""
                        SELECT original_url 
                        FROM videos 
                        WHERE status IN ('PENDING', 'FAILED')
                           OR (status = 'COMPLETED' AND (upload_provider IS NULL OR upload_provider != %s))
                        ORDER BY created_at ASC
                    """, (provider,))
            else:
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

    def get_video_details(self, url):
        """
        Get status and upload_provider of a specific video.
        
        Args:
            url: Video page URL
            
        Returns:
            tuple: (status, upload_provider) or None if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT status, upload_provider FROM videos WHERE original_url = %s",
                (url,)
            )
            result = cursor.fetchone()
        
        return result if result else None

    def get_all_upload_ids(self, url):
        """
        Get status and all upload details of a specific video to support side-by-side storage.
        
        Args:
            url: Video page URL
            
        Returns:
            dict: {status, upload_provider, upload_id, doodstream_id, seekstreaming_id, lulustream_id, bunny_guid} or None if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT status, upload_provider, upload_id, doodstream_id, seekstreaming_id, lulustream_id, bunny_guid 
                FROM videos 
                WHERE original_url = %s
            """, (url,))
            row = cursor.fetchone()
            
        if not row:
            return None
            
        return {
            'status': row[0],
            'upload_provider': row[1],
            'upload_id': row[2],
            'doodstream_id': row[3],
            'seekstreaming_id': row[4],
            'lulustream_id': row[5],
            'bunny_guid': row[6]
        }

    def clean_failed_videos(self):
        """
        Delete all videos with status 'FAILED' from the database.
        
        Returns:
            int: Number of deleted entries
        """
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM videos WHERE status = 'FAILED'")
            affected = cursor.rowcount
        
        if affected > 0:
            logger.info(f"[MAINTENANCE] Removed {affected} failed videos from the database")
        return affected
    
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
    
    # Whitelist of valid column names to prevent SQL injection in dynamic queries
    ALLOWED_UPDATE_COLUMNS = {
        'bunny_guid', 'upload_provider', 'upload_id', 
        'local_filename', 'error_message',
        'doodstream_id', 'seekstreaming_id', 'lulustream_id'
    }
    
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
                # Validate column name against whitelist to prevent SQL injection
                if key not in self.ALLOWED_UPDATE_COLUMNS:
                    logger.warning(f"[SUPABASE] Ignoring unknown column: {key}")
                    continue
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
            logger.info(f"[RESET] Reset {affected} stale videos to PENDING")
        
        return affected
    
    def get_stats(self, provider=None):
        """
        Get status distribution for monitoring dashboard.
        If provider is specified, stats are tailored specifically to that provider.
        
        Returns:
            dict: Status counts (e.g., {'PENDING': 45, 'COMPLETED': 12})
        """
        if not provider:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT status, COUNT(*) 
                    FROM videos 
                    GROUP BY status
                """)
                return dict(cursor.fetchall())
        
        provider = provider.strip().lower()
        prov_col = {
            'doodstream': 'doodstream_id',
            'seekstreaming': 'seekstreaming_id',
            'lulustream': 'lulustream_id',
            'bunny': 'bunny_guid'
        }.get(provider)
        
        with self.get_cursor() as cursor:
            # Get other statuses (EXTRACTING, DOWNLOADING, UPLOADING, FAILED)
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM videos 
                WHERE status IN ('EXTRACTING', 'DOWNLOADING', 'UPLOADING', 'FAILED')
                GROUP BY status
            """)
            stats = dict(cursor.fetchall())
            
            if prov_col:
                # Completed means status is COMPLETED and the provider column is not null
                cursor.execute(f"""
                    SELECT COUNT(*) FROM videos 
                    WHERE status = 'COMPLETED' AND {prov_col} IS NOT NULL
                """)
                stats['COMPLETED'] = cursor.fetchone()[0]
                
                # Pending means status is PENDING or (COMPLETED and provider column is null)
                cursor.execute(f"""
                    SELECT COUNT(*) FROM videos 
                    WHERE status = 'PENDING' 
                       OR (status = 'COMPLETED' AND {prov_col} IS NULL)
                """)
                stats['PENDING'] = cursor.fetchone()[0]
            else:
                # Fallback if unknown provider
                cursor.execute("""
                    SELECT COUNT(*) FROM videos 
                    WHERE status = 'COMPLETED' AND upload_provider = %s
                """, (provider,))
                stats['COMPLETED'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(*) FROM videos 
                    WHERE status = 'PENDING' 
                       OR (status = 'COMPLETED' AND (upload_provider IS NULL OR upload_provider != %s))
                """, (provider,))
                stats['PENDING'] = cursor.fetchone()[0]
            
        return stats
    
    def get_provider_stats(self):
        """
        Get per-provider upload statistics for monitoring dashboard.
        
        Returns:
            dict: Provider counts (e.g., {'doodstream': 25, 'lulustream': 10})
                  Only includes COMPLETED videos with a known provider.
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COALESCE(upload_provider, 'unknown') as provider,
                    COUNT(*) as count
                FROM videos 
                WHERE status = 'COMPLETED' 
                    AND upload_provider IS NOT NULL
                GROUP BY upload_provider
                ORDER BY count DESC
            """)
            provider_stats = dict(cursor.fetchall())
        
        return provider_stats
    
    def get_total_count(self):
        """Get total number of videos in database."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM videos")
            return cursor.fetchone()[0]


# Singleton instance
db = SupabaseManager()
