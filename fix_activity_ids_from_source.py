#!/usr/bin/env python3
import pandas as pd
import sys
import os
import requests
from datetime import datetime

# Add the src directory to the path so we can import the function
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import the create_client_excel_report function
from dashboard.app import create_client_excel_report

# First, get the source data to create WO# -> Activity_ID mapping
print("📥 Fetching source data to create WO# -> Activity_ID mapping...")

# The source data from reports.driveshop.com
source_url = "https://reports.driveshop.com/?report=file:/home/deployer/reports/clips/media_loans_without_clips.rpt&init=csv"

try:
    response = requests.get(source_url)
    source_data = response.text
    
    # Parse the CSV-like data
    lines = source_data.strip().split('\n')
    wo_to_activity_mapping = {}
    
    for line in lines:
        # Parse each line - format: "Activity_ID","Person_ID","Make","Model","WO#",...
        parts = [part.strip('"') for part in line.split('","')]
        if len(parts) >= 5:
            activity_id = parts[0]  # First item is Activity_ID
            wo_number = parts[4]    # FIFTH item is WO# (index 4)
            wo_to_activity_mapping[wo_number] = activity_id
    
    print(f"✅ Created mapping for {len(wo_to_activity_mapping)} WO# -> Activity_ID pairs")
    print(f"📋 Sample mappings: {list(wo_to_activity_mapping.items())[:3]}")
    
except Exception as e:
    print(f"❌ Error fetching source data: {e}")
    print("Script failed - cannot proceed without source data mapping")
    exit(1)

# Read the approved clips CSV file
df = pd.read_csv('data/approved_clips.csv')
print(f"📊 Loaded {len(df)} approved clips from CSV")

# Fill in the Activity_ID based on WO# mapping
df['Activity_ID'] = df['WO #'].astype(str).map(wo_to_activity_mapping)

# Check how many we successfully mapped
mapped_count = df['Activity_ID'].notna().sum()
print(f"✅ Successfully mapped Activity_IDs for {mapped_count} out of {len(df)} clips")

# Show some examples
print("\n📋 Sample mappings:")
for i, row in df.head(5).iterrows():
    wo_num = row['WO #']
    activity_id = row['Activity_ID']
    print(f"   WO# {wo_num} -> Activity_ID {activity_id}")

# Generate the beautiful formatted Excel report
workbook = create_client_excel_report(df)

# Save with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
excel_filename = f'DriveShop_WITH_REAL_ACTIVITY_IDS_{timestamp}.xlsx'

workbook.save(excel_filename)

print(f"\n✅ FINAL Excel report created: {excel_filename}")
print(f"📋 Contains {len(df)} approved clips with REAL Activity IDs matched from source data")
print(f"🎯 {mapped_count} clips have proper Activity IDs filled in") 