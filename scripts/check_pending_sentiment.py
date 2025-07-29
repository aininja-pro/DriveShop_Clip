#!/usr/bin/env python3
"""
Script to check clips with pending sentiment status and diagnose the issue.
"""

import os
import sys
from datetime import datetime

# Add parent directory to path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import DatabaseManager
from src.utils.logger import setup_logger

# Setup logging
logger = setup_logger('check_pending_sentiment')

def check_pending_sentiment():
    """Check and display information about clips with pending sentiment"""
    
    # Initialize database connection
    db = DatabaseManager()
    
    print("\n🔍 Checking for clips with pending sentiment status...\n")
    
    try:
        # Query for clips that are in sentiment_analyzed stage but have sentiment_completed = False
        result = db.supabase.table('clips').select('*').eq('workflow_stage', 'sentiment_analyzed').eq('sentiment_completed', False).execute()
        
        if result.data:
            pending_clips = result.data
            print(f"📋 Found {len(pending_clips)} clips with pending sentiment:\n")
            
            for clip in pending_clips:
                print(f"WO #{clip['wo_number']} - {clip['make']} {clip['model']}")
                print(f"  Contact: {clip.get('contact', 'N/A')}")
                print(f"  Media Outlet: {clip.get('media_outlet', 'N/A')}")
                print(f"  Workflow Stage: {clip.get('workflow_stage', 'N/A')}")
                print(f"  Sentiment Completed: {clip.get('sentiment_completed', False)}")
                print(f"  URL: {clip.get('clip_url', 'N/A')}")
                
                # Check if any sentiment fields are populated
                sentiment_fields = ['overall_sentiment', 'relevance_score', 'overall_score', 
                                  'summary', 'sentiment_analysis_date']
                populated_fields = []
                for field in sentiment_fields:
                    if clip.get(field):
                        populated_fields.append(f"{field}: {clip[field]}")
                
                if populated_fields:
                    print(f"  ⚠️  Partial sentiment data found:")
                    for field_data in populated_fields:
                        print(f"    - {field_data}")
                else:
                    print(f"  ❌ No sentiment data found")
                
                print()
            
            # Also check for clips in 'found' stage that might need sentiment
            found_result = db.supabase.table('clips').select('*').eq('workflow_stage', 'found').execute()
            if found_result.data:
                print(f"\n⚠️  Also found {len(found_result.data)} clips in 'found' stage that haven't been analyzed yet")
                
        else:
            print("✅ No clips found with pending sentiment status")
            
            # Check if there are any clips ready for export
            ready_result = db.supabase.table('clips').select('wo_number', 'sentiment_completed').eq('workflow_stage', 'sentiment_analyzed').eq('sentiment_completed', True).execute()
            if ready_result.data:
                print(f"\n✅ {len(ready_result.data)} clips have completed sentiment analysis and are ready for export")
            
    except Exception as e:
        logger.error(f"Error checking pending sentiment clips: {e}")
        print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    check_pending_sentiment()