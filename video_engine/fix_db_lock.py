"""
Database Lock Fix Utility
Resolves SQLite database locking issues by:
1. Closing all connections
2. Removing WAL files
3. Rebuilding database with proper settings
"""
import sqlite3
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH

def fix_database_lock():
    """Fix database locking issues."""
    print("🔧 Database Lock Fix Utility")
    print("=" * 60)
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    print(f"📂 Database path: {DB_PATH}")
    
    # Check for WAL files
    wal_file = f"{DB_PATH}-wal"
    shm_file = f"{DB_PATH}-shm"
    
    wal_exists = os.path.exists(wal_file)
    shm_exists = os.path.exists(shm_file)
    
    if wal_exists:
        print(f"⚠️  Found WAL file: {wal_file}")
    if shm_exists:
        print(f"⚠️  Found SHM file: {shm_file}")
    
    print("\n🔄 Attempting to fix database lock...")
    
    try:
        # Step 1: Open connection and checkpoint WAL
        print("  1. Checkpointing WAL...")
        conn = sqlite3.connect(DB_PATH, timeout=60.0)
        conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        conn.commit()
        conn.close()
        print("     ✅ WAL checkpointed")
        
        # Step 2: Remove WAL files if they still exist
        if os.path.exists(wal_file):
            print("  2. Removing WAL file...")
            try:
                os.remove(wal_file)
                print("     ✅ WAL file removed")
            except Exception as e:
                print(f"     ⚠️  Could not remove WAL file: {e}")
        
        if os.path.exists(shm_file):
            print("  3. Removing SHM file...")
            try:
                os.remove(shm_file)
                print("     ✅ SHM file removed")
            except Exception as e:
                print(f"     ⚠️  Could not remove SHM file: {e}")
        
        # Step 3: Optimize database
        print("  4. Optimizing database...")
        conn = sqlite3.connect(DB_PATH, timeout=60.0)
        conn.execute('PRAGMA optimize')
        conn.execute('VACUUM')
        
        # Re-enable WAL mode with proper settings
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA busy_timeout=60000')
        
        conn.commit()
        conn.close()
        print("     ✅ Database optimized")
        
        print("\n✅ Database lock fix completed successfully!")
        print("\n📊 Database is now ready to use.")
        
    except Exception as e:
        print(f"\n❌ Error fixing database: {e}")
        print("\n💡 Alternative solution:")
        print("   1. Close all Python processes")
        print("   2. Delete the database file and WAL files manually")
        print("   3. Run the pipeline again to recreate the database")
        return False
    
    return True


if __name__ == "__main__":
    success = fix_database_lock()
    sys.exit(0 if success else 1)
