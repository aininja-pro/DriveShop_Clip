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

# Read the most recent approved clips JSON file (your last 4-hour run)
with open('data/approved_clips_20250626_000635.json', 'r') as f:
    approved_data = json.load(f)

# Convert to DataFrame
df = pd.DataFrame(approved_data)

print(f"📊 Loaded {len(df)} approved clips from your last run")

# Generate the beautiful formatted Excel report for just this run
workbook = create_client_excel_report(df)

# Save with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
excel_filename = f'DriveShop_LastRun_44clips_{timestamp}.xlsx'

workbook.save(excel_filename)

print(f"✅ Beautiful formatted Excel report created: {excel_filename}")
print(f"📋 Contains your last 4-hour run with {len(df)} approved clips")
print(f"🎨 Professional formatting with Executive Summary, Detailed Results, and Rejected Loans tabs") 