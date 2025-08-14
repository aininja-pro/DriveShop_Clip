#!/usr/bin/env python3
"""
Re-extract and analyze a YouTube clip with Whisper support
"""
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.utils.database import DatabaseManager
from src.utils.youtube_handler import get_transcript, extract_video_id
from src.utils.sentiment_analysis import run_sentiment_analysis
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def reprocess_youtube_clip(wo_number):
    """Re-extract content and run sentiment for a YouTube clip"""
    db = DatabaseManager()
    
    # Find the clip
    result = db.supabase.table('clips').select('*').eq('wo_number', wo_number).execute()
    
    if not result.data:
        print(f"❌ No clip found with WO# {wo_number}")
        return False
        
    clip = result.data[0]
    print(f"\nFound clip: {clip['wo_number']} - {clip.get('media_outlet', 'Unknown')}")
    content = clip.get('extracted_content') or ''
    print(f"Current content length: {len(content)} chars")
    print(f"URL: {clip.get('clip_url', '')}")
    
    # Extract video ID
    video_id = extract_video_id(clip.get('clip_url', ''))
    if not video_id:
        print("❌ Could not extract video ID from URL")
        return False
    
    print(f"Video ID: {video_id}")
    
    # Re-extract transcript with Whisper fallback
    print("\n🔄 Re-extracting transcript (will use Whisper if no captions)...")
    transcript = get_transcript(video_id, video_url=clip.get('clip_url', ''), use_whisper_fallback=True)
    
    if transcript:
        print(f"✅ Got transcript: {len(transcript)} characters")
        print(f"\nFirst 500 chars:\n{transcript[:500]}...")
        
        # Update the clip with new content
        update_result = db.supabase.table('clips').update({
            'extracted_content': transcript,
            'workflow_stage': 'found'  # Reset to found so it can be approved again
        }).eq('id', clip['id']).execute()
        
        if update_result.data:
            print(f"\n✅ Updated clip with new transcript")
            
            # Now run sentiment analysis
            print("\n🤖 Running enhanced sentiment analysis...")
            clip['extracted_content'] = transcript  # Update local copy
            results = run_sentiment_analysis([clip])
            
            if results['successful'] > 0:
                print(f"\n✅ Sentiment analysis completed successfully!")
                
                # Fetch updated clip to see results
                updated = db.supabase.table('clips').select('*').eq('id', clip['id']).execute()
                if updated.data:
                    updated_clip = updated.data[0]
                    if updated_clip.get('sentiment_data_enhanced'):
                        import json
                        enhanced_data = json.loads(updated_clip['sentiment_data_enhanced'])
                        print(f"\n📊 Enhanced Sentiment Results:")
                        print(f"Key Features: {len(enhanced_data.get('key_features', []))} found")
                        print(f"Brand Attributes: {len(enhanced_data.get('brand_attributes', []))} found")
                        print(f"Purchase Drivers: {len(enhanced_data.get('purchase_drivers', []))} found")
            else:
                print(f"\n❌ Sentiment analysis failed")
        else:
            print(f"\n❌ Failed to update clip with new content")
    else:
        print(f"\n❌ Failed to extract transcript")
        
    return True

if __name__ == "__main__":
    # The YouTube clip from the log
    wo_number = "1203079"
    
    print(f"🎬 Reprocessing YouTube clip WO# {wo_number}...")
    reprocess_youtube_clip(wo_number)