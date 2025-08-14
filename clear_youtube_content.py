#!/usr/bin/env python3
"""
Clear extracted content for a YouTube clip to force re-extraction
"""
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.utils.database import DatabaseManager

def clear_content_for_wo(wo_number):
    """Clear extracted content for a specific WO number"""
    db = DatabaseManager()
    
    # Find the clip
    result = db.supabase.table('clips').select('*').eq('wo_number', wo_number).execute()
    
    if result.data:
        clip = result.data[0]
        print(f"Found clip: {clip['wo_number']} - {clip.get('media_outlet', 'Unknown')}")
        print(f"Current content length: {len(clip.get('extracted_content', ''))} chars")
        print(f"URL: {clip.get('clip_url', '')}")
        
        # Clear the extracted content
        update_result = db.supabase.table('clips').update({
            'extracted_content': None,  # Clear the content
            'workflow_stage': 'found'  # Reset to found stage
        }).eq('id', clip['id']).execute()
        
        if update_result.data:
            print(f"\n✅ Cleared extracted content for WO# {wo_number}")
            print("The clip will now re-extract content when processed again")
            return True
        else:
            print(f"\n❌ Failed to update clip")
            return False
    else:
        print(f"\n❌ No clip found with WO# {wo_number}")
        return False

if __name__ == "__main__":
    # The YouTube clip from the log
    wo_number = "1203079"
    
    print(f"Clearing content for YouTube clip WO# {wo_number}...")
    clear_content_for_wo(wo_number)