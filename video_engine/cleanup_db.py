"""
Database cleanup utility for Colab.
Run this if you encounter 'database is locked' errors.
"""

import os
import sqlite3

# Colab database path
DB_PATH = "/content/drive/MyDrive/video_engine_data/video_tracker.db"

print("=" * 60)
print("Database Cleanup Utility")
print("=" * 60)

if not os.path.exists(DB_PATH):
    print(f"\nDatabase not found at: {DB_PATH}")
    print("Nothing to clean up.")
    exit(0)

print(f"\nDatabase found: {DB_PATH}")

# Close any existing connections
print("\n1. Checking for lock files...")
lock_files = [
    DB_PATH + "-shm",
    DB_PATH + "-wal",
    DB_PATH + "-journal"
]

for lock_file in lock_files:
    if os.path.exists(lock_file):
        print(f"   Found: {os.path.basename(lock_file)}")
        try:
            os.remove(lock_file)
            print(f"   Removed: {os.path.basename(lock_file)}")
        except Exception as e:
            print(f"   Failed to remove: {e}")

# Vacuum the database
print("\n2. Optimizing database...")
try:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("VACUUM")
    conn.commit()
    conn.close()
    print("   Database optimized successfully")
except Exception as e:
    print(f"   Error: {e}")

# Show stats
print("\n3. Database statistics:")
try:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute("SELECT status, COUNT(*) FROM videos GROUP BY status")
    stats = dict(cursor.fetchall())
    
    if stats:
        for status, count in stats.items():
            print(f"   {status:12s}: {count:3d}")
    else:
        print("   No videos in database")
    
    conn.close()
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 60)
print("Cleanup complete! You can now re-run the pipeline.")
print("=" * 60)
