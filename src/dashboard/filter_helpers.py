"""
Helper functions for the filtering functionality in the dashboard.
"""

import os
import requests
import pandas as pd
import io
import streamlit as st
from pathlib import Path

def load_loans_data_for_filtering(url: str):
    """
    Load loans data from URL for preview and filtering without processing.
    Returns (success: bool, data_info: dict)
    """
    try:
        # Download CSV
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Define headers manually for this specific report
        headers = [
            "ArticleID", "Person_ID", "Make", "Model", "WO #", "To", 
            "Affiliation", "Start Date", "Stop Date", "Office", "Links"
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

def run_ingest_concurrent_with_filters(url: str, filters: dict):
    """
    Run ingestion with filters applied.
    This is a wrapper around the backend function.
    """
    try:
        # Import the backend function
        from src.ingest.ingest import run_ingest_concurrent_with_filters as backend_filter_function
        return backend_filter_function(url=url, filters=filters)
    except ImportError:
        # Fallback to basic function if advanced filtering not implemented
        from src.ingest.ingest import run_ingest_concurrent
        st.warning("Advanced filtering not available, using basic processing")
        limit = filters.get('limit')
        return run_ingest_concurrent(url=url, limit=limit) 