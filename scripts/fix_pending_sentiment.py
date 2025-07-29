#!/usr/bin/env python3
"""
Script to re-run sentiment analysis on clips that have pending sentiment status.
This fixes clips that were approved but failed sentiment analysis.
"""

import os
import sys
from datetime import datetime
import logging

# Add parent directory to path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import DatabaseManager
from src.utils.sentiment_analysis import run_sentiment_analysis
from src.utils.logger import setup_logger

# Setup logging
logger = setup_logger('fix_pending_sentiment')

def get_pending_sentiment_clips(db):
    """Get all clips that have pending sentiment status"""
    try:
        # Query for clips that are in sentiment_analyzed stage but have sentiment_completed = False
        result = db.supabase.table('clips').select('*').eq('workflow_stage', 'sentiment_analyzed').eq('sentiment_completed', False).execute()
        
        if result.data:
            logger.info(f"Found {len(result.data)} clips with pending sentiment")
            return result.data
        else:
            logger.info("No clips found with pending sentiment")
            return []
    except Exception as e:
        logger.error(f"Error fetching pending sentiment clips: {e}")
        return []

def fix_pending_sentiment():
    """Main function to fix pending sentiment clips"""
    
    # Check for OpenAI API key
    if not os.environ.get('OPENAI_API_KEY'):
        logger.error("❌ OPENAI_API_KEY not found in environment variables")
        print("\n❌ ERROR: OpenAI API key not found!")
        print("Please set the OPENAI_API_KEY environment variable before running this script.")
        print("Example: export OPENAI_API_KEY='your-api-key-here'")
        return
    
    # Initialize database connection
    db = DatabaseManager()
    
    # Get clips with pending sentiment
    pending_clips = get_pending_sentiment_clips(db)
    
    if not pending_clips:
        print("✅ No clips found with pending sentiment status")
        return
    
    print(f"\n📋 Found {len(pending_clips)} clips with pending sentiment:")
    for clip in pending_clips:
        print(f"  - WO #{clip['wo_number']} - {clip['model']} - {clip['contact']}")
    
    # Confirm before proceeding
    response = input("\n🤔 Do you want to re-run sentiment analysis on these clips? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Operation cancelled")
        return
    
    print("\n🧠 Running sentiment analysis...")
    
    # Progress tracking
    def update_progress(progress, message):
        print(f"\r{message} - {int(progress * 100)}%", end='', flush=True)
    
    try:
        # Run sentiment analysis
        results = run_sentiment_analysis(pending_clips, update_progress)
        print()  # New line after progress
        
        # Process results
        success_count = 0
        if results and 'results' in results:
            for clip, result in zip(pending_clips, results['results']):
                if result.get('sentiment_completed'):
                    success = db.update_clip_sentiment(clip['id'], result)
                    if success:
                        success_count += 1
                        print(f"✅ Updated sentiment for WO #{clip['wo_number']}")
                    else:
                        print(f"❌ Failed to update sentiment for WO #{clip['wo_number']}")
                else:
                    print(f"⚠️  Sentiment analysis failed for WO #{clip['wo_number']}")
        
        print(f"\n📊 Summary: {success_count}/{len(pending_clips)} clips successfully updated")
        
        # Show remaining pending clips
        remaining_pending = get_pending_sentiment_clips(db)
        if remaining_pending:
            print(f"\n⚠️  {len(remaining_pending)} clips still have pending sentiment")
        else:
            print("\n✅ All clips now have completed sentiment analysis!")
            
    except Exception as e:
        logger.error(f"Error during sentiment analysis: {e}")
        print(f"\n❌ Error during sentiment analysis: {str(e)}")

if __name__ == "__main__":
    fix_pending_sentiment()