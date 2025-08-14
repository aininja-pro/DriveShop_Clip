#!/usr/bin/env python3
"""
Reset cooldowns for clips in testing
This script allows you to clear cooldowns and retry dates for clips that are stuck
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.database import get_database
from src.utils.logger import setup_logger

# Load environment variables
load_dotenv()

logger = setup_logger(__name__)

def reset_all_cooldowns():
    """Reset ALL cooldowns - use with caution"""
    db = get_database()
    
    try:
        # Reset all retry_after_dates in wo_tracking
        result = db.supabase.table('wo_tracking').update({
            'retry_after_date': None,
            'attempt_count': 0  # Reset attempt count too
        }).neq('status', 'found').execute()  # Don't reset successful ones
        
        logger.info(f"✅ Reset cooldowns for {len(result.data)} WO tracking records")
        
        # Reset clips with failed statuses to allow reprocessing
        result = db.supabase.table('clips').update({
            'status': 'pending_review',
            'attempt_count': 0
        }).in_('status', ['no_content_found', 'processing_failed']).execute()
        
        logger.info(f"✅ Reset status for {len(result.data)} failed clips")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error resetting cooldowns: {e}")
        return False

def reset_specific_wo_cooldowns(wo_numbers):
    """Reset cooldowns for specific WO numbers"""
    db = get_database()
    
    try:
        # Reset retry_after_dates for specific WOs
        result = db.supabase.table('wo_tracking').update({
            'retry_after_date': None,
            'attempt_count': 0
        }).in_('wo_number', wo_numbers).execute()
        
        logger.info(f"✅ Reset cooldowns for {len(result.data)} specific WOs")
        
        # Reset clips for these WOs
        result = db.supabase.table('clips').update({
            'status': 'pending_review',
            'attempt_count': 0
        }).in_('wo_number', wo_numbers).execute()
        
        logger.info(f"✅ Reset clips for {len(result.data)} specific WOs")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error resetting specific cooldowns: {e}")
        return False

def list_clips_in_cooldown():
    """List all clips currently in cooldown"""
    db = get_database()
    
    try:
        # Get WOs with future retry dates
        result = db.supabase.table('wo_tracking').select('*').gt('retry_after_date', datetime.now().isoformat()).execute()
        
        if result.data:
            logger.info(f"\n📋 Found {len(result.data)} WOs in cooldown:")
            for wo in result.data:
                retry_date = datetime.fromisoformat(wo['retry_after_date'].replace('Z', '+00:00'))
                time_left = retry_date - datetime.now(retry_date.tzinfo)
                logger.info(f"  WO# {wo['wo_number']}: cooldown until {retry_date.strftime('%Y-%m-%d %H:%M')} ({time_left.days} days, {time_left.seconds//3600} hours left)")
        else:
            logger.info("✅ No WOs currently in cooldown")
            
        # Also check failed clips
        result = db.supabase.table('clips').select('wo_number, status, attempt_count').in_('status', ['no_content_found', 'processing_failed']).execute()
        
        if result.data:
            logger.info(f"\n📋 Found {len(result.data)} clips with failed status:")
            for clip in result.data[:10]:  # Show first 10
                logger.info(f"  WO# {clip['wo_number']}: {clip['status']} (attempts: {clip.get('attempt_count', 0)})")
            if len(result.data) > 10:
                logger.info(f"  ... and {len(result.data) - 10} more")
                
    except Exception as e:
        logger.error(f"❌ Error listing cooldowns: {e}")

def set_cooldown_to_past():
    """Set all cooldowns to past date (makes them immediately retryable)"""
    db = get_database()
    
    try:
        past_date = (datetime.now() - timedelta(days=1)).isoformat()
        
        # Update all non-found WOs to have past retry date
        result = db.supabase.table('wo_tracking').update({
            'retry_after_date': past_date
        }).neq('status', 'found').not_.is_('retry_after_date', None).execute()
        
        logger.info(f"✅ Set {len(result.data)} WO cooldowns to past (immediately retryable)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error setting cooldowns to past: {e}")
        return False

def main():
    """Main menu for cooldown management"""
    
    print("\n🔧 COOLDOWN RESET UTILITY")
    print("=" * 50)
    print("⚠️  WARNING: This tool modifies database cooldowns")
    print("=" * 50)
    
    while True:
        print("\nOptions:")
        print("1. List all clips in cooldown")
        print("2. Reset ALL cooldowns (immediate retry)")
        print("3. Set cooldowns to past (ready for retry)")
        print("4. Reset specific WO numbers")
        print("5. Exit")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == '1':
            list_clips_in_cooldown()
            
        elif choice == '2':
            confirm = input("\n⚠️  This will reset ALL cooldowns. Are you sure? (yes/no): ").strip().lower()
            if confirm == 'yes':
                if reset_all_cooldowns():
                    print("✅ All cooldowns reset successfully!")
                else:
                    print("❌ Failed to reset cooldowns")
            else:
                print("Cancelled")
                
        elif choice == '3':
            confirm = input("\n⚠️  This will make all cooldowns immediately retryable. Continue? (yes/no): ").strip().lower()
            if confirm == 'yes':
                if set_cooldown_to_past():
                    print("✅ Cooldowns set to past - all ready for retry!")
                else:
                    print("❌ Failed to update cooldowns")
            else:
                print("Cancelled")
                
        elif choice == '4':
            wo_input = input("\nEnter WO numbers (comma-separated): ").strip()
            wo_numbers = [wo.strip() for wo in wo_input.split(',') if wo.strip()]
            
            if wo_numbers:
                if reset_specific_wo_cooldowns(wo_numbers):
                    print(f"✅ Reset cooldowns for {len(wo_numbers)} WO numbers")
                else:
                    print("❌ Failed to reset specific cooldowns")
            else:
                print("No WO numbers provided")
                
        elif choice == '5':
            print("\nExiting...")
            break
            
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()