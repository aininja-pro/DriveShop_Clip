#\!/usr/bin/env python3
"""
Check what content was extracted for YouTube clip
"""
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.utils.database import DatabaseManager

def check_content(wo_number):
    db = DatabaseManager()
    
    result = db.supabase.table('clips').select('*').eq('wo_number', wo_number).execute()
    
    if result.data:
        clip = result.data[0]
        content = clip.get('extracted_content', '')
        print(f"WO# {wo_number}")
        print(f"URL: {clip.get('clip_url', '')}")
        print(f"Content length: {len(content)} chars")
        print(f"\nContent preview:")
        print("-" * 50)
        print(content[:500] + "..." if len(content) > 500 else content)
        print("-" * 50)
        
        # Check enhanced data
        if clip.get('sentiment_data_enhanced'):
            import json
            enhanced = json.loads(clip['sentiment_data_enhanced'])
            print(f"\nEnhanced sentiment data:")
            print(f"Key features: {len(enhanced.get('key_features', []))}")
            print(f"Brand attributes: {len(enhanced.get('brand_attributes', []))}")
            print(f"Purchase drivers: {len(enhanced.get('purchase_drivers', []))}")

if __name__ == "__main__":
    check_content("1203079")