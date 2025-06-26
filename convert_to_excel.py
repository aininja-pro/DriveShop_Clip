#!/usr/bin/env python3
import pandas as pd
from datetime import datetime

# Read the approved clips CSV
df = pd.read_csv('data/approved_clips.csv')

# Create Excel file with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
excel_filename = f'approved_clips_{timestamp}.xlsx'

# Write to Excel
df.to_excel(excel_filename, index=False, engine='openpyxl')

print(f"✅ Excel file created: {excel_filename}")
print(f"📊 Contains {len(df)} approved clips") 