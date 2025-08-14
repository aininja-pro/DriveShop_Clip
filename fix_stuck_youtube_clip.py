#!/usr/bin/env python3
"""
Fix stuck YouTube clip that failed during sentiment analysis
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.database import get_database
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)

def check_and_fix_clip(wo_number='1208314'):
    """Check and fix the stuck YouTube clip"""
    db = get_database()
    
    # Get the clip
    result = db.supabase.table('clips').select('*').eq('wo_number', wo_number).execute()
    
    if not result.data:
        print(f"❌ Clip {wo_number} not found")
        return
    
    clip = result.data[0]
    
    print(f"\n📋 Clip {wo_number} current state:")
    print(f"  Status: {clip.get('status')}")
    print(f"  Workflow stage: {clip.get('workflow_stage')}")
    print(f"  Sentiment completed: {clip.get('sentiment_completed')}")
    print(f"  Content length: {len(clip.get('extracted_content', ''))}")
    print(f"  URL: {clip.get('clip_url')}")
    
    # Check why it's not showing in Approved Queue
    if clip.get('status') == 'approved':
        print("\n✅ Clip is approved")
        
        if clip.get('workflow_stage') != 'sentiment_analyzed':
            print("⚠️  But workflow_stage is not 'sentiment_analyzed'")
            print(f"   Current stage: {clip.get('workflow_stage')}")
            
            # Fix it by marking sentiment as completed
            print("\n🔧 Fixing clip...")
            
            update_data = {
                'workflow_stage': 'sentiment_analyzed',
                'sentiment_completed': True,
                'summary': 'YouTube video - transcription failed due to download errors. Manual review recommended.',
                'overall_sentiment': 'neutral',
                'relevance_score': 5,  # Set a moderate score since we couldn't analyze
            }
            
            result = db.supabase.table('clips').update(update_data).eq('wo_number', wo_number).execute()
            
            if result.data:
                print("✅ Clip fixed! It should now appear in Approved Queue")
                print("\nUpdated fields:")
                for key, value in update_data.items():
                    print(f"  {key}: {value}")
            else:
                print("❌ Failed to update clip")
        else:
            print("✅ Clip already has correct workflow_stage")
            print("\n🔍 Checking why it's not showing...")
            
            # Check if it's in a different run
            print(f"  Processing run ID: {clip.get('processing_run_id')}")
            
            # Get the latest run
            latest_run = db.supabase.table('processing_runs').select('*').order('created_at', desc=True).limit(1).execute()
            if latest_run.data:
                print(f"  Latest run ID: {latest_run.data[0]['id']}")
                if clip.get('processing_run_id') != latest_run.data[0]['id']:
                    print("  ⚠️ Clip is from a different processing run")
    else:
        print(f"\n⚠️ Clip status is '{clip.get('status')}', not 'approved'")
        
        # Update to approved if needed
        confirm = input("\nDo you want to approve this clip? (yes/no): ").strip().lower()
        if confirm == 'yes':
            update_data = {
                'status': 'approved',
                'workflow_stage': 'sentiment_analyzed',
                'sentiment_completed': True,
                'summary': 'YouTube video - transcription failed. Manual review recommended.',
                'overall_sentiment': 'neutral',
                'relevance_score': 5,
            }
            
            result = db.supabase.table('clips').update(update_data).eq('wo_number', wo_number).execute()
            
            if result.data:
                print("✅ Clip approved and fixed!")
            else:
                print("❌ Failed to approve clip")

if __name__ == "__main__":
    check_and_fix_clip()