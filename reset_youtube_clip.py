#!/usr/bin/env python3
"""
Reset YouTube clip to approved stage with original short content
"""
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.utils.database import DatabaseManager

def reset_clip(wo_number):
    """Reset clip to approved stage with short content"""
    db = DatabaseManager()
    
    # Find the clip
    result = db.supabase.table('clips').select('*').eq('wo_number', wo_number).execute()
    
    if result.data:
        clip = result.data[0]
        
        # Reset to the original short content
        short_content = """We got the new Volvo EX30 and instantly fell in love! This might just be the most fun (and well packaged) small electric crossover on the planet. What do you think? Would you pick this over the similarly sized (more expensive) Mini Countryman or smaller (cheaper) Chevy Bolt? And stay tuned... we've got a lot more content planned on this lovely little yellow plush toy!"""
        
        # Update the clip
        update_result = db.supabase.table('clips').update({
            'extracted_content': short_content,
            'workflow_stage': 'found',  # Back to approved stage
            'sentiment_completed': False,
            'sentiment_data_enhanced': None,
            'sentiment_version': 'v1'
        }).eq('id', clip['id']).execute()
        
        if update_result.data:
            print(f"✅ Reset clip WO# {wo_number} to approved stage with {len(short_content)} chars")
            print(f"When you run sentiment analysis, it will now automatically re-extract with Whisper")
            return True
    
    return False

if __name__ == "__main__":
    wo_number = "1203079"
    print(f"Resetting YouTube clip WO# {wo_number}...")
    reset_clip(wo_number)