#!/usr/bin/env python3
"""
Clear all data from Supabase database tables.
This script will delete all clips, processing runs, and WO tracking data.
"""

import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from utils.database import get_database
from utils.logger import setup_logger

logger = setup_logger(__name__)

def clear_database():
    """Clear all data from the database"""
    try:
        # Get database connection
        db = get_database()
        
        if not db.test_connection():
            logger.error("Cannot connect to database")
            return False
        
        logger.info("🗑️ Starting database cleanup...")
        
        # Clear clips table
        logger.info("Clearing clips table...")
        result = db.supabase.table('clips').delete().gte('id', 0).execute()
        logger.info(f"✅ Deleted clips from clips table")
        
        # Clear processing runs table
        logger.info("Clearing processing_runs table...")
        result = db.supabase.table('processing_runs').delete().gte('created_at', '2000-01-01').execute()
        logger.info(f"✅ Deleted processing runs from processing_runs table")
        
        # Clear WO tracking table
        logger.info("Clearing wo_tracking table...")
        result = db.supabase.table('wo_tracking').delete().gte('id', 0).execute()
        logger.info(f"✅ Deleted WO tracking records from wo_tracking table")
        
        logger.info("🎉 Database cleanup completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error clearing database: {e}")
        return False

if __name__ == "__main__":
    print("⚠️  WARNING: This will delete ALL data from the database!")
    print("This includes:")
    print("- All clips (pending, approved, rejected)")
    print("- All processing runs")
    print("- All WO tracking data")
    print()
    
    confirm = input("Are you sure you want to continue? Type 'YES' to confirm: ")
    
    if confirm == 'YES':
        success = clear_database()
        if success:
            print("✅ Database cleared successfully!")
        else:
            print("❌ Failed to clear database!")
            sys.exit(1)
    else:
        print("❌ Database clearing cancelled.")
        sys.exit(0) 