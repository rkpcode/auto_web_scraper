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
        """Initialize database schema."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_url TEXT UNIQUE,
                    status TEXT DEFAULT 'PENDING',
                    bunny_guid TEXT,
                    local_filename TEXT,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME
                )
            ''')
            conn.commit()
            conn.close()
    
    def reset_stale_statuses(self):
        """
        Reset zombie threads from previous crashes.
        DOWNLOADING/UPLOADING -> PENDING
        """
        with self.lock:
            conn = sqlite3.connect(self.db_path)
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
    
    def get_pending_urls(self):
        """Returns all PENDING or FAILED URLs for crash recovery."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM videos WHERE original_url = ?", (url,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def insert_video(self, url, status='PENDING'):
        """Insert a new video record."""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
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
    
    def update_status(self, url, status, **kwargs):
        """
        Thread-safe atomic status update with dynamic kwargs.
        Example: update_status(url, 'COMPLETED', bunny_guid='xxx', local_filename='yyy')
        """
        with self.lock:
            conn = sqlite3.connect(self.db_path)
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
    
    def log_error(self, url, error_msg):
        """Mark video as FAILED with error details."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE videos 
                SET status = 'FAILED', error_message = ?, updated_at = ? 
                WHERE original_url = ?
            """, (error_msg, datetime.now(), url))
            conn.commit()
            conn.close()
    
    def get_stats(self):
        """Get status distribution for monitoring."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT status, COUNT(*) 
            FROM videos 
            GROUP BY status
        """)
        stats = dict(cursor.fetchall())
        conn.close()
        return stats


# Singleton instance
db = DatabaseManager()
