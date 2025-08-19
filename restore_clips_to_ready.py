#!/usr/bin/env python3
"""
Script to restore the 13 clips back to Ready to Export status.
This moves them from 'exported' back to 'sentiment_analyzed' workflow stage.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.utils.database import DatabaseManager
from src.utils.logger import logger

def restore_clips_to_ready():
    """Restore the 13 clips back to Ready to Export status."""
    
    # The 13 WO numbers from your report
    wo_numbers = [
        '1196311', '1213011', '1216969', '1210753', '1212369', 
        '1191442', '1221186', '1195226', '1210120', '1221419', 
        '1191033', '1218545', '1195280', '1204050'
    ]
    
    print("🔄 Restoring clips to Ready to Export status")
    print("=" * 60)
    print(f"Target WO numbers: {', '.join(wo_numbers)}")
    print()
    
    try:
        # Initialize database connection
        db = DatabaseManager()
        
        restored_count = 0
        not_found_count = 0
        already_ready_count = 0
        
        for wo in wo_numbers:
            print(f"Processing WO# {wo}...")
            
            # First, check current status
            result = db.supabase.table('clips').select(
                'id, wo_number, workflow_stage, fms_export_date'
            ).eq('wo_number', wo).execute()
            
            if not result.data:
                print(f"  ❌ WO# {wo}: Not found in database")
                not_found_count += 1
                continue
                
            clip = result.data[0]
            current_stage = clip.get('workflow_stage', 'unknown')
            export_date = clip.get('fms_export_date')
            
            print(f"  📋 Current stage: {current_stage}")
            if export_date:
                print(f"  📅 Export date: {export_date}")
            
            if current_stage == 'sentiment_analyzed':
                print(f"  ✅ Already in Ready to Export")
                already_ready_count += 1
                continue
            
            # Update the clip back to Ready to Export
            update_result = db.supabase.table('clips').update({
                'workflow_stage': 'sentiment_analyzed',
                # Keep the fms_export_date for reference but move back to ready
                # This way we can track that it was attempted but needs retry
            }).eq('id', clip['id']).execute()
            
            if update_result.data:
                print(f"  ✅ Restored to Ready to Export")
                restored_count += 1
            else:
                print(f"  ❌ Failed to update")
            
            print()
        
        # Summary
        print("=" * 60)
        print("📊 SUMMARY:")
        print(f"✅ Successfully restored: {restored_count}")
        print(f"⚠️  Already ready: {already_ready_count}")
        print(f"❌ Not found: {not_found_count}")
        print(f"📝 Total processed: {len(wo_numbers)}")
        
        if restored_count > 0:
            print()
            print("🎉 SUCCESS! Clips have been moved back to Ready to Export.")
            print("💡 You can now find them in the 'Ready to Export' tab.")
            print("📤 They will show 'Exported to FMS' status since they have export dates,")
            print("   but they're available for re-export/testing.")
        
        if not_found_count > 0:
            print()
            print(f"⚠️  {not_found_count} clips were not found. They may have been:")
            print("   - Deleted from the database")
            print("   - Have different WO numbers")
            print("   - Be in a different processing run")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        logger.error(f"Error restoring clips: {e}", exc_info=True)
        return False
        
    return True

if __name__ == "__main__":
    success = restore_clips_to_ready()
    if success:
        print("\n🚀 Script completed successfully!")
    else:
        print("\n💥 Script failed. Check the logs for details.")