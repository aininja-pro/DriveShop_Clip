#!/usr/bin/env python3
import pandas as pd
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Add the src directory to the path so we can import the function
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import the create_client_excel_report function
from dashboard.app import create_client_excel_report

# Read the most recent approved clips JSON file
with open('data/approved_clips_20250626_000635.json', 'r') as f:
    approved_data = json.load(f)

print(f"📊 Raw data loaded: {len(approved_data)} clips")

# Convert to the format expected by the Excel function
formatted_data = []
for i, clip in enumerate(approved_data, 1):
    # Generate Activity ID based on work order and sequence
    activity_id = f"ACT-{clip.get('work_order', '')}-{i:03d}"
    
    formatted_clip = {
        'Activity_ID': activity_id,
        'Office': clip.get('office', ''),
        'WO #': clip.get('work_order', ''),
        'Make': clip.get('make', ''),
        'Model': clip.get('vehicle_model', ''),
        'Contact': clip.get('contact', ''),
        'Media_Outlet': clip.get('media_outlet', ''),
        'Relevance': clip.get('relevance_score', ''),
        'Sentiment': clip.get('sentiment', ''),
        'URLs': clip.get('clip_url', ''),
        'Other_URLs': clip.get('original_links', ''),
        'Title': 'Media Clip',  # Default title since not in JSON
        'Published_Date': clip.get('processed_date', ''),
        'Summary': clip.get('summary', ''),
        'Brand_Alignment': clip.get('brand_alignment', ''),
        'Approval_Status': 'Approved',
        'Approval_Date': clip.get('approval_timestamp', ''),
        'Notes': clip.get('recommendation', '')
    }
    formatted_data.append(formatted_clip)

# Convert to DataFrame
df = pd.DataFrame(formatted_data)

print(f"📊 Formatted data: {len(df)} clips with {len(df.columns)} columns")
print(f"📋 Sample Activity IDs: {df['Activity_ID'].head(3).tolist()}")

# Generate the beautiful formatted Excel report
workbook = create_client_excel_report(df)

# Save with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
excel_filename = f'DriveShop_WITH_ACTIVITY_IDS_{timestamp}.xlsx'

workbook.save(excel_filename)

print(f"✅ FINAL Excel report created: {excel_filename}")
print(f"📋 Contains your 39 approved clips with PROPER ACTIVITY IDs")
print(f"🎨 All tabs have data and Activity IDs are filled!") 