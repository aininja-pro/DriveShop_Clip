#!/usr/bin/env python3
import pandas as pd
import sys
import os
from datetime import datetime

# Add the src directory to the path so we can import the function
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import the create_client_excel_report function
from dashboard.app import create_client_excel_report

# Read the approved clips CSV file directly - it has everything!
approved_df = pd.read_csv('data/approved_clips.csv')

print(f"📊 Loaded {len(approved_df)} approved clips from CSV")
print(f"✅ Article_ID (Activity_ID) column present: {'Article_ID' in approved_df.columns}")
print(f"✅ Sample Activity IDs: {approved_df['Article_ID'].head(3).tolist()}")

# Rename the date columns to be more descriptive since they represent different information
if 'Published Date' in approved_df.columns and 'published_date' in approved_df.columns:
    print(f"📅 Renaming date columns for clarity:")
    print(f"   'Published Date' → 'Article Published Date' (when media outlet published)")
    print(f"   'published_date' → 'Loan End Date' (from source data Stop Date)")
    
    approved_df = approved_df.rename(columns={
        'Published Date': 'Article Published Date',
        'published_date': 'Loan End Date'
    })

# Rename Article_ID to Activity_ID for the Excel function
if 'Article_ID' in approved_df.columns:
    approved_df = approved_df.rename(columns={'Article_ID': 'Activity_ID'})
    print(f"✅ Renamed Article_ID to Activity_ID for Excel compatibility")

print(f"📋 Final column count: {len(approved_df.columns)}")
print(f"📋 Key columns: {[col for col in approved_df.columns if 'Date' in col or 'Activity' in col]}")

# Create the Excel report with both the main data and approved data
# Pass approved_df as both parameters since we want the approved clips in both places
workbook = create_client_excel_report(approved_df, approved_df)

# Save the Excel file
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f'DriveShop_FINAL_CORRECT_{timestamp}.xlsx'
workbook.save(filename)

print(f"✅ Excel report generated successfully!")
print(f"📁 File saved as: {filename}")
print(f"📊 Report contains {len(approved_df)} approved clips")
print(f"📋 With proper Activity IDs and clear date column names") 