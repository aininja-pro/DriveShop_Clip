#!/usr/bin/env python3
"""
Fix existing NULL Activity_ID records in the database
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.ingest.ingest import load_loans_data_from_url
from src.utils.database import get_database

def fix_existing_activity_ids():
    """Fix existing NULL Activity_ID records by fetching fresh data and updating"""
    
    print("🔧 Fixing existing NULL Activity_ID records...")
    
    try:
        db = get_database()
        
        # Get all clips with NULL Activity_ID
        null_clips_result = db.supabase.table('clips').select('*').is_('activity_id', None).execute()
        null_clips = null_clips_result.data
        
        print(f"📊 Found {len(null_clips)} clips with NULL Activity_ID")
        
        if not null_clips:
            print("✅ No NULL Activity_ID records found!")
            return True
        
        # Get fresh source data
        url = "https://reports.driveshop.com/?report=file:/home/deployer/reports/clips/media_loans_without_clips.rpt&init=csv"
        loans = load_loans_data_from_url(url)
        
        # Create mapping of WO# to Activity_ID
        wo_to_activity_id = {}
        for loan in loans:
            wo_number = str(loan.get('work_order', ''))
            activity_id = loan.get('activity_id', '')
            if wo_number and activity_id:
                wo_to_activity_id[wo_number] = activity_id
        
        print(f"📋 Source data has {len(wo_to_activity_id)} WO# to Activity_ID mappings")
        
        # Fix each NULL record
        fixed_count = 0
        for clip in null_clips:
            wo_number = str(clip.get('wo_number', ''))
            clip_id = clip.get('id')
            
            if wo_number in wo_to_activity_id:
                activity_id = wo_to_activity_id[wo_number]
                
                print(f"🔧 Updating WO#{wo_number} with Activity_ID: {activity_id}")
                
                update_result = db.supabase.table('clips').update({
                    'activity_id': activity_id
                }).eq('id', clip_id).execute()
                
                if update_result.data:
                    print(f"   ✅ Successfully updated")
                    fixed_count += 1
                else:
                    print(f"   ❌ Failed to update")
            else:
                print(f"   ⚠️ WO#{wo_number} not found in source data - skipping")
        
        print(f"\n📊 Fixed {fixed_count} out of {len(null_clips)} NULL Activity_ID records")
        
        # Verify the fixes
        print("\n🔍 Verifying fixes...")
        remaining_null_result = db.supabase.table('clips').select('*').is_('activity_id', None).execute()
        remaining_null = remaining_null_result.data
        
        print(f"📊 Remaining NULL Activity_ID records: {len(remaining_null)}")
        
        if len(remaining_null) == 0:
            print("🎉 All Activity_ID records are now populated!")
            return True
        else:
            print("⚠️ Some records still have NULL Activity_ID")
            for clip in remaining_null:
                print(f"   - WO#{clip.get('wo_number')} (ID: {clip.get('id')})")
            return len(remaining_null) < len(null_clips)  # Return True if we made progress
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_existing_activity_ids()
    if success:
        print("\n🎉 Activity_ID fix operation completed successfully!")
    else:
        print("\n💥 Activity_ID fix operation failed!")
    
    exit(0 if success else 1) 