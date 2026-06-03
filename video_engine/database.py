import sqlite3
import threading
from datetime import datetime
from config import DB_PATH


class DatabaseManager:
    """Thread-safe SQLite database manager with zombie thread recovery."""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema with WAL mode for better concurrency."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
            conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
            # Enable WAL mode for better concurrent access
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_url TEXT UNIQUE,
                    status TEXT DEFAULT 'PENDING',
                    bunny_guid TEXT,
                    upload_provider TEXT,
                    upload_id TEXT,
                    local_filename TEXT,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME
                )
            ''')
            
            # Migration check for existing SQLite database
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(videos)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'upload_provider' not in columns:
                conn.execute("ALTER TABLE videos ADD COLUMN upload_provider TEXT")
            if 'upload_id' not in columns:
                conn.execute("ALTER TABLE videos ADD COLUMN upload_id TEXT")
                
            # Migrate any old streamwish entries to seekstreaming
            conn.execute("UPDATE videos SET upload_provider = 'seekstreaming' WHERE upload_provider = 'streamwish'")
                 
            conn.commit()
            conn.close()
    
    def reset_stale_statuses(self):
        """
        Reset zombie threads from previous crashes.
        DOWNLOADING/UPLOADING -> PENDING
        """
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
            conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE videos 
                SET status = 'PENDING', updated_at = ? 
                WHERE status IN ('DOWNLOADING', 'UPLOADING', 'EXTRACTING')
            """, (datetime.now(),))
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            return affected
    
    def get_pending_urls(self, current_provider=None):
        """Returns all PENDING or FAILED URLs, or COMPLETED URLs with a different upload provider for crash recovery."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
            conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
            cursor = conn.cursor()
            if current_provider:
                cursor.execute("""
                    SELECT original_url 
                    FROM videos 
                    WHERE status IN ('PENDING', 'FAILED')
                       OR (status = 'COMPLETED' AND (upload_provider IS NULL OR upload_provider != ?))
                    ORDER BY created_at ASC
                """, (current_provider,))
            else:
                cursor.execute("""
                    SELECT original_url 
                    FROM videos 
                    WHERE status IN ('PENDING', 'FAILED')
                    ORDER BY created_at ASC
                """)
            urls = [row[0] for row in cursor.fetchall()]
            conn.close()
            return urls
    
    def get_video_status(self, url):
        """Check status of a video by URL."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
            conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM videos WHERE original_url = ?", (url,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None

    def get_video_details(self, url):
        """Get status and upload_provider of a video by URL."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
            conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
            cursor = conn.cursor()
            cursor.execute("SELECT status, upload_provider FROM videos WHERE original_url = ?", (url,))
            result = cursor.fetchone()
            conn.close()
            return result if result else None

    def clean_failed_videos(self):
        """Delete all videos with status 'FAILED' from the database."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
            conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
            cursor = conn.cursor()
            cursor.execute("DELETE FROM videos WHERE status = 'FAILED'")
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            return affected
    
    def insert_video(self, url, status='PENDING'):
        """Insert a new video record."""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
                conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO videos (original_url, status, created_at) 
                    VALUES (?, ?, ?)
                """, (url, status, datetime.now()))
                conn.commit()
                conn.close()
                return True
        except sqlite3.IntegrityError:
            # URL already exists
            return False
    
    def insert_videos_batch(self, urls, status='PENDING', batch_size=100):
        """
        Insert multiple videos in batches for better performance.
        
        Args:
            urls: List/set of URLs to insert
            status: Initial status for all URLs
            batch_size: Number of URLs per batch
            
        Returns:
            int: Number of successfully inserted URLs
        """
        inserted_count = 0
        urls_list = list(urls) if isinstance(urls, set) else urls
        
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
            conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
            cursor = conn.cursor()
            
            # Process in batches
            for i in range(0, len(urls_list), batch_size):
                batch = urls_list[i:i + batch_size]
                now = datetime.now()
                
                # Prepare batch data
                batch_data = [(url, status, now) for url in batch]
                
                try:
                    cursor.executemany("""
                        INSERT OR IGNORE INTO videos (original_url, status, created_at)
                        VALUES (?, ?, ?)
                    """, batch_data)
                    inserted_count += cursor.rowcount
                except Exception as e:
                    # Log error but continue with next batch
                    import logging
                    logging.error(f"Batch insert error: {e}")
            
            conn.commit()
            conn.close()
        
        return inserted_count
    
    def update_status(self, url, status, **kwargs):
        """
        Thread-safe atomic status update with dynamic kwargs.
        Example: update_status(url, 'COMPLETED', bunny_guid='xxx', local_filename='yyy')
        """
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
            conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
            cursor = conn.cursor()
            
            # Build dynamic UPDATE query
            set_clauses = ["status = ?", "updated_at = ?"]
            params = [status, datetime.now()]
            
            for key, value in kwargs.items():
                set_clauses.append(f"{key} = ?")
                params.append(value)
            
            query = f"UPDATE videos SET {', '.join(set_clauses)} WHERE original_url = ?"
            params.append(url)
            
            cursor.execute(query, params)
            conn.commit()
            conn.close()
    
    def log_error(self, url, error_msg, provider=None):
        """Mark video as FAILED with error details."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
            conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
            cursor = conn.cursor()
            if provider:
                cursor.execute("""
                    UPDATE videos 
                    SET status = 'FAILED', error_message = ?, upload_provider = ?, updated_at = ? 
                    WHERE original_url = ?
                """, (error_msg, provider, datetime.now(), url))
            else:
                cursor.execute("""
                    UPDATE videos 
                    SET status = 'FAILED', error_message = ?, updated_at = ? 
                    WHERE original_url = ?
                """, (error_msg, datetime.now(), url))
            conn.commit()
            conn.close()
    
    def get_stats(self, provider=None):
        """Get status distribution for monitoring."""
        if not provider:
            with self.lock:
                conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
                conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status, COUNT(*) 
                    FROM videos 
                    GROUP BY status
                """)
                stats = dict(cursor.fetchall())
                conn.close()
                return stats

        provider = provider.strip().lower()
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=60.0, isolation_level='DEFERRED')
            conn.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout
            cursor = conn.cursor()
            query = """
                SELECT 
                    CASE 
                        WHEN status = 'COMPLETED' AND upload_provider = ? THEN 'COMPLETED'
                        WHEN status = 'FAILED' AND upload_provider = ? THEN 'FAILED'
                        WHEN status = 'EXTRACTING' AND upload_provider = ? THEN 'EXTRACTING'
                        WHEN status = 'DOWNLOADING' AND upload_provider = ? THEN 'DOWNLOADING'
                        WHEN status = 'UPLOADING' AND upload_provider = ? THEN 'UPLOADING'
                        ELSE 'PENDING'
                    END as status_bucket,
                    COUNT(*)
                FROM videos
                GROUP BY status_bucket
            """
            cursor.execute(query, (provider, provider, provider, provider, provider))
            stats = dict(cursor.fetchall())
            conn.close()
            return stats


# Singleton instance
db = DatabaseManager()
