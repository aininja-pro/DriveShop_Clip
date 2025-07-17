# Dashboard Module Documentation

## Module: `src/dashboard/app.py`

### Purpose

The Dashboard module provides a comprehensive Streamlit-based web interface for the DriveShop Clip Tracking System. It serves as the central hub for reviewing, approving, and managing media clips discovered through automated crawling and analysis. The dashboard enables users to process loans without clips, review AI-analyzed content, manage journalist-outlet relationships, and export formatted reports for stakeholders.

### Key Functions/Classes

#### Main Application Function
```python
def main():
    """
    Entry point for the Streamlit dashboard application.
    Handles authentication, UI layout, and orchestrates all dashboard functionality.
    """
```

#### Data Loading Functions
```python
def load_person_outlets_mapping():
    """
    Loads Person_ID to Media Outlets mapping from JSON file.
    Returns: Dict mapping Person_ID to list of outlet data with impressions
    """

def load_loans_data_for_filtering(url: str):
    """
    Fetches and caches loans data from URL for filtering.
    Returns: DataFrame with loan records or None if error
    """
```

#### UI Helper Functions
```python
def apply_custom_sidebar_styling():
    """
    Applies comprehensive black sidebar CSS styling to the Streamlit app.
    Includes hover effects, custom colors, and professional appearance.
    """

def update_progress(current: int, total: int, message: str):
    """
    Updates processing progress in session state.
    Used for real-time progress tracking during batch operations.
    """

def format_time(seconds: float) -> str:
    """
    Formats seconds into human-readable time string.
    Example: 125 seconds -> "2 minutes 5 seconds"
    """
```

#### Data Processing Functions
```python
def create_reporter_name_to_id_mapping(person_outlets_data: dict) -> dict:
    """
    Creates mapping of reporter full names to Person_IDs.
    Handles name variations and duplicates.
    """

def get_outlet_options_for_person(person_id: str, person_outlets_data: dict) -> list:
    """
    Returns list of outlet names associated with a Person_ID.
    Used for dropdown population in the UI.
    """

def parse_url_tracking(wo_tracking: str) -> dict:
    """
    Parses URL tracking data from database JSON string.
    Extracts discovered URLs and their processing status.
    """
```

#### Export Functions
```python
def create_client_excel_report(clips_df: pd.DataFrame, 
                             rejected_df: pd.DataFrame,
                             selected_office: str,
                             selected_makes: list,
                             date_range: tuple) -> BytesIO:
    """
    Creates professional multi-sheet Excel report.
    Includes Executive Summary, Detailed Results, Rejected Loans, and Approved Clips.
    Returns: BytesIO object containing the Excel file
    """
```

#### Database Interaction Functions
```python
def update_person_outlets_mapping_from_url(url: str):
    """
    Updates local person-outlets mapping from remote URL.
    Refreshes both JSON and CSV versions for consistency.
    """
```

### Expected Inputs/Outputs

#### Inputs
1. **Loans Data Source**:
   - Live URL: `https://driveshop.mystagingwebsite.com/reports/media-and-pr/loans-without-clips/download/csv`
   - File Upload: CSV/XLSX files with columns:
     - `Work Order Number`, `First Name`, `Last Name`, `Media Outlet`
     - `Model`, `Start Date`, `End Date`, `Office`, `Make`

2. **User Interactions**:
   - Filter selections (Office, Make, Reporter, Outlet, Date Range)
   - Approval/Rejection checkboxes in AgGrid
   - Media Outlet dropdown selections
   - Byline Author text inputs
   - Sentiment analysis triggers

3. **Configuration Files**:
   - `data/person_outlets_mapping.json`: Journalist-outlet associations
   - Environment variables via `.env` file

#### Outputs
1. **Database Updates**:
   - Clip status updates (approved/rejected)
   - UI state persistence
   - Media outlet associations
   - Byline modifications

2. **Export Files**:
   - **Excel Reports** (.xlsx):
     - Executive Summary sheet
     - Detailed Results sheet
     - Rejected Loans sheet
     - Approved Clips sheet (FMS format)
   - **JSON Files**: Timestamped approved clips data

3. **Visual Feedback**:
   - Processing progress bars
   - Success/error notifications
   - Metrics display (total clips, approved, rejected)
   - Real-time grid updates

### Dependencies

#### External Libraries
```python
# UI Framework
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# Data Processing
import pandas as pd
import numpy as np

# File Handling
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# System & Utilities
import os
import sys
import json
import io
import time
import pickle
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Image Processing
from PIL import Image
```

#### Internal Modules
```python
# Database Operations
from src.utils.database import DatabaseManager

# Logging
from src.utils.logger import get_logger

# Processing Pipeline
from src.ingest.ingest_database import (
    process_loans_batch,
    check_all_youtube_outlets_in_mapping
)

# Analysis
from src.utils.sentiment_analysis import run_sentiment_analysis

# CreatorIQ Integration
from src.creatoriq.scrape_campaign_report import scrape_campaign_report
from src.creatoriq.scrape_post_urls import scrape_posts_for_campaign
```

### Configuration

#### Environment Variables
- `SUPABASE_URL`: Database connection URL
- `SUPABASE_KEY`: Database authentication key
- `STREAMLIT_PASSWORD`: Dashboard access password
- `DATABASE_PASSWORD`: PostgreSQL password

#### Session State Management
```python
# Tracking Sets
st.session_state.viewed_records = set()      # Viewed WO numbers
st.session_state.approved_records = set()    # Approved WO numbers
st.session_state.rejected_records = set()    # Rejected WO numbers

# Data Storage
st.session_state.last_saved_outlets = {}     # Media outlet selections
st.session_state.last_saved_bylines = {}     # Byline author edits
st.session_state.outlet_data_mapping = {}    # Full outlet data

# Processing State
st.session_state.processing_progress = {...}  # Progress tracking
st.session_state.loans_data_loaded = False   # Data load flag
st.session_state.batch_info = {...}          # Batch processing info
```

### Error Handling

- Database connection failures handled with user-friendly messages
- File upload validation with size and format checks
- API rate limiting with exponential backoff
- Graceful degradation when external services unavailable
- Comprehensive logging for debugging

### Performance Considerations

- Caching implemented for expensive operations (`@st.cache_data`)
- Batch processing for large datasets
- Pagination support in AgGrid for large result sets
- Optimized database queries with proper indexing
- Lazy loading for media outlet data

### Security

- Password protection for dashboard access
- Environment-based configuration (no hardcoded secrets)
- SQL injection prevention through parameterized queries
- XSS protection in user input handling
- Secure file upload with validation