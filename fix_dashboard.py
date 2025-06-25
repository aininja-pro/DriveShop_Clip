#!/usr/bin/env python3
"""
Script to add the missing load_loans_data_for_filtering function to the dashboard.
"""

import re

def add_function_to_dashboard():
    """Add the missing function to the dashboard app."""
    
    # Read the dashboard file
    with open('src/dashboard/app.py', 'r') as f:
        content = f.read()
    
    # Define the function to add
    function_to_add = '''
def load_loans_data_for_filtering(url: str):
    """
    Load loans data from URL for preview and filtering without processing.
    Returns (success: bool, data_info: dict)
    """
    try:
        import requests
        import pandas as pd
        import io
        
        # Download CSV
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Define headers manually for this specific report
        headers = [
            "ActivityID", "Person_ID", "Make", "Model", "WO #", "To", 
            "Affiliation", "Start Date", "Stop Date", "Model Short Name", "Links"
        ]
        
        # Parse CSV
        csv_content = response.content.decode('utf-8')
        df = pd.read_csv(io.StringIO(csv_content), header=None, names=headers, on_bad_lines='warn')
        
        # Clean up column names
        df.columns = [col.strip() for col in df.columns]
        
        # Calculate data info
        data_info = {
            'total_records': len(df),
            'unique_offices': df['Office'].nunique() if 'Office' in df.columns else 0,
            'unique_makes': df['Make'].nunique() if 'Make' in df.columns else 0,
            'unique_person_ids': df['Person_ID'].nunique() if 'Person_ID' in df.columns else 0,
            'sample_data': df.head(5).to_dict('records')  # First 5 records for preview
        }
        
        return True, data_info
        
    except Exception as e:
        return False, {'error': str(e)}

'''
    
    # Find the position to insert the function (before the sidebar section)
    sidebar_marker = "# --- SIDEBAR UI ---"
    
    if sidebar_marker in content:
        # Insert the function before the sidebar section
        new_content = content.replace(sidebar_marker, function_to_add + sidebar_marker)
        
        # Write the updated content back
        with open('src/dashboard/app.py', 'w') as f:
            f.write(new_content)
        
        print("✅ Successfully added load_loans_data_for_filtering function to dashboard")
        return True
    else:
        print("❌ Could not find sidebar marker in dashboard file")
        return False

if __name__ == "__main__":
    add_function_to_dashboard() 