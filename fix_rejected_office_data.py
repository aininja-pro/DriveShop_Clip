#!/usr/bin/env python3
"""
Script to fix the Office column in rejected_clips.csv by fetching Office data from source
"""

import pandas as pd
import requests
import csv
from io import StringIO

def fetch_office_mapping():
    """Fetch WO# -> Office mapping from DriveShop source"""
    print("📥 Fetching Office data from DriveShop source...")
    
    url = "https://reports.driveshop.com/?report=file:/home/deployer/reports/clips/media_loans_without_clips.rpt&init=csv"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    # Parse the CSV data
    lines = response.text.strip().split('\n')
    wo_to_office_mapping = {}
    
    for line in lines:
        if line.strip() and not line.startswith('"Activity_ID"'):  # Skip header
            # Parse CSV line properly (handle quoted fields)
            reader = csv.reader(StringIO(line))
            parts = next(reader)
            if len(parts) >= 12:
                # Position mapping from your data:
                # 1=Activity_ID, 2=Person_ID, 3=Make, 4=Model, 5=WO#, 6=Office, 7=Contact, 8=Media, 9=Start, 10=End, 11=Short, 12=Links
                wo_number = parts[4].strip()  # WO# is in 5th position (index 4)
                office = parts[5].strip()     # Office is in 6th position (index 5)
                wo_to_office_mapping[wo_number] = office
    
    print(f"✅ Created Office mapping for {len(wo_to_office_mapping)} WO# records")
    print(f"📋 Sample mappings: {list(wo_to_office_mapping.items())[:3]}")
    return wo_to_office_mapping

def fix_rejected_office_data():
    """Fix the Office column in rejected_clips.csv"""
    
    # Check if rejected file exists
    rejected_file = 'data/rejected_clips.csv'
    try:
        df = pd.read_csv(rejected_file)
        print(f"📊 Loaded {len(df)} rejected records")
    except FileNotFoundError:
        print("❌ No rejected_clips.csv file found")
        return False
    
    # Get the Office mapping
    wo_to_office = fetch_office_mapping()
    
    # Count how many currently have Office data
    current_office_count = df['Office'].notna().sum() if 'Office' in df.columns else 0
    print(f"📈 Current records with Office data: {current_office_count}/{len(df)}")
    
    # Ensure Office column exists
    if 'Office' not in df.columns:
        df['Office'] = ''
        print("➕ Added Office column")
    
    # Map Office data based on WO#
    df['WO #'] = df['WO #'].astype(str)  # Ensure string type
    df['Office'] = df['WO #'].map(wo_to_office).fillna(df['Office'])
    
    # Count how many now have Office data
    new_office_count = df['Office'].notna().sum()
    print(f"📈 Updated records with Office data: {new_office_count}/{len(df)}")
    print(f"🎯 Improvement: +{new_office_count - current_office_count} records now have Office data")
    
    # Show some examples
    print(f"\n📋 Sample Office assignments:")
    sample_with_office = df[df['Office'].notna() & (df['Office'] != '')].head(3)
    for _, row in sample_with_office.iterrows():
        print(f"   WO# {row['WO #']}: {row['Office']}")
    
    # Save the updated file
    df.to_csv(rejected_file, index=False)
    print(f"💾 Updated {rejected_file} with Office data")
    
    return True

if __name__ == "__main__":
    print("🚀 Fixing Office Data in Rejected Records")
    print("=" * 50)
    
    try:
        success = fix_rejected_office_data()
        if success:
            print("\n✅ SUCCESS: Office data has been added to rejected records!")
            print("🔄 Restart your dashboard to see the updated Office column")
        else:
            print("\n❌ FAILED: Could not fix Office data")
    except Exception as e:
        print(f"❌ Error: {e}") 