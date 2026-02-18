import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_supabase import SupabaseManager
from core.logger import logger

def clean_database():
    print("=" * 60)
    print("Supabase Database Maintenance")
    print("=" * 60)
    
    try:
        db = SupabaseManager()
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return

    # 1. Show current stats
    print("\n1. Current Statistics:")
    stats = db.get_stats()
    if stats:
        for status, count in stats.items():
            print(f"   {status:12s}: {count:3d}")
    else:
        print("   Database is empty.")

    # 2. Identify failed entries to clean
    print("\n2. Cleaning up failed entries...")
    
    cleanup_patterns = [
        "No video URLs intercepted",
        "404",
        "Navigating to page failed",
        "Timeout"
    ]
    
    deleted_count = 0
    
    with db.get_cursor() as cursor:
        for pattern in cleanup_patterns:
            query = """
                DELETE FROM videos 
                WHERE status = 'FAILED' 
                AND error_message LIKE %s
            """
            cursor.execute(query, (f"%{pattern}%",))
            count = cursor.rowcount
            if count > 0:
                print(f"   Removed {count} entries with error containing: '{pattern}'")
                deleted_count += count
    
    if deleted_count == 0:
        print("   No matching failed entries found to clean.")
    else:
        print(f"   Total entries removed: {deleted_count}")

    # 3. Reset stale statuses
    print("\n3. Resetting stale statuses...")
    reset_count = db.reset_stale_statuses()
    print(f"   Reset {reset_count} stuck tasks to PENDING.")

    # 4. Final Stats
    print("\n4. Final Statistics:")
    stats = db.get_stats()
    if stats:
        for status, count in stats.items():
            print(f"   {status:12s}: {count:3d}")
    else:
        print("   Database is empty.")
        
    print("\n" + "=" * 60)
    print("Maintenance Complete")
    print("=" * 60)

if __name__ == "__main__":
    clean_database()
