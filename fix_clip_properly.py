#!/usr/bin/env python3
"""
Properly fix the clip state - approved but sentiment pending
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

def fix_clip_state():
    """Fix the clip to proper state - approved but sentiment pending"""
    db = get_database()
    
    # Revert my bad changes
    result = db.supabase.table('clips').update({
        'workflow_stage': 'found',  # Original stage - NOT sentiment_analyzed
        'sentiment_completed': False,  # Sentiment is NOT complete
        'summary': None,  # Remove fake summary
        'overall_sentiment': None,  # Remove fake sentiment
        'relevance_score': db.supabase.table('clips').select('relevance_score').eq('wo_number', '1208314').execute().data[0].get('relevance_score')  # Keep original score if any
    }).eq('wo_number', '1208314').execute()
    
    if result.data:
        print("✅ Fixed properly:")
        print("  - Status: approved (correct)")
        print("  - Workflow stage: found (correct - sentiment not done)")
        print("  - Sentiment completed: False (correct)")
        print("\nThis clip should now show in Approved Queue with 'Sentiment Pending'")
        print("You can run sentiment from there when ready.")
    else:
        print("❌ Failed to fix clip state")
    
    # Now let's check why the Approved Queue isn't showing it
    print("\n🔍 Checking Approved Queue query logic...")
    
    # Get all approved clips to see the pattern
    approved = db.supabase.table('clips').select('wo_number, status, workflow_stage, sentiment_completed').eq('status', 'approved').execute()
    
    if approved.data:
        print(f"\nFound {len(approved.data)} approved clips:")
        for clip in approved.data[:5]:  # Show first 5
            print(f"  WO# {clip['wo_number']}: stage={clip['workflow_stage']}, sentiment_completed={clip['sentiment_completed']}")
        
        # Count by workflow stage
        stages = {}
        for clip in approved.data:
            stage = clip['workflow_stage']
            stages[stage] = stages.get(stage, 0) + 1
        
        print("\nApproved clips by workflow stage:")
        for stage, count in stages.items():
            print(f"  {stage}: {count} clips")
        
        print("\n⚠️  The Approved Queue should show ALL approved clips, regardless of sentiment status")
        print("If it's filtering by workflow_stage='sentiment_analyzed', that's the bug.")

if __name__ == "__main__":
    fix_clip_state()