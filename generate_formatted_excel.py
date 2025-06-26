#!/usr/bin/env python3
import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime

# Add the src directory to the path so we can import the function
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import the create_client_excel_report function
from dashboard.app import create_client_excel_report

# Read the approved clips data
df = pd.read_csv('data/approved_clips.csv')

print(f"📊 Loaded {len(df)} approved clips")

# Generate the beautiful formatted Excel report
workbook = create_client_excel_report(df)

# Save with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
excel_filename = f'DriveShop_Report_{timestamp}.xlsx'

workbook.save(excel_filename)

print(f"✅ Beautiful formatted Excel report created: {excel_filename}")
print(f"📋 Contains Executive Summary, Detailed Results, and Rejected Loans tabs")
print(f"🎨 Professional formatting with clickable URLs and styled headers") 