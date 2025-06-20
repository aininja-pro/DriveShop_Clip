#!/usr/bin/env python3
"""
Script to create Person_ID to Media Outlets mapping from DriveShop reports data
Transforms the raw data into a format suitable for dropdown lookups
"""

import requests
import pandas as pd
import io
from typing import Dict, List
import json

def fetch_driveshop_data():
    """Fetch data from DriveShop reports URL"""
    url = "https://reports.driveshop.com/?report=file:%2Fhome%2Fdeployer%2Freports%2Fclips%2Fmedia_outlet_list.rpt&init=csv&exportreportdataonly=true&columnnames=true"
    
    print("📥 Fetching data from DriveShop reports...")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    # Parse the CSV data
    headers = ["Person_ID", "Reporter_Name", "Outlet_ID", "Outlet_Name", "Outlet_URL", "Circulation"]
    df = pd.read_csv(io.StringIO(response.content.decode('utf-8')), header=None, names=headers)
    
    print(f"✅ Loaded {len(df)} records")
    return df

def create_person_outlets_mapping(df: pd.DataFrame) -> Dict[str, List[Dict]]:
    """
    Transform the data into Person_ID to outlets mapping
    
    Returns:
        Dict where key is Person_ID and value is list of outlet dictionaries
    """
    print("🔧 Creating Person_ID to outlets mapping...")
    
    # Group by Person_ID
    person_outlets = {}
    
    for _, row in df.iterrows():
        person_id = str(row['Person_ID'])
        outlet_info = {
            'outlet_name': row['Outlet_Name'],
            'outlet_url': row['Outlet_URL'],
            'outlet_id': str(row['Outlet_ID']),
            'circulation': row['Circulation']
        }
        
        if person_id not in person_outlets:
            person_outlets[person_id] = []
        
        person_outlets[person_id].append(outlet_info)
    
    print(f"✅ Created mapping for {len(person_outlets)} unique Person_IDs")
    return person_outlets

def save_mapping_files(person_outlets: Dict[str, List[Dict]]):
    """Save the mapping in multiple formats"""
    
    # Create data directory if it doesn't exist
    import os
    os.makedirs('data', exist_ok=True)
    
    # Save as JSON (for easy programmatic access)
    json_file = 'data/person_outlets_mapping.json'
    with open(json_file, 'w') as f:
        json.dump(person_outlets, f, indent=2)
    print(f"💾 Saved JSON mapping to {json_file}")
    
    # Save as CSV (for easy editing/viewing)
    csv_rows = []
    for person_id, outlets in person_outlets.items():
        for outlet in outlets:
            csv_rows.append({
                'Person_ID': person_id,
                'Outlet_Name': outlet['outlet_name'],
                'Outlet_URL': outlet['outlet_url'],
                'Outlet_ID': outlet['outlet_id'],
                'Circulation': outlet['circulation']
            })
    
    csv_df = pd.DataFrame(csv_rows)
    csv_file = 'data/person_outlets_mapping.csv'
    csv_df.to_csv(csv_file, index=False)
    print(f"💾 Saved CSV mapping to {csv_file}")
    
    # Print some statistics
    print(f"\n📊 Mapping Statistics:")
    print(f"   Total Person_IDs: {len(person_outlets)}")
    print(f"   Total outlet relationships: {len(csv_rows)}")
    
    # Show some examples
    print(f"\n📋 Example mappings:")
    for i, (person_id, outlets) in enumerate(list(person_outlets.items())[:3]):
        print(f"   Person_ID {person_id}: {len(outlets)} outlets")
        for outlet in outlets[:2]:  # Show first 2 outlets
            print(f"     - {outlet['outlet_name']} ({outlet['outlet_url']})")
        if len(outlets) > 2:
            print(f"     ... and {len(outlets) - 2} more")

def main():
    """Main function to create the mapping"""
    print("🚀 Creating Person_ID to Media Outlets Mapping")
    print("=" * 50)
    
    try:
        # Fetch the data
        df = fetch_driveshop_data()
        
        # Create the mapping
        person_outlets = create_person_outlets_mapping(df)
        
        # Save the files
        save_mapping_files(person_outlets)
        
        print("\n✅ SUCCESS: Person_ID to Media Outlets mapping created!")
        print("📁 Files saved in data/ directory")
        print("🎯 Ready to use in your AgGrid dropdowns!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main() 