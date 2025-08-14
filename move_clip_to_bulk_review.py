#!/usr/bin/env python3
"""
Move a clip back to Bulk Review (pending_review status)
"""

import os
import sys
from dotenv import load_dotenv

# Load environment first
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.database import get_database
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def move_clip_to_bulk_review(wo_number='1208314'):
    """Move a clip back to Bulk Review for testing"""
    db = get_database()
    
    # Get current state
    result = db.supabase.table('clips').select('*').eq('wo_number', wo_number).execute()
    
    if not result.data:
        print(f"❌ Clip {wo_number} not found")
        return
    
    clip = result.data[0]
    
    print(f"\n📋 Current state of WO# {wo_number}:")
    print(f"  Status: {clip.get('status')}")
    print(f"  Workflow stage: {clip.get('workflow_stage')}")
    print(f"  Sentiment completed: {clip.get('sentiment_completed')}")
    print(f"  Content length: {len(clip.get('extracted_content', ''))}")
    
    # Move back to Bulk Review
    print(f"\n🔄 Moving clip back to Bulk Review...")
    
    update_data = {
        'status': 'pending_review',  # This puts it in Bulk Review
        'workflow_stage': 'found',    # Reset to initial stage
        'sentiment_completed': False, # Clear sentiment status
        'sentiment_data_enhanced': None,  # Clear enhanced sentiment data
        'overall_sentiment': None,    # Clear sentiment
        'summary': None,              # Clear summary
    }
    
    result = db.supabase.table('clips').update(update_data).eq('wo_number', wo_number).execute()
    
    if result.data:
        print("✅ Success! Clip moved back to Bulk Review")
        print("\nClip is now:")
        print("  Status: pending_review")
        print("  Workflow stage: found")
        print("  Ready for testing in Bulk Review tab")
        
        # Also clear it from approved/rejected session state if needed
        print("\n📝 Note: You may need to refresh the dashboard to see the change")
    else:
        print("❌ Failed to move clip")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        wo_number = sys.argv[1]
        print(f"Moving WO# {wo_number} to Bulk Review...")
        move_clip_to_bulk_review(wo_number)
    else:
        # Default to the problematic YouTube clip
        move_clip_to_bulk_review('1208314')