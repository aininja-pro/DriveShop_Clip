import streamlit as st
import pandas as pd
import os
import sys
from pathlib import Path
from datetime import datetime
import time
import json
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, DataReturnMode, GridUpdateMode
from src.utils.logger import logger
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
import requests

# Add explicit .env loading with debug output
from dotenv import load_dotenv
from PIL import Image

# Determine the location of the .env file
# Check both the current directory and project root
possible_env_paths = [
    '.env',                                       # Current directory
    os.path.join(os.path.dirname(__file__), '.env'),  # Same dir as this file
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'),  # Project root
]

env_loaded = False
for env_path in possible_env_paths:
    if os.path.exists(env_path):
        print(f"Loading .env file from: {env_path}")
        load_dotenv(env_path)
        env_loaded = True
        break

if not env_loaded:
    print("WARNING: No .env file found!")

# Debug: Print loaded environment variables (without exposing full API keys)
openai_key = os.environ.get('OPENAI_API_KEY', '')
slack_webhook = os.environ.get('SLACK_WEBHOOK_URL', '')
print(f"OPENAI_API_KEY loaded: {'Yes (starts with ' + openai_key[:5] + '...)' if openai_key else 'No'}")
print(f"SLACK_WEBHOOK_URL loaded: {'Yes' if slack_webhook else 'No'}")

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import local modules
try:
    from src.ingest.ingest_database import run_ingest_database, run_ingest_database_with_filters
    from src.utils.database import get_database
except ImportError:
    # Define a stub for when the module is not yet implemented
    def run_ingest_database(file_path):
        st.error("Database ingest module not implemented yet")
        return False
    def run_ingest_database_with_filters(url, filters):
        st.error("Database ingest with filters module not implemented yet")
        return False
    def get_database():
        st.error("Database module not available")
        return None

def load_person_outlets_mapping():
    """Load Person_ID to Media Outlets mapping from JSON file"""
    try:
        mapping_file = os.path.join(project_root, "data", "person_outlets_mapping.json")
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r') as f:
                mapping = json.load(f)
            print(f"✅ Loaded Person_ID mapping with {len(mapping)} unique Person_IDs")
            return mapping
        else:
            print("⚠️ Person_ID mapping file not found")
            return {}
    except Exception as e:
        print(f"❌ Error loading Person_ID mapping: {e}")
        return {}

def get_outlet_options_for_person(person_id, mapping):
    """Get list of outlet names for a given Person_ID"""
    if not person_id or not mapping:
        return []
    
    person_id_str = str(person_id)
    if person_id_str in mapping:
        # FIX: Correctly access the nested 'outlets' list
        person_data = mapping.get(person_id_str, {})
        outlets_list = person_data.get('outlets', [])
        return [outlet['outlet_name'] for outlet in outlets_list]
    return []

@st.cache_data
def create_reporter_name_to_id_mapping():
    """Create a mapping from Reporter Name to Person_ID for lookups."""
    try:
        mapping_file = os.path.join(project_root, "data", "person_outlets_mapping.csv")
        if not os.path.exists(mapping_file):
            return {}
        
        df = pd.read_csv(mapping_file)
        # Ensure correct types
        df['Reporter_Name'] = df['Reporter_Name'].astype(str)
        df['Person_ID'] = df['Person_ID'].astype(str)
        
        # Create a dictionary from the two columns, dropping duplicates
        # In case a name is associated with multiple IDs, this takes the first one.
        # NORMALIZE names to handle spacing and case variations
        df['Reporter_Name_Normalized'] = df['Reporter_Name'].str.strip().str.replace(r'\s+', ' ', regex=True).str.title()
        name_to_id_map = df.drop_duplicates('Reporter_Name_Normalized').set_index('Reporter_Name_Normalized')['Person_ID'].to_dict()
        print(f"✅ Created Reporter Name to Person_ID mapping for {len(name_to_id_map)} reporters.")
        return name_to_id_map
    except Exception as e:
        print(f"❌ Error creating reporter name to ID mapping: {e}")
        return {}

def load_loans_data_for_filtering(url: str):
    """
    Load loans data from URL for preview and filtering without processing.
    Returns (success: bool, df: pd.DataFrame, data_info: dict)
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        headers = [
            "ActivityID", "Person_ID", "Make", "Model", "WO #", "Office", "To", 
            "Affiliation", "Start Date", "Stop Date", "Model Short Name", "Links"
        ]
        
        csv_content = response.content.decode('utf-8')
        df = pd.read_csv(io.StringIO(csv_content), header=None, names=headers, on_bad_lines='warn')
        
        df.columns = [col.strip() for col in df.columns]

        total_records = len(df)
        offices_count = df['Office'].nunique() if 'Office' in df.columns else 0
        makes_count = df['Make'].nunique() if 'Make' in df.columns else 0

        data_info = {
            "total_records": total_records,
            "offices_count": offices_count,
            "makes_count": makes_count
        }
        return True, df, data_info
    except Exception as e:
        st.error(f"Failed to load loans data: {e}")
        return False, None, {"error": str(e)}

# Load environment variables
def load_env():
    """Load environment variables from .env file"""
    from dotenv import load_dotenv
    load_dotenv()
    return os.environ.get("STREAMLIT_PASSWORD", "password")

# Helper function to parse URL tracking data
def parse_url_tracking(df_row):
    """Parse URL tracking data from the backend to show multiple URL information"""
    try:
        # Check if URL_Tracking column exists and has data
        if 'URL_Tracking' in df_row and pd.notna(df_row['URL_Tracking']):
            # Try to parse as JSON if it's a string
            if isinstance(df_row['URL_Tracking'], str):
                url_tracking_str = df_row['URL_Tracking']
                
                # Handle Python-style single quotes by converting to valid JSON
                # Replace single quotes with double quotes, but be careful about quotes inside strings
                try:
                    # First try direct JSON parsing (in case it's already valid JSON)
                    url_tracking = json.loads(url_tracking_str)
                except json.JSONDecodeError:
                    # If that fails, try using Python's eval (safe since it's our own data)
                    # This handles Python-style single quotes
                    url_tracking = eval(url_tracking_str)
            else:
                url_tracking = df_row['URL_Tracking']
            
            return url_tracking
        else:
            # Fallback: infer from available data
            urls_processed = df_row.get('URLs_Processed', 1)
            urls_successful = df_row.get('URLs_Successful', 1)
            
            # Create a simple tracking structure
            return [{
                'original_url': df_row.get('Links', df_row.get('Clip URL', '')),
                'actual_url': df_row.get('Clip URL', ''),
                'success': True,
                'relevance_score': df_row.get('Relevance Score', 0),
                'content_type': 'inferred'
            }]
    except Exception as e:
        # If parsing fails, return basic structure
        return [{
            'original_url': df_row.get('Links', df_row.get('Clip URL', '')),
            'actual_url': df_row.get('Clip URL', ''),
            'success': True,
            'relevance_score': df_row.get('Relevance Score', 0),
            'content_type': 'inferred'
        }]


# Custom CSS for black sidebar with logo
def apply_custom_sidebar_styling():
    """Apply custom CSS styling for black sidebar with white logo"""
    st.markdown("""
    <style>
    /* Black sidebar styling */
    .css-1d391kg, .css-1lcbmhc, .css-17lntkn, .css-1y4p8pa, 
    .stSidebar > div:first-child, .css-12oz5g7, .css-1cypcdb {
        background-color: #000000 !important;
    }
    
    /* Sidebar content styling */
    .stSidebar {
        background-color: #000000 !important;
    }
    
    /* All text in sidebar to white */
    .stSidebar * {
        color: white !important;
    }
    
    /* Sidebar headers and labels */
    .stSidebar .stMarkdown h1,
    .stSidebar .stMarkdown h2, 
    .stSidebar .stMarkdown h3,
    .stSidebar .stMarkdown h4,
    .stSidebar .stMarkdown h5,
    .stSidebar .stMarkdown h6 {
        color: white !important;
        font-weight: 600;
    }
    
    /* Sidebar radio buttons and selectbox text */
    .stSidebar .stRadio label,
    .stSidebar .stSelectbox label,
    .stSidebar .stMultiSelect label,
    .stSidebar .stTextInput label,
    .stSidebar .stNumberInput label {
        color: white !important;
        font-weight: 500;
    }
    
    /* Radio button options */
    .stSidebar .stRadio > div > div > div > label {
        color: white !important;
    }
    
    /* Selectbox dropdown styling */
    .stSidebar .stSelectbox > div > div {
        background-color: #1a1a1a !important;
        border: 1px solid #333333 !important;
        color: white !important;
    }
    
    /* Fix input text colors - make text dark in input fields */
    .stSidebar .stTextInput > div > div > input {
        color: #000000 !important;
        background-color: white !important;
    }
    
    .stSidebar .stNumberInput > div > div > input {
        color: #000000 !important;
        background-color: white !important;
    }
    
    .stSidebar .stSelectbox > div > div > div {
        color: #000000 !important;
        background-color: white !important;
    }
    
    /* Dropdown options styling */
    .stSidebar .stSelectbox option {
        color: #000000 !important;
        background-color: white !important;
    }
    
    /* Fix all input elements in sidebar */
    .stSidebar input {
        color: #000000 !important;
        background-color: white !important;
    }
    
    /* Simple fix for number input buttons */
    .stSidebar button {
        color: #000000 !important;
        font-weight: bold !important;
    }
    
    /* Fix multiselect and other input types */
    .stSidebar .stMultiSelect > div > div > div {
        color: #000000 !important;
        background-color: white !important;
    }
    
    /* Ensure placeholder text is visible */
    .stSidebar input::placeholder {
        color: #6c757d !important;
    }
    
    /* Fix text area if any */
    .stSidebar textarea {
        color: #2c3e50 !important;
        background-color: white !important;
    }
    
    /* Fix file uploader visibility */
    .stSidebar .stFileUploader {
        color: white !important;
    }
    
    .stSidebar .stFileUploader label {
        color: white !important;
        font-weight: 500;
    }
    
    .stSidebar .stFileUploader > div {
        background-color: white !important;
        border: 2px dashed #000000 !important;
        border-radius: 6px !important;
    }
    
    .stSidebar .stFileUploader > div > div {
        color: #000000 !important;
        font-weight: 600 !important;
    }
    
    .stSidebar .stFileUploader button {
        color: white !important;
        background-color: #000000 !important;
        border: 1px solid #000000 !important;
        font-weight: 600 !important;
        padding: 8px 16px !important;
        border-radius: 4px !important;
    }
    
    .stSidebar .stFileUploader button:hover {
        background-color: #333333 !important;
        border-color: #333333 !important;
    }
    
    /* Fix file uploader text and button visibility - make text darker */
    .stSidebar .stFileUploader span,
    .stSidebar .stFileUploader p,
    .stSidebar .stFileUploader div[data-testid="stFileUploaderDropzone"] {
        color: #000000 !important;
        font-weight: 600 !important;
        font-size: 14px !important;
    }
    
    .stSidebar .stFileUploader div[data-testid="stFileUploaderDropzone"] span {
        color: #000000 !important;
        font-weight: 500 !important;
    }
    
    /* Make drag and drop text more visible */
    .stSidebar .stFileUploader div[data-testid="stFileUploaderDropzone"] p {
        color: #000000 !important;
        font-weight: 600 !important;
        margin: 0 !important;
    }
    
    /* Button styling in sidebar - LIGHT BLUE BUTTONS with DARK TEXT for visibility */
    .stSidebar .stButton > button {
        background-color: #e3f2fd !important;
        color: #1565c0 !important;
        border: 2px solid #90caf9 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.15) !important;
        padding: 12px 16px !important;
        min-height: 44px !important;
        width: 100% !important;
        text-align: center !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    
    .stSidebar .stButton > button:hover {
        background-color: #bbdefb !important;
        color: #0d47a1 !important;
        border-color: #64b5f6 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.25) !important;
    }
    
    /* Force dark blue text on all sidebar buttons - override any inherited styles */
    .stSidebar .stButton > button * {
        color: #1565c0 !important;
    }
    
    .stSidebar .stButton > button span {
        color: #1565c0 !important;
    }
    
    .stSidebar .stButton > button:hover * {
        color: #0d47a1 !important;
    }
    
    .stSidebar .stButton > button:hover span {
        color: #0d47a1 !important;
    }
    
    /* Logo container styling */
    .sidebar-logo {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 1rem 0 2rem 0;
        margin-bottom: 1rem;
        border-bottom: 1px solid #333333;
    }
    
    .sidebar-logo img {
        max-width: 180px;
        height: auto;
        filter: brightness(1.1);
    }
    
    /* Style Streamlit's image component in sidebar */
    .stSidebar .stImage {
        display: flex;
        justify-content: center;
        padding: 1rem 0 2rem 0;
        margin-bottom: 1rem;
        border-bottom: 1px solid #333333;
    }
    
    .stSidebar .stImage img {
        filter: brightness(1.1);
        border-radius: 4px;
    }
    
    /* Sidebar metrics styling */
    .stSidebar .metric-container {
        background-color: #1a1a1a !important;
        padding: 0.5rem;
        border-radius: 6px;
        margin: 0.5rem 0;
        border: 1px solid #333333;
    }
    
    /* Fix for any remaining black text */
    .stSidebar p, .stSidebar span, .stSidebar div {
        color: white !important;
    }
    
    /* Tab styling adjustments for better contrast with black sidebar */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #f8f9fa;
        border-radius: 6px 6px 0 0;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #000000;
        color: white;
    }
    
    /* 1) Invert / restore visibility of number-input spinners in WebKit browsers */
    .stSidebar input[type="number"]::-webkit-inner-spin-button,
    .stSidebar input[type="number"]::-webkit-outer-spin-button {
        -webkit-appearance: initial !important;
        filter: invert(1) contrast(200%) !important;
        opacity: 1 !important;
    }

    /* 2) Firefox: turn numbers back into textfields (hides native arrows) */
    .stSidebar input[type="number"] {
        -moz-appearance: textfield !important;
    }

    /* 3) Add a visible border around inputs so they don't vanish on white */
    .stSidebar .stTextInput > div > div > input,
    .stSidebar .stNumberInput > div > div > input {
        border: 1px solid #333333 !important;
        border-radius: 4px !important;
        padding: 4px 8px !important;
    }

    /* 4) Make the file-uploader icon and emoji darker so it shows on charcoal */
    .stSidebar .stFileUploader div[data-testid="stFileUploaderDropzone"] svg {
        filter: brightness(0) invert(1) !important;
        width: 1.2rem !important; height: 1.2rem !important;
    }

    /* 5) Tidy up any stray SVGs or emojis inside buttons */
    .stSidebar .stButton > button svg,
    .stSidebar .stButton > button {
        filter: none !important;
        color: white !important;
    }
    
    /* --- Always show +/– on number inputs --- */
    .stSidebar input[type="number"]::-webkit-inner-spin-button,
    .stSidebar input[type="number"]::-webkit-outer-spin-button {
      /* Make sure they're rendered as controls */
      -webkit-appearance: inner-spin-button !important;
      display: block !important;
      opacity: 1 !important;
      visibility: visible !important;
      pointer-events: auto !important;
      width: 1.2em !important;
      height: 1.2em !important;
    }

    /* Firefox fallback — revert to textfield so at least you can type */
    .stSidebar input[type="number"] {
      -moz-appearance: textfield !important;
    }

    /* Tidy up the outline and border so you can see the control region */
    .stSidebar .stNumberInput > div > div > input {
      border: 1px solid #333333 !important;
      padding-right: 1.6em !important;  /* leave room for the spinner */
      border-radius: 4px !important;
      background-clip: padding-box !important;
    }
    
    /* ALWAYS VISIBLE & DARKENED steppers */
    .stSidebar input[type="number"]::-webkit-inner-spin-button,
    .stSidebar input[type="number"]::-webkit-outer-spin-button {
      /* treat them as real controls */
      -webkit-appearance: inner-spin-button !important;
      display: block !important;
      visibility: visible !important;
      opacity: 1 !important;
      pointer-events: auto !important;

      /* tint them dark */
      filter: brightness(0%) contrast(100%) !important;
    }

    /* Firefox fallback — hide arrows, let user type */
    .stSidebar input[type="number"] {
      -moz-appearance: textfield !important;
    }
    
    /* Compact table area */
    .ag-theme-alpine {
        font-size: 0.8rem !important;
    }
    
    /* Sticky Action Bar for Bulk Review */
    .sticky-action-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: linear-gradient(135deg, #000000 0%, #2c3e50 100%);
        padding: 0.8rem 1rem;
        box-shadow: 0 -4px 20px rgba(0,0,0,0.3);
        border-top: 2px solid #333;
        z-index: 1000;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 1rem;
    }
    
    .sticky-action-bar .stButton > button {
        background: linear-gradient(135deg, #000000 0%, #333333 100%) !important;
        color: white !important;
        border: 2px solid #444 !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
        min-width: 140px !important;
    }
    
    .sticky-action-bar .stButton > button:hover {
        background: linear-gradient(135deg, #333333 0%, #555555 100%) !important;
        border-color: #666 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
    }
    
    /* Add bottom padding to main content to prevent overlap */
    .main .block-container {
        padding-bottom: 5rem !important;
    }
    
    /* Target ALL metric text elements but keep READABLE */
    div[data-testid="metric-container"] > div,
    div[data-testid="metric-container"] span,
    div[data-testid="metric-container"] p,
    [data-testid="metric-container"] * {
        font-size: 0.9rem !important;
        line-height: 1.2 !important;
        margin: 0.1rem 0 !important;
        padding: 0 !important;
    }
    
    /* Force label text to be small but readable */
    div[data-testid="metric-container"] > div:first-child,
    [data-testid="metric-container"] [data-testid="metric-label"],
    .metric-label {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        color: #6c757d !important;
        margin-bottom: 0.15rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.3px !important;
        line-height: 1.1 !important;
    }
    
    /* Force value text to be bigger and VISIBLE */
    div[data-testid="metric-container"] > div:last-child,
    [data-testid="metric-container"] [data-testid="metric-value"],
    .metric-value {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        line-height: 1.2 !important;
        color: #2c3e50 !important;
    }
    
    /* Override Streamlit's default metric styling */
    .stMetric {
        padding: 0.15rem !important;
        margin: 0.15rem !important;
        height: auto !important;
        min-height: 2.5rem !important;
    }
    
    .stMetric > div {
        font-size: 0.9rem !important;
        line-height: 1.2 !important;
    }
    
    /* Nuclear option - target by text content if needed */
    div:contains("Total Clips"),
    div:contains("Avg Score"), 
    div:contains("High Quality"),
    div:contains("Approved") {
        font-size: 0.1rem !important;
    }
    
    /* Table row styling */
    .table-row {
        padding: 6px 4px;
        min-height: 1.8rem;
        display: flex;
        align-items: center;
        text-align: center;
        font-size: 0.7rem;
        line-height: 1.2;
    }
    
    /* URL popup styling */
    .url-popup {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.375rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .url-item {
        padding: 0.25rem 0;
        border-bottom: 1px solid #e9ecef;
    }
    
    .url-item:last-child {
        border-bottom: none;
    }
    
    /* Better button targeting - all buttons in action columns */
    div[data-testid="column"]:last-child div[data-testid="stButton"]:nth-child(1) button {
        background: #28a745 !important;
        color: white !important;
        border: none !important;
        border-radius: 4px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        padding: 3px 12px !important;
        height: 1.8rem !important;
    }
    
    div[data-testid="column"]:last-child div[data-testid="stButton"]:nth-child(3) button {
        background: #dc3545 !important;
        color: white !important;
        border: none !important;
        border-radius: 4px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        padding: 3px 12px !important;
        height: 1.8rem !important;
    }
    
    /* More aggressive targeting for all checkmark buttons */
    button:contains("✓") {
        background-color: #28a745 !important;
        color: white !important;
    }
    
    /* More aggressive targeting for all X buttons */
    button:contains("✗") {
        background-color: #dc3545 !important;
        color: white !important;
    }
    
    /* Universal button override */
    .stButton button {
        font-size: 12px !important;
        font-weight: 600 !important;
        padding: 3px 12px !important;
        border: none !important;
        border-radius: 4px !important;
        height: 1.8rem !important;
    }
    
    /* Score color styling */
    .score-high { color: #28a745; font-weight: 600; }
    .score-med { color: #007bff; font-weight: 600; }
    .score-low { color: #ffc107; font-weight: 600; }
    
    /* Scrollable table styling */
    .scrollable-table {
        max-height: 450px;
        overflow-y: auto;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        background: white;
    }
    
    .fixed-header {
        position: sticky;
        top: 0;
        z-index: 100;
        background: white;
        border-bottom: 2px solid #adb5bd;
        padding: 0.2rem 0;
    }
    
    /* Smooth scrolling */
    .scrollable-table::-webkit-scrollbar {
        width: 8px;
    }
    
    .scrollable-table::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    
    .scrollable-table::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 4px;
    }
    
    .scrollable-table::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
    }
    
    /* Compact sidebar styling */
    .css-1d391kg {
        width: 250px !important;
        min-width: 250px !important;
    }
    
    /* Make sidebar content more compact */
    .css-1d391kg .stMarkdown p {
        margin: 0.2rem 0 !important;
        font-size: 0.9rem !important;
    }
    
    .css-1d391kg .stButton button {
        padding: 0.3rem 0.5rem !important;
        font-size: 0.8rem !important;
        margin: 0.1rem 0 !important;
    }
    
    .css-1d391kg .stFileUploader {
        margin: 0.2rem 0 !important;
    }
    
    .css-1d391kg .stFileUploader > div {
        padding: 0.3rem !important;
        font-size: 0.8rem !important;
    }
    
    /* Compact success/error messages in sidebar */
    .css-1d391kg .stAlert {
        padding: 0.3rem !important;
        font-size: 0.8rem !important;
        margin: 0.2rem 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

def create_client_excel_report(df, approved_df=None):
    """Create a professional Excel report for client presentation"""
    
    # Handle empty DataFrame case
    if df is None or df.empty:
        st.warning("⚠️ No data available to create Excel report. Please process some loans first.")
        # Return a minimal workbook with just headers
        wb = Workbook()
        wb.remove(wb.active)
        summary_ws = wb.create_sheet("No Data Available")
        summary_ws.append(["No clips found", "Please process loans first"])
        return wb
    
    # Create workbook with multiple sheets
    wb = Workbook()
    
    # Remove default sheet
    wb.remove(wb.active)
    
    # 1. Executive Summary Sheet
    summary_ws = wb.create_sheet("Executive Summary")
    
    # Header styling
    header_font = Font(bold=True, size=14, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    
    # Summary metrics (using Bulk Review column names)
    clips_found = len(df)  # This is the successful clips count
    relevance_col = 'Relevance Score' if 'Relevance Score' in df.columns else 'Relevance'
    
    # Try to get total original records by checking for rejected clips file
    try:
        import os
        project_root = Path(__file__).parent.parent.parent
        rejected_file = os.path.join(project_root, "data", "rejected_clips.csv")
        if os.path.exists(rejected_file):
            rejected_df = pd.read_csv(rejected_file)
            clips_not_found = len(rejected_df)
        else:
            rejected_df = None
            clips_not_found = 0
    except:
        rejected_df = None
        clips_not_found = 0
    
    # Calculate total records
    total_records = clips_found + clips_not_found
    
    # Other metrics
    avg_relevance = df[relevance_col].mean() if relevance_col in df.columns and len(df) > 0 else 0
    high_quality = len(df[df[relevance_col] >= 8]) if relevance_col in df.columns else 0
    positive_sentiment = len(df[df['Sentiment'] == 'positive']) if 'Sentiment' in df.columns else 0
    
    # Add summary data
    summary_data = [
        ["DriveShop Media Monitoring Report", ""],
        ["Report Generated", datetime.now().strftime("%B %d, %Y at %I:%M %p")],
        ["", ""],
        ["EXECUTIVE SUMMARY", ""],
        ["Total Records Processed", total_records],
        ["Clips Found", clips_found],
        ["Not Found/Rejected", clips_not_found],
        ["Success Rate", f"{(clips_found/total_records*100):.1f}%" if total_records > 0 else "0%"],
        ["", ""],
        ["QUALITY METRICS", ""],
        ["Average Relevance Score", f"{avg_relevance:.1f}/10"],
        ["High Quality Clips (8+)", high_quality],
        ["Positive Sentiment", positive_sentiment]
    ]
    
    for row_idx, row_data in enumerate(summary_data, 1):
        for col_idx, value in enumerate(row_data, 1):
            cell = summary_ws.cell(row=row_idx, column=col_idx, value=value)
            if row_idx == 1:  # Title row
                cell.font = Font(bold=True, size=16, color="366092")
            elif row_idx == 4 or (isinstance(value, str) and value.isupper()):  # Section headers
                cell.font = Font(bold=True, size=12, color="366092")
    
    # Auto-size columns
    for col in summary_ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        summary_ws.column_dimensions[column].width = adjusted_width
    
    # 2. Detailed Results Sheet
    results_ws = wb.create_sheet("Detailed Results")
    
    # Use the same column names as Bulk Review (exclude Approve/Reject columns)
    # Include Activity_ID for approval workflow even though it's not visible in UI
    bulk_review_columns = [
        'Activity_ID', 'Office', 'WO #', 'Make', 'Model', 'Contact', 'Media Outlet', 
        'URL', 'Relevance', 'Sentiment'
    ]
    
    # Map our data columns to Bulk Review column names
    column_mapping = {
        'Activity_ID': 'Activity_ID',  # Activity_ID column exists but may be empty
        'Office': 'Office',
        'WO #': 'WO #',
        'Make': 'Make',
        'Model': 'Model',
        'To': 'Contact',
        'Affiliation': 'Media Outlet',
        'Clip URL': 'URL',  # Add the primary URL from the View column
        'Relevance Score': 'Relevance',
        'Overall Sentiment': 'Sentiment',  # Fix: Use the correct sentiment column
    }
    
    # FIX: Fetch Activity_ID values from external source if they're blank in the data
    activity_id_mapping = {}
    try:
        import requests
        response = requests.get("https://reports.driveshop.com/?report=file:/home/deployer/reports/clips/media_loans_without_clips.rpt&init=csv", timeout=30)
        if response.status_code == 200:
            source_lines = response.text.strip().split('\n')
            for line in source_lines:
                if line.strip() and not line.startswith('"Activity_ID"'):  # Skip header
                    # Parse CSV line properly (handle quoted fields)
                    import csv
                    from io import StringIO
                    reader = csv.reader(StringIO(line))
                    parts = next(reader)
                    if len(parts) >= 5:
                        # Position mapping: Activity_ID(1st), Person_ID(2nd), Make(3rd), Model(4th), WO#(5th), ...
                        activity_id = parts[0].strip()  # Activity_ID is in 1st position
                        wo_number = parts[4].strip()    # WO# is in 5th position
                        activity_id_mapping[wo_number] = activity_id
        print(f"✅ Fetched Activity_ID mapping for {len(activity_id_mapping)} WO# records")
    except Exception as e:
        print(f"Warning: Could not fetch Activity_ID mapping: {e}")
    
    # Create export dataframe with Bulk Review column structure
    export_df = pd.DataFrame()
    
    for bulk_col in bulk_review_columns:
        # Find the corresponding column in our data
        source_col = None
        for data_col, bulk_name in column_mapping.items():
            if bulk_name == bulk_col and data_col in df.columns:
                source_col = data_col
                break
        
        if source_col:
            if bulk_col == 'Activity_ID' and activity_id_mapping:
                # FIX: Populate Activity_ID from external mapping using WO#
                export_df[bulk_col] = df['WO #'].astype(str).map(activity_id_mapping).fillna(df[source_col])
            else:
                export_df[bulk_col] = df[source_col]
        else:
            # Fill with empty if column doesn't exist
            export_df[bulk_col] = ''
    
    # Add header row
    headers = list(export_df.columns)
    results_ws.append(headers)
    
    # Add data rows with clickable URLs and formatted sentiment
    for idx, row in export_df.iterrows():
        row_data = []
        for col_idx, (col_name, value) in enumerate(row.items()):
            # Format sentiment with abbreviations and emojis
            if col_name == 'Sentiment' and value:
                sentiment_map = {
                    'positive': 'POS 😊',
                    'negative': 'NEG 😞',
                    'neutral': 'NEU 😐',
                    'pos': 'POS 😊',
                    'neg': 'NEG 😞', 
                    'neu': 'NEU 😐'
                }
                # Clean the value and try multiple formats
                cleaned_value = str(value).lower().strip()
                formatted_value = sentiment_map.get(cleaned_value, f"{cleaned_value} 😐")
                row_data.append(formatted_value)

            else:
                row_data.append(value)
        results_ws.append(row_data)
    
    # Style the header row
    for cell in results_ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Make URLs clickable and style data rows
    from openpyxl.styles import Font as XLFont
    url_font = XLFont(color="0000FF", underline="single")
    
    for row_idx in range(2, results_ws.max_row + 1):  # Start from row 2 (after header)
        for col_idx, col_name in enumerate(headers, 1):
            cell = results_ws.cell(row=row_idx, column=col_idx)
            
            # Make URLs clickable
            if col_name == 'URL' and cell.value and str(cell.value).startswith(('http://', 'https://')):
                cell.hyperlink = str(cell.value)
                cell.font = url_font

    
    # Auto-size columns
    for col in results_ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        results_ws.column_dimensions[column].width = adjusted_width
    
    # 3. Rejected Loans Sheet (if rejected data is available)
    if rejected_df is not None and len(rejected_df) > 0:
        rejected_ws = wb.create_sheet("Rejected Loans")
        
        # Define columns for rejected loans report
        rejected_columns = [
            'WO #', 'Model', 'Contact', 'Media Outlet', 'Rejection Reason', 'URLs Searched', 'Details'
        ]
        
        # Create rejected export dataframe
        rejected_export_df = pd.DataFrame()
        
        # Map rejected data to export columns
        rejected_export_df['WO #'] = rejected_df['WO #']
        rejected_export_df['Model'] = rejected_df['Model']
        rejected_export_df['Contact'] = rejected_df['To']
        rejected_export_df['Media Outlet'] = rejected_df['Affiliation']
        rejected_export_df['Rejection Reason'] = rejected_df['Rejection_Reason']
        
        # Extract the actual URLs from the URL_Details field
        def extract_urls_from_details(url_details):
            """Extract just the URLs from the detailed rejection info"""
            if pd.isna(url_details) or not url_details:
                return "No URLs processed"
            
            urls = []
            # Split by semicolon and extract URLs
            for detail in str(url_details).split(';'):
                detail = detail.strip()
                if detail.startswith(('http://', 'https://')):
                    # Find the colon that separates URL from description (not the :// in https)
                    # Look for ": " (colon followed by space) which indicates the description starts
                    if ': ' in detail:
                        url_part = detail.split(': ')[0].strip()
                        urls.append(url_part)
                    else:
                        # If no description separator found, take the whole thing as URL
                        urls.append(detail)
            
            return '\n'.join(urls) if urls else "No URLs found"
        
        rejected_export_df['URLs Searched'] = rejected_df['URL_Details'].apply(extract_urls_from_details)
        rejected_export_df['Details'] = rejected_df['URL_Details']
        
        # Add header row
        rejected_headers = list(rejected_export_df.columns)
        rejected_ws.append(rejected_headers)
        
        # Add data rows
        for idx, row in rejected_export_df.iterrows():
            row_data = []
            for col_name, value in row.items():
                # Handle URL columns by making them clickable if they contain URLs
                if col_name == 'URLs Searched' and value and 'http' in str(value):
                    row_data.append(str(value))
                else:
                    row_data.append(value)
            rejected_ws.append(row_data)
        
        # Style the header row with a red theme for rejected items
        rejected_header_fill = PatternFill(start_color="dc3545", end_color="dc3545", fill_type="solid")
        for cell in rejected_ws[1]:
            cell.font = header_font
            cell.fill = rejected_header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Make URLs clickable in the URLs Searched column
        urls_searched_col_idx = rejected_headers.index('URLs Searched') + 1
        for row_idx in range(2, rejected_ws.max_row + 1):
            cell = rejected_ws.cell(row=row_idx, column=urls_searched_col_idx)
            if cell.value and 'http' in str(cell.value):
                urls_text = str(cell.value)
                # Check if there are multiple URLs (newline separated)
                if '\n' in urls_text:
                    # Multiple URLs - make text blue and add line breaks for readability
                    cell.font = XLFont(color="0000FF")
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                    # For the first URL, we can still make it a hyperlink
                    first_url = urls_text.split('\n')[0].strip()
                    if first_url.startswith(('http://', 'https://')):
                        cell.hyperlink = first_url
                        cell.font = url_font
                else:
                    # Single URL can be a hyperlink
                    url = urls_text.strip()
                    if url.startswith(('http://', 'https://')):
                        cell.hyperlink = url
                        cell.font = url_font
        
        # Auto-size columns for rejected sheet
        for col in rejected_ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 80)  # Wider for rejection details
            rejected_ws.column_dimensions[column].width = adjusted_width
    
    # 4. Approved Clips Sheet (filter to match current dataset only)
    if approved_df is not None and len(approved_df) > 0:
        # Filter approved clips to only include WO #s that exist in the current detailed results
        current_wo_numbers = set(df['WO #'].astype(str))
        current_approved_df = approved_df[approved_df['WO #'].astype(str).isin(current_wo_numbers)].copy()
        
        if not current_approved_df.empty:
            # FIX: Get actual loan end dates AND Activity_IDs from source data for Excel
            source_mapping = {}
            activity_id_mapping = {}
            try:
                import requests
                response = requests.get("https://reports.driveshop.com/?report=file:/home/deployer/reports/clips/media_loans_without_clips.rpt&init=csv", timeout=30)
                if response.status_code == 200:
                    source_lines = response.text.strip().split('\n')
                    for line in source_lines:
                        if line.strip() and not line.startswith('"Activity_ID"'):  # Skip header
                            # Parse CSV line properly (handle quoted fields)
                            import csv
                            from io import StringIO
                            reader = csv.reader(StringIO(line))
                            parts = next(reader)
                            if len(parts) >= 10:
                                # Position mapping: Activity_ID(1st), Person_ID(2nd), Make(3rd), Model(4th), WO#(5th), ..., Stop_Date(10th)
                                activity_id = parts[0].strip()  # Activity_ID is in 1st position
                                wo_number = parts[4].strip()    # WO# is in 5th position
                                stop_date = parts[9].strip()    # Stop Date is in 10th position
                                source_mapping[wo_number] = stop_date
                                activity_id_mapping[wo_number] = activity_id
                print(f"✅ Fetched source data mapping for {len(source_mapping)} WO# records")
            except Exception as e:
                print(f"Warning: Could not fetch source data for loan end dates and Activity_IDs: {e}")
            
            # FIX: Populate Activity_ID from external source data using WO# mapping
            if activity_id_mapping:
                current_approved_df['Activity_ID'] = current_approved_df['WO #'].astype(str).map(activity_id_mapping)
            elif 'Article_ID' in current_approved_df.columns:
                current_approved_df['Activity_ID'] = current_approved_df['Article_ID']
                current_approved_df.drop('Article_ID', axis=1, inplace=True)
            elif 'Activity_ID' not in current_approved_df.columns:
                # If neither exists, create empty Activity_ID column
                current_approved_df['Activity_ID'] = ''
            
            # FIX: Clean up date columns - keep only ONE published date and add loan end date
            # Remove the confusing 'published_date' column (it's not the loan end date)
            if 'published_date' in current_approved_df.columns:
                current_approved_df.drop('published_date', axis=1, inplace=True)
            
            # Add actual loan end dates from source data
            current_approved_df['Loan End Date'] = current_approved_df['WO #'].astype(str).map(source_mapping).fillna('')
            
            # Rename the Published Date column to be clear about what it is
            column_renames = {}
            if 'Published Date' in current_approved_df.columns:
                column_renames['Published Date'] = 'Article Published Date'
            
            if column_renames:
                current_approved_df.rename(columns=column_renames, inplace=True)
            
            # Move Activity_ID to first column
            if 'Activity_ID' in current_approved_df.columns:
                cols = current_approved_df.columns.tolist()
                cols.remove('Activity_ID')
                current_approved_df = current_approved_df[['Activity_ID'] + cols]
            
            # Create Approved Clips sheet using openpyxl syntax (not xlsxwriter)
            approved_sheet = wb.create_sheet('Approved Clips')
            
            # Write headers with openpyxl formatting (using already imported Font)
            header_font = Font(bold=True, size=12, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            
            for col_num, header in enumerate(current_approved_df.columns, 1):
                cell = approved_sheet.cell(row=1, column=col_num, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
            
            # Write data using openpyxl
            url_font = Font(color="0000FF", underline="single")
            
            for row_num, (_, row_data) in enumerate(current_approved_df.iterrows(), 2):  # Start from row 2
                for col_num, value in enumerate(row_data, 1):
                    cell = approved_sheet.cell(row=row_num, column=col_num)
                    
                    if pd.isna(value):
                        cell.value = ''
                    elif isinstance(value, (int, float)):
                        cell.value = value
                    else:
                        # Handle URLs with hyperlinks
                        str_value = str(value)
                        if str_value.startswith(('http://', 'https://')):
                            cell.value = str_value
                            cell.hyperlink = str_value
                            cell.font = url_font
                        else:
                            cell.value = str_value
            
            # Auto-size columns
            for col in approved_sheet.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                approved_sheet.column_dimensions[column].width = adjusted_width
    
    return wb

# Initialize session state for popup management
if 'show_url_popup' not in st.session_state:
    st.session_state.show_url_popup = False
if 'popup_data' not in st.session_state:
    st.session_state.popup_data = {}

# Page configuration
st.set_page_config(
    page_title="DriveShop Clip Tracking",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom dark charcoal sidebar styling
apply_custom_sidebar_styling()

# Add logo to sidebar
with st.sidebar:
    # DriveShop Logo at the top - use Streamlit's built-in image display
    try:
        # Debug current working directory
        print(f"Current working directory: {os.getcwd()}")
        print(f"Project root: {project_root}")
        
        # Try multiple possible paths
        possible_paths = [
            os.path.join(project_root, "assets", "DriveShop_WebLogo.png"),
            "assets/DriveShop_WebLogo.png",
            "./assets/DriveShop_WebLogo.png",
            "DriveShop_WebLogo.png"
        ]
        
        logo_loaded = False
        for logo_path in possible_paths:
            print(f"Trying logo path: {logo_path}")
            print(f"Path exists: {os.path.exists(logo_path)}")
            if os.path.exists(logo_path):
                try:
                    logo = Image.open(logo_path)
                    st.image(logo, width=180)
                    print(f"✅ Logo loaded successfully from: {logo_path}")
                    logo_loaded = True
                    break
                except Exception as img_error:
                    print(f"❌ Failed to load image from {logo_path}: {img_error}")
                    continue
        
        if not logo_loaded:
            print("❌ No logo paths worked, using text fallback")
            st.markdown("**DriveShop**")
            
    except Exception as e:
        print(f"Logo loading error: {e}")
        st.markdown("**DriveShop**")

# DEVELOPMENT MODE: Skip password check
# Main application
st.title("DriveShop Clip Tracking Dashboard")

# Custom CSS for better styling
st.markdown("""
<style>
    /* ULTRA COMPACT layout - maximum table space */
    .main > div {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
        padding-top: 0.5rem !important;
    }
    
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        max-width: 100% !important;
    }
    
    /* Compact main title */
    h1 {
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        line-height: 1.2 !important;
        margin-bottom: 0.3rem !important;
        margin-top: 0 !important;
        padding: 0 !important;
        color: #1a1a1a !important;
    }
    
    /* Ensure title container has space */
    .stApp > header {
        background-color: transparent;
    }
    
    /* Compact table header styling */
    .clip-table-header {
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        color: #5a6c7d !important;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        background-color: #f8f9fa;
        padding: 0.4rem 0.3rem;
        border-bottom: 2px solid #adb5bd;
        text-align: center;
    }
    
    /* ULTRA COMPACT metrics */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa !important;
        border: 1px solid #e9ecef !important;
        padding: 0.2rem 0.3rem !important;
        border-radius: 0.2rem !important;
        margin: 0.1rem 0 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        height: auto !important;
        min-height: 2rem !important;
        max-height: 2.5rem !important;
    }
    
    /* Compact tabs */
    .stTabs {
        margin: 0.2rem 0 !important;
    }
    
    .stTabs > div > div > div > div {
        padding: 0.3rem 0.8rem !important;
        font-size: 0.9rem !important;
    }
    
    /* Remove excessive margins everywhere */
    .element-container {
        margin: 0.2rem 0 !important;
    }
    
    /* Compact columns */
    .row-widget {
        margin: 0.1rem 0 !important;
    }
    
    /* Remove divider spacing */
    hr {
        margin: 0.3rem 0 !important;
    }
    
    /* Make everything more compact */
    .stMarkdown {
        margin: 0.1rem 0 !important;
    }
    
    /* Compact table area */
    .ag-theme-alpine {
        font-size: 0.8rem !important;
    }
    
    /* Sticky Action Bar for Bulk Review */
    .sticky-action-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: linear-gradient(135deg, #000000 0%, #2c3e50 100%);
        padding: 0.8rem 1rem;
        box-shadow: 0 -4px 20px rgba(0,0,0,0.3);
        border-top: 2px solid #333;
        z-index: 1000;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 1rem;
    }
    
    .sticky-action-bar .stButton > button {
        background: linear-gradient(135deg, #000000 0%, #333333 100%) !important;
        color: white !important;
        border: 2px solid #444 !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
        min-width: 140px !important;
    }
    
    .sticky-action-bar .stButton > button:hover {
        background: linear-gradient(135deg, #333333 0%, #555555 100%) !important;
        border-color: #666 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
    }
    
    /* Add bottom padding to main content to prevent overlap */
    .main .block-container {
        padding-bottom: 5rem !important;
    }
    
    /* Target ALL metric text elements but keep READABLE */
    div[data-testid="metric-container"] > div,
    div[data-testid="metric-container"] span,
    div[data-testid="metric-container"] p,
    [data-testid="metric-container"] * {
        font-size: 0.9rem !important;
        line-height: 1.2 !important;
        margin: 0.1rem 0 !important;
        padding: 0 !important;
    }
    
    /* Force label text to be small but readable */
    div[data-testid="metric-container"] > div:first-child,
    [data-testid="metric-container"] [data-testid="metric-label"],
    .metric-label {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        color: #6c757d !important;
        margin-bottom: 0.15rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.3px !important;
        line-height: 1.1 !important;
    }
    
    /* Force value text to be bigger and VISIBLE */
    div[data-testid="metric-container"] > div:last-child,
    [data-testid="metric-container"] [data-testid="metric-value"],
    .metric-value {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        line-height: 1.2 !important;
        color: #2c3e50 !important;
    }
    
    /* Override Streamlit's default metric styling */
    .stMetric {
        padding: 0.15rem !important;
        margin: 0.15rem !important;
        height: auto !important;
        min-height: 2.5rem !important;
    }
    
    .stMetric > div {
        font-size: 0.9rem !important;
        line-height: 1.2 !important;
    }
    
    /* Nuclear option - target by text content if needed */
    div:contains("Total Clips"),
    div:contains("Avg Score"), 
    div:contains("High Quality"),
    div:contains("Approved") {
        font-size: 0.1rem !important;
    }
    
    /* Table row styling */
    .table-row {
        padding: 6px 4px;
        min-height: 1.8rem;
        display: flex;
        align-items: center;
        text-align: center;
        font-size: 0.7rem;
        line-height: 1.2;
    }
    
    /* URL popup styling */
    .url-popup {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.375rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .url-item {
        padding: 0.25rem 0;
        border-bottom: 1px solid #e9ecef;
    }
    
    .url-item:last-child {
        border-bottom: none;
    }
    
    /* Better button targeting - all buttons in action columns */
    div[data-testid="column"]:last-child div[data-testid="stButton"]:nth-child(1) button {
        background: #28a745 !important;
        color: white !important;
        border: none !important;
        border-radius: 4px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        padding: 3px 12px !important;
        height: 1.8rem !important;
    }
    
    div[data-testid="column"]:last-child div[data-testid="stButton"]:nth-child(3) button {
        background: #dc3545 !important;
        color: white !important;
        border: none !important;
        border-radius: 4px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        padding: 3px 12px !important;
        height: 1.8rem !important;
    }
    
    /* More aggressive targeting for all checkmark buttons */
    button:contains("✓") {
        background-color: #28a745 !important;
        color: white !important;
    }
    
    /* More aggressive targeting for all X buttons */
    button:contains("✗") {
        background-color: #dc3545 !important;
        color: white !important;
    }
    
    /* Universal button override */
    .stButton button {
        font-size: 12px !important;
        font-weight: 600 !important;
        padding: 3px 12px !important;
        border: none !important;
        border-radius: 4px !important;
        height: 1.8rem !important;
    }
    
    /* Score color styling */
    .score-high { color: #28a745; font-weight: 600; }
    .score-med { color: #007bff; font-weight: 600; }
    .score-low { color: #ffc107; font-weight: 600; }
    
    /* Scrollable table styling */
    .scrollable-table {
        max-height: 450px;
        overflow-y: auto;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        background: white;
    }
    
    .fixed-header {
        position: sticky;
        top: 0;
        z-index: 100;
        background: white;
        border-bottom: 2px solid #adb5bd;
        padding: 0.2rem 0;
    }
    
    /* Smooth scrolling */
    .scrollable-table::-webkit-scrollbar {
        width: 8px;
    }
    
    .scrollable-table::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    
    .scrollable-table::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 4px;
    }
    
    .scrollable-table::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
    }
    
    /* Compact sidebar styling */
    .css-1d391kg {
        width: 250px !important;
        min-width: 250px !important;
    }
    
    /* Make sidebar content more compact */
    .css-1d391kg .stMarkdown p {
        margin: 0.2rem 0 !important;
        font-size: 0.9rem !important;
    }
    
    .css-1d391kg .stButton button {
        padding: 0.3rem 0.5rem !important;
        font-size: 0.8rem !important;
        margin: 0.1rem 0 !important;
    }
    
    .css-1d391kg .stFileUploader {
        margin: 0.2rem 0 !important;
    }
    
    .css-1d391kg .stFileUploader > div {
        padding: 0.3rem !important;
        font-size: 0.8rem !important;
    }
    
    /* Compact success/error messages in sidebar */
    .css-1d391kg .stAlert {
        padding: 0.3rem !important;
        font-size: 0.8rem !important;
        margin: 0.2rem 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- MAPPING UPDATE FEATURE (SIDEBAR) ---
def update_person_outlets_mapping_from_url(url):
    """
    Download the mapping CSV from the given URL, validate, save, and regenerate the JSON mapping file.
    Returns (success: bool, message: str)
    """
    import requests
    import pandas as pd
    import json
    import os
    try:
        # Download CSV
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        csv_content = resp.content.decode('utf-8')

        # Define headers manually, as the source CSV doesn't contain them
        headers = ["Person_ID", "Reporter_Name", "Outlet_ID", "Outlet_Name", "Outlet_URL", "Impressions"]
        
        # Parse CSV without reading a header row and assign our defined headers
        df = pd.read_csv(io.StringIO(csv_content), header=None, names=headers)
        
        # Validate that the DataFrame now has the correct columns
        required_cols = {'Person_ID', 'Reporter_Name', 'Outlet_Name', 'Outlet_URL', 'Outlet_ID', 'Impressions'}
        if not required_cols.issubset(set(df.columns)):
            return False, f"Internal Error: Failed to assign correct columns. Please check the function."

        # Save CSV
        csv_path = os.path.join(project_root, 'data', 'person_outlets_mapping.csv')
        df.to_csv(csv_path, index=False)
        # Regenerate JSON mapping
        person_outlets = {}
        for _, row in df.iterrows():
            person_id = str(row['Person_ID'])
            reporter_name = str(row['Reporter_Name'])
            outlet_info = {
                'outlet_name': row['Outlet_Name'],
                'outlet_url': row['Outlet_URL'],
                'outlet_id': str(row['Outlet_ID']),
                'impressions': row['Impressions']
            }
            if person_id not in person_outlets:
                person_outlets[person_id] = {
                    'reporter_name': reporter_name,
                    'outlets': []
                }
            person_outlets[person_id]['outlets'].append(outlet_info)
        json_path = os.path.join(project_root, 'data', 'person_outlets_mapping.json')
        with open(json_path, 'w') as f:
            json.dump(person_outlets, f, indent=2)
        return True, f"Mapping updated successfully! {len(person_outlets)} Person_IDs, {len(df)} outlet relationships."
    except Exception as e:
        return False, f"Error updating mapping: {e}"

# --- SIDEBAR UI ---
with st.sidebar:
    # Display mapping update message if it exists in session state
    if 'mapping_update_msg' in st.session_state:
        success, msg = st.session_state.mapping_update_msg
        if success:
            st.success(msg)
        else:
            st.error(msg)
        # Clear the message after displaying it
        del st.session_state.mapping_update_msg

    st.markdown("**🔄 Update Person-Outlets Mapping**")
    default_mapping_url = "https://reports.driveshop.com/?report-file=/home/deploys/creatoriq-reports/45805/driveshop_media_outlet_list.csv"
    mapping_url = st.text_input(
        "Paste mapping CSV URL here:",
        value=default_mapping_url,
        help="Paste the direct link to the latest mapping CSV."
    )
    if st.button("Update Mapping", use_container_width=True):
        with st.spinner("Updating mapping from URL..."):
            success, msg = update_person_outlets_mapping_from_url(mapping_url)
            st.session_state.mapping_update_msg = (success, msg)
            st.rerun()

    # Thin separator line
    st.markdown('<hr style="margin: 1rem 0; border: none; height: 1px; background-color: #666666;">', unsafe_allow_html=True)
    
    st.markdown("### Process Loans from Live URL")
    
    loans_url = st.text_input(
        "Live 'Loans without Clips' URL:",
        "https://reports.driveshop.com/?report=file:/home/deployer/reports/clips/media_loans_without_clips.rpt&init=csv"
    )
    
    st.markdown("### Filters")

    # This input is now the first filter for a clearer workflow.
    limit_records = st.number_input(
        "Limit records to process (0 for all):",
        min_value=0,
        value=0,  # Default to 0, which means "All"
        step=1,
        help="Set the maximum number of records to process from the filtered set. Set to 0 to process all."
    )
    
    offices = ['All Offices']
    makes = ['All Makes']
    reporter_names = ['All Reporters']
    outlets = ['All Outlets']
    name_to_id_map = create_reporter_name_to_id_mapping()

    if 'loans_data_loaded' in st.session_state and st.session_state.loans_data_loaded:
        df = st.session_state.get('loaded_loans_df')
        if df is not None:
            if 'Office' in df.columns:
                offices += sorted(df['Office'].dropna().astype(str).unique().tolist())
            if 'Make' in df.columns:
                makes += sorted(df['Make'].dropna().astype(str).unique().tolist())
    
    mapping_file = os.path.join(project_root, "data", "person_outlets_mapping.csv")
    if os.path.exists(mapping_file):
        try:
            mapping_df = pd.read_csv(mapping_file)
            if 'Reporter_Name' in mapping_df.columns:
                reporter_names += sorted(mapping_df['Reporter_Name'].dropna().unique().tolist())
            if 'Outlet_Name' in mapping_df.columns:
                outlets += sorted(mapping_df['Outlet_Name'].dropna().unique().tolist())
        except Exception as e:
            st.warning(f"Could not load reporter/outlet names: {e}")

    selected_office = st.selectbox("Filter by Office:", offices)
    selected_make = st.selectbox("Filter by Make:", makes)
    selected_reporter_name = st.selectbox("Filter by Reporter:", reporter_names)
    selected_outlet = st.selectbox("Filter by Media Outlet:", outlets)
    
    # Add WO # and Activity ID filters with multiple value support
    wo_number_filter = st.text_input(
        "Filter by WO # (optional):",
        value="",
        help="Enter Work Order number(s). Use commas to separate multiple values (e.g., 1182796,1182884,1182887)"
    )
    
    activity_id_filter = st.text_input(
        "Filter by Activity ID (optional):",
        value="",
        help="Enter Activity ID(s). Use commas to separate multiple values (e.g., 1114558,1114646,1114649)"
    )
    
    # Show batch processing info if available
    suggested_value = ""
    if 'batch_info' in st.session_state:
        info = st.session_state.batch_info
        st.success(f"""
        **📊 Last Batch Completed at {info['timestamp']}:**
        - **Last Activity ID:** {info['last_processed_id']}
        - **Records Processed:** {info['records_processed']}
        - **Completed At:** {info['timestamp']}
        """)
        
        # Add a button to auto-fill the next Activity ID
        if st.button("📋 Use Suggested ID for Next Batch", key="use_suggested_id", help="Auto-fill the suggested Activity ID"):
            st.session_state.suggested_id_to_use = info['next_suggested_id']
            st.rerun()
        
        # Check if we should use the suggested value
        if 'suggested_id_to_use' in st.session_state:
            suggested_value = st.session_state.suggested_id_to_use
            del st.session_state.suggested_id_to_use
    
    # Position-based filter for batch processing (much simpler!)
    skip_records = st.number_input(
        "Skip first X records (optional):",
        min_value=0,
        value=0,
        step=1,
        help="Enter number of records to skip from the beginning. For example, enter 200 to start processing from record 201."
    )

    if 'loans_data_loaded' in st.session_state and st.session_state.loans_data_loaded:
        filtered_df = st.session_state.loaded_loans_df.copy()
        
        if selected_office != 'All Offices':
            filtered_df = filtered_df[filtered_df['Office'] == selected_office]
        
        if selected_make != 'All Makes':
            filtered_df = filtered_df[filtered_df['Make'] == selected_make]
        
        if selected_reporter_name != 'All Reporters':
            person_id = name_to_id_map.get(selected_reporter_name)
            if person_id:
                # This includes the fix for the Person_ID data type issue
                filtered_df['Person_ID'] = pd.to_numeric(filtered_df['Person_ID'], errors='coerce').astype('Int64').astype(str)
                filtered_df = filtered_df[filtered_df['Person_ID'] == person_id]
        
        # Apply WO # filter if specified (supports multiple comma-separated values)
        if wo_number_filter.strip():
            if 'WO #' in filtered_df.columns:
                # Parse comma-separated values and clean them
                wo_numbers = [wo.strip() for wo in wo_number_filter.split(',') if wo.strip()]
                filtered_df = filtered_df[filtered_df['WO #'].astype(str).isin(wo_numbers)]
                st.info(f"🎯 Filtering by {len(wo_numbers)} WO #(s): {', '.join(wo_numbers)}")
            else:
                st.warning("⚠️ WO # column not found in data")
        
        # Apply Activity ID filter if specified (supports multiple comma-separated values)
        if activity_id_filter.strip():
            if 'Activity_ID' in filtered_df.columns:
                # Parse comma-separated values and clean them
                activity_ids = [aid.strip() for aid in activity_id_filter.split(',') if aid.strip()]
                filtered_df = filtered_df[filtered_df['Activity_ID'].astype(str).isin(activity_ids)]
                st.info(f"🎯 Filtering by {len(activity_ids)} Activity ID(s): {', '.join(activity_ids)}")
            else:
                st.warning("⚠️ Activity_ID column not found in data")
        
        # Apply position-based filtering (skip first X records)
        if skip_records > 0:
            if skip_records < len(filtered_df):
                filtered_df = filtered_df.iloc[skip_records:].reset_index(drop=True)
                st.info(f"📍 Skipping first {skip_records} records, starting from position {skip_records + 1}")
            else:
                st.warning(f"Skip value ({skip_records}) is greater than available records ({len(filtered_df)}). Processing all records.")
        
        # Clarify how many records will be processed based on filters and the limit
        num_filtered = len(filtered_df)
        limit_text = f"Up to {limit_records} of these will be processed." if limit_records > 0 else "All of these will be processed."
        st.info(f"**{num_filtered}** records match your filters. {limit_text}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Load Data", key='load_data_for_filtering'):
            with st.spinner("Loading data from URL..."):
                success, df, data_info = load_loans_data_for_filtering(loans_url)
                if success:
                    st.session_state.loans_data_loaded = True
                    st.session_state.loaded_loans_df = df
                    st.session_state.loans_data_info = data_info
                    st.success(f"✅ Loaded {data_info['total_records']} records. Ready to filter.")
                    st.rerun()
                else:
                    st.error("❌ Failed to load data.")
    
    with col2:
        if st.button("Process Filtered", key='process_from_url_filtered'):
            # Only proceed if data has been loaded and filtered
            if 'filtered_df' in locals() and not filtered_df.empty:
                with st.spinner(f"Processing filtered records... This may take a while."):
                    from src.ingest.ingest_database import run_ingest_database_with_filters
                    
                    # Convert filtered dataframe to list of records
                    records_to_process = filtered_df.to_dict('records')

                    # FIX: Remap dataframe columns to the format the backend expects
                    remapped_records = []
                    for record in records_to_process:
                        # Split the 'Links' string into a list of URLs
                        urls = []
                        if 'Links' in record and pd.notna(record['Links']):
                            urls = [url.strip() for url in str(record['Links']).split(',') if url.strip()]

                        remapped_records.append({
                            'work_order': record.get('WO #'),
                            'model': record.get('Model'),
                            'to': record.get('To'),
                            'affiliation': record.get('Affiliation'),
                            'urls': urls,
                            'start_date': record.get('Start Date'),
                            'make': record.get('Make'),
                            'activity_id': record.get('ActivityID'),  # FIXED: Use ActivityID (no underscore) - this is the actual column name in source data
                            'person_id': record.get('Person_ID'),
                            'office': record.get('Office')
                        })
                    
                    # Add a debug expander to show exactly what's being sent
                    with st.expander("DEBUG: Data sent to backend"):
                        st.json(remapped_records)

                    # Call the backend with the pre-filtered and correctly mapped data
                    success = run_ingest_database_with_filters(
                        filtered_loans=remapped_records, 
                        limit=limit_records
                    )
                    
                    if success:
                        # Store batch processing info for next batch suggestion
                        if remapped_records:
                            # Get the last Activity ID from the processed records
                            processed_activity_ids = [r.get('activity_id') for r in remapped_records if r.get('activity_id')]
                            if processed_activity_ids:
                                last_processed_id = processed_activity_ids[-1]
                                
                                # Find the next Activity ID in the original data for batch suggestion
                                original_df = st.session_state.loaded_loans_df
                                if 'Activity_ID' in original_df.columns:
                                    # Convert to numeric and sort to find next ID
                                    original_df_sorted = original_df.copy()
                                    original_df_sorted['Activity_ID_numeric'] = pd.to_numeric(original_df_sorted['Activity_ID'], errors='coerce')
                                    original_df_sorted = original_df_sorted.dropna(subset=['Activity_ID_numeric']).sort_values('Activity_ID_numeric')
                                    
                                    # Find the next ID after the last processed one
                                    last_processed_numeric = pd.to_numeric(last_processed_id, errors='coerce')
                                    next_ids = original_df_sorted[original_df_sorted['Activity_ID_numeric'] > last_processed_numeric]['Activity_ID']
                                    
                                    if not next_ids.empty:
                                        next_suggested_id = str(int(next_ids.iloc[0]))
                                        st.session_state.batch_info = {
                                            'last_processed_id': str(last_processed_id),
                                            'next_suggested_id': next_suggested_id,
                                            'records_processed': len(remapped_records),
                                            'timestamp': datetime.now().strftime("%H:%M:%S")
                                        }
                        
                        st.session_state.last_run_timestamp = datetime.now()
                        st.rerun()
                    else:
                        st.error("❌ Filtered processing failed.")
            else:
                st.warning("No data loaded or no records match filters. Please load data first.")
            
    if 'loans_data_loaded' in st.session_state and st.session_state.loans_data_loaded:
        info = st.session_state.get('loans_data_info', {})
        st.markdown(f"📊 Data loaded: **{info.get('total_records', 0)}** total records, **{info.get('offices_count', 0)}** offices, **{info.get('makes_count', 0)}** makes")

    # Thin separator line
    st.markdown('<hr style="margin: 1rem 0; border: none; height: 1px; background-color: #666666;">', unsafe_allow_html=True)
    
    st.markdown("**📁 Process from File Upload**")
    uploaded_file = st.file_uploader("Upload Loans CSV/XLSX", type=['csv', 'xlsx'], label_visibility="collapsed")
    
    if uploaded_file is not None:
        temp_file_path = os.path.join(project_root, "data", "fixtures", "temp_upload.csv")
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        if st.button("Process Uploaded File", use_container_width=True):
            with st.spinner("Processing..."):
                success = run_ingest_database(input_file=temp_file_path)
                if success:
                    st.success("✅ Done!")
                    st.rerun() # Refresh the page
                else:
                    st.error("❌ Failed")
    
    # Thin separator line
    st.markdown('<hr style="margin: 1rem 0; border: none; height: 1px; background-color: #666666;">', unsafe_allow_html=True)

    if st.button("🔄 Process Default File (for testing)", use_container_width=True):
        with st.spinner("Processing default file..."):
            default_file = os.path.join(project_root, "data", "fixtures", "Loans_without_Clips.csv")
            success = run_ingest_database(input_file=default_file)
            if success:
                st.success("✅ Done!")
                st.rerun() # Refresh the page
            else:
                st.error("❌ Failed")

# Create tabs for different user workflows  
bulk_review_tab, approved_queue_tab, rejected_tab, analysis_tab, creatoriq_tab, history_tab = st.tabs([
    "📋 Bulk Review", 
    "✅ Approved Queue",
    "⚠️ Rejected/Issues", 
    "📊 Detailed Analysis", 
    "🎬 CreatorIQ Export",
    "📚 File History"
])

# ========== CREATORIQ TAB ==========
with creatoriq_tab:
    # Import CreatorIQ modules
    try:
        from src.creatoriq import playwright_scraper, parser, exporter
        
        # Compact header styling
        st.markdown("### 🎬 CreatorIQ Scraper")
        st.markdown("Extract social media post URLs from CreatorIQ campaign reports")
        
        # Input section with tight layout
        col1, col2 = st.columns([3, 1])
        
        with col1:
            url = st.text_input(
                "CreatorIQ Report URL:",
                placeholder="https://report.driveshop.com/report/audi_media_spotl-dcMIG3Mp5APt/posts",
                help="Paste the CreatorIQ campaign report URL here"
            )
        
        with col2:
            scrolls = st.slider("Scroll cycles:", 5, 50, 20, help="Number of scroll cycles to load all posts")
        
        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            scrape_button = st.button("🚀 Scrape", use_container_width=True)
        
        with col2:
            if st.button("📋 Clear", use_container_width=True):
                if 'creatoriq_urls' in st.session_state:
                    del st.session_state.creatoriq_urls
                if 'creatoriq_export_path' in st.session_state:
                    del st.session_state.creatoriq_export_path
                st.rerun()
        
        # Scraping logic
        if scrape_button:
            if url:
                with st.spinner("🔄 Scraping CreatorIQ... this may take 1-3 minutes."):
                    try:
                        # Get HTML content and API responses with network interception
                        html, api_responses = playwright_scraper.get_creatoriq_data(url, scrolls=scrolls)
                        
                        # Extract URLs using both HTML and captured API responses
                        urls = parser.extract_social_urls(html, api_responses)
                        
                        # Store in session state
                        st.session_state.creatoriq_urls = urls
                        
                        # Create export directory
                        os.makedirs("data/creatoriq_exports", exist_ok=True)
                        export_path = f"data/creatoriq_exports/creatoriq_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        
                        # Export to CSV
                        exporter.export_to_csv(urls, export_path)
                        st.session_state.creatoriq_export_path = export_path
                        
                        st.success(f"✅ Extraction complete: {len(urls)} URLs found")
                        
                    except Exception as e:
                        st.error(f"❌ Error during scraping: {str(e)}")
            else:
                st.warning("⚠️ Please enter a valid CreatorIQ report URL")
        
        # Results display
        if 'creatoriq_urls' in st.session_state and st.session_state.creatoriq_urls:
            urls = st.session_state.creatoriq_urls
            
            # Metrics row
            col1, col2, col3, col4 = st.columns(4)
            
            # Count URLs by platform
            platform_counts = {}
            for url in urls:
                if 'instagram.com' in url:
                    platform_counts['Instagram'] = platform_counts.get('Instagram', 0) + 1
                elif 'tiktok.com' in url:
                    platform_counts['TikTok'] = platform_counts.get('TikTok', 0) + 1
                elif 'youtube.com' in url:
                    platform_counts['YouTube'] = platform_counts.get('YouTube', 0) + 1
                elif 'twitter.com' in url:
                    platform_counts['Twitter'] = platform_counts.get('Twitter', 0) + 1
                elif 'facebook.com' in url:
                    platform_counts['Facebook'] = platform_counts.get('Facebook', 0) + 1
            
            with col1:
                st.metric("Total URLs", len(urls))
            with col2:
                st.metric("Instagram", platform_counts.get('Instagram', 0))
            with col3:
                st.metric("TikTok", platform_counts.get('TikTok', 0))
            with col4:
                st.metric("YouTube", platform_counts.get('YouTube', 0))
            
            # Create DataFrame for AgGrid display
            data = []
            for i, url in enumerate(urls, 1):
                platform = exporter.get_platform(url)
                data.append({
                    "#": i,
                    "Platform": platform,
                    "Post URL": url,
                    "Creator": "",  # Will be extracted later
                    "Status": "✅ Found"
                })
            
            df = pd.DataFrame(data)
            
            # Create proper cellRenderer for clickable URLs (same as Bulk Review)
            cellRenderer_url = JsCode("""
            class UrlCellRenderer {
              init(params) {
                this.eGui = document.createElement('a');
                this.eGui.innerText = '🔗 View';
                this.eGui.href = params.value;
                this.eGui.target = '_blank';
                this.eGui.style.color = '#1f77b4';
                this.eGui.style.textDecoration = 'underline';
                this.eGui.style.cursor = 'pointer';
              }

              getGui() {
                return this.eGui;
              }

              refresh(params) {
                return false;
              }
            }
            """)
            
            # Configure AgGrid with EXACT same settings as Bulk Review
            gb = GridOptionsBuilder.from_dataframe(df)
            
            # *** ADVANCED FEATURES WITH SET FILTERS (CHECKBOXES) ***
            gb.configure_side_bar()  # Enable filtering sidebar
            gb.configure_default_column(
                filter="agSetColumnFilter",  # CHECKBOX FILTERS with search
                sortable=True,  # Enable sorting
                resizable=True,  # Enable column resizing
                editable=False, 
                groupable=True, 
                value=True, 
                enableRowGroup=True, 
                enablePivot=True, 
                enableValue=True,
                filterParams={
                    "buttons": ["reset", "apply"],
                    "closeOnApply": True,
                    "newRowsAction": "keep"
                }
            )
            
            # Configure columns with proper widths and features
            gb.configure_column("#", width=60, pinned="left")
            gb.configure_column("Platform", width=120, pinned="left")
            gb.configure_column("Post URL", 
                cellRenderer=cellRenderer_url,
                width=100,
                sortable=False,
                filter=False
            )
            gb.configure_column("Creator", width=150)
            gb.configure_column("Status", width=100)
            
            # Configure selection
            gb.configure_selection(selection_mode="multiple", use_checkbox=False)
            
            gridOptions = gb.build()
            
            # Display table with EXACT same AgGrid call as Bulk Review
            st.markdown("#### 📊 Extracted URLs")
            selected_rows = AgGrid(
                df,
                gridOptions=gridOptions,
                allow_unsafe_jscode=True,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                height=650,  # Same height as Bulk Review
                fit_columns_on_grid_load=True,
                theme="alpine",
                enable_enterprise_modules=True  # REQUIRED for Set Filters with checkboxes
            )
            
            # Download section
            if 'creatoriq_export_path' in st.session_state:
                export_path = st.session_state.creatoriq_export_path
                
                if os.path.exists(export_path):
                    with open(export_path, 'rb') as f:
                        csv_data = f.read()
                    
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv_data,
                        file_name=f"creatoriq_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
        
        # Help section
        with st.expander("ℹ️ How to use CreatorIQ Scraper"):
            st.markdown("""
            **Steps:**
            1. **Get URL**: Copy the CreatorIQ campaign report URL (must end with `/posts`)
            2. **Adjust Scrolls**: Set scroll cycles (20 is usually enough for 500+ posts)
            3. **Scrape**: Click 'Scrape' and wait 1-3 minutes for completion
            4. **Review**: Check the extracted URLs in the table below
            5. **Download**: Export the results as CSV for further analysis
            
            **Supported Platforms:**
            - Instagram (profiles and posts)
            - TikTok (videos)
            - YouTube (videos)
            - Twitter (posts)
            - Facebook (posts)
            
            **Note**: The scraper extracts post URLs only. Creator names and engagement metrics will be added in future versions.
            """)
    
    except ImportError as e:
        st.error(f"❌ CreatorIQ module not available: {str(e)}")
        st.info("Please ensure the CreatorIQ module is properly installed.")

# ========== BULK REVIEW TAB (Compact Interface) ==========
with bulk_review_tab:
    
    # Initialize session state for viewed records tracking
    if 'viewed_records' not in st.session_state:
        st.session_state.viewed_records = set()
    if 'total_records_count' not in st.session_state:
        st.session_state.total_records_count = 0
    
    # Initialize session state for approve/reject tracking (persist across refreshes)
    if 'approved_records' not in st.session_state:
        st.session_state.approved_records = set()
    if 'rejected_records' not in st.session_state:
        st.session_state.rejected_records = set()
    
    # Try to load results from database
    try:
        db = get_database()
        clips_data = db.get_pending_clips()
        
        if clips_data:
            # Convert database results to DataFrame
            df = pd.DataFrame(clips_data)
            
            # Map database fields to expected CSV format
            df = df.rename(columns={
                'wo_number': 'WO #',
                'make': 'Make',
                'model': 'Model',
                'contact': 'To',
                'office': 'Office',
                'clip_url': 'Clip URL',
                'relevance_score': 'Relevance Score',
                'status': 'Status',
                'tier_used': 'Processing Method',
                'published_date': 'Published Date',
                'media_outlet': 'Affiliation'  # Map media_outlet to Affiliation for UI compatibility
            })
            
            # Set default values for missing columns  
            if 'Affiliation' not in df.columns:
                df['Affiliation'] = df.get('Media Outlet', 'N/A')
        else:
            df = pd.DataFrame()  # Empty DataFrame if no clips
    except Exception as e:
        st.error(f"❌ Error loading clips from database: {e}")
        df = pd.DataFrame()  # Empty DataFrame on error
    
    # Process database results
    if len(df) > 0:
        try:
            
            # Ensure WO # is treated as string
            if 'WO #' in df.columns:
                df['WO #'] = df['WO #'].astype(str)
            
            if not df.empty:
                # Update total records count for progress tracking
                st.session_state.total_records_count = len(df)
                
                # Show rejection success message if flagged
                if st.session_state.get('rejection_success', False):
                    st.success("✅ Record successfully rejected and moved to Rejected/Issues tab!")
                    st.session_state.rejection_success = False  # Clear the flag

                # Quick stats overview 
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Clips", len(df))
                with col2:
                    avg_score = df['Relevance Score'].mean() if 'Relevance Score' in df.columns and not df.empty else 0
                    st.metric("Avg Score", f"{avg_score:.1f}/10")
                with col3:
                    high_quality = len(df[df['Relevance Score'] >= 8]) if 'Relevance Score' in df.columns and not df.empty else 0
                    st.metric("High Quality", high_quality)
                with col4:
                    # Check approved count from database
                    try:
                        approved_clips = db.get_approved_clips()
                        approved_count = len(approved_clips)
                    except Exception as e:
                        logger.error(f"Error getting approved clips count: {e}")
                        approved_count = 0
                    st.metric("Approved", approved_count)
                
                # Display filtered results with AgGrid
                display_df = df.copy()
                
                # Create the EXACT table structure from the working version (Image 1)
                clean_df = pd.DataFrame()
                clean_df['Office'] = display_df['Office'] if 'Office' in display_df.columns else 'N/A'
                clean_df['WO #'] = display_df['WO #'] if 'WO #' in display_df.columns else ''
                clean_df['Make'] = display_df['Make'] if 'Make' in display_df.columns else ''
                clean_df['Model'] = display_df['Model'] if 'Model' in display_df.columns else ''
                clean_df['Contact'] = display_df['To'] if 'To' in display_df.columns else ''
                
                # --- FIX: Use a name-to-ID mapping to get the correct numeric Person_ID ---
                reporter_name_to_id_map = create_reporter_name_to_id_mapping()
                
                # Use the 'Contact' column to look up the numeric Person_ID
                # NORMALIZE contact names to match the mapping (handle double spaces, case variations)
                def lookup_person_id(name):
                    if pd.isna(name) or not name:
                        return ''
                    # Normalize: strip, replace multiple spaces with single space, title case
                    normalized_name = str(name).strip().replace(r'\s+', ' ').title()
                    normalized_name = ' '.join(normalized_name.split())  # Extra normalization for multiple spaces
                    return reporter_name_to_id_map.get(normalized_name, '')
                
                clean_df['Person_ID'] = clean_df['Contact'].apply(lookup_person_id)
                
                # Add Media Outlet column right after Contact (replacing Publication)
                # Smart matching: find the correct Outlet_Name from Person_outlets_mapping
                person_outlets_mapping = load_person_outlets_mapping()
                
                def smart_outlet_matching(row):
                    affiliation = str(row.get('Affiliation', ''))
                    person_id = str(row.get('Person_ID', ''))
                    
                    if not affiliation or not person_id or not person_outlets_mapping:
                        return ''  # Return empty for dropdown
                    
                    # Get available outlet options for this person
                    outlet_options = get_outlet_options_for_person(person_id, person_outlets_mapping)
                    if not outlet_options:
                        return ''
                    
                    print(f"🔍 Smart matching '{affiliation}' for Person_ID {person_id}")
                    print(f"   Available options: {outlet_options}")
                    
                    # Try exact match first
                    if affiliation in outlet_options:
                        print(f"✅ Exact match: '{affiliation}'")
                        return affiliation
                    
                    # Try fuzzy matching - check if outlet name is contained in affiliation
                    affiliation_lower = affiliation.lower().strip()
                    for outlet in outlet_options:
                        outlet_lower = outlet.lower().strip()
                        if outlet_lower in affiliation_lower:
                            print(f"🎯 Smart match: '{affiliation}' -> '{outlet}'")
                            return outlet
                    
                    print(f"❌ No match found for '{affiliation}'")
                    return ''  # Return empty if no match
                
                clean_df['Media Outlet'] = display_df.apply(smart_outlet_matching, axis=1)
                
                
                # Format relevance score as "8/10" format
                if 'Relevance Score' in display_df.columns:
                    clean_df['Relevance'] = display_df['Relevance Score'].apply(lambda x: f"{x}/10" if pd.notna(x) and x != 'N/A' else 'N/A')
                else:
                    clean_df['Relevance'] = 'N/A'
                
                # REMOVED: Sentiment column - NEW database system uses cost-optimized GPT (relevance-only)
                # Sentiment analysis is not performed in the NEW system to save costs
                
                # Handle the URL for the View column
                url_column = None
                for col in ['Clip URL', 'url', 'final_url', 'Links']:
                    if col in display_df.columns:
                        url_column = col
                        break
                
                if url_column:
                    # ChatGPT's Alternative Solution: Create separate View column
                    clean_df['Clip URL'] = display_df[url_column]  # Keep raw URLs hidden
                    clean_df['📄 View'] = display_df[url_column]   # Copy URLs for cellRenderer
                else:
                    clean_df['Clip URL'] = 'No URL found'
                    clean_df['📄 View'] = 'No URL found'
                
                # ===== NEW: Add URL tracking columns =====
                
                # Add viewed status column for styling
                clean_df['Viewed'] = clean_df['WO #'].apply(lambda wo: str(wo) in st.session_state.viewed_records)
                
                # Add Published Date column - improved extraction with multiple fallbacks
                def get_published_date(row):
                    """Extract published date with multiple fallback methods"""
                    try:
                        # Method 1: Try Published Date field first
                        raw_date = row.get('Published Date', '')
                        if pd.notna(raw_date) and str(raw_date).strip() and str(raw_date).lower() not in ['nan', 'none', '']:
                            try:
                                import dateutil.parser
                                parsed_date = dateutil.parser.parse(str(raw_date))
                                return parsed_date.strftime('%b %d, %Y')
                            except:
                                pass
                        
                        # Method 2: Try to extract from URL if it contains date patterns
                        url = row.get('Clip URL', '')
                        if url:
                            import re
                            # Look for year/month/day patterns in URL
                            date_patterns = [
                                r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2024/12/25/
                                r'/(\d{4})-(\d{1,2})-(\d{1,2})',    # /2024-12-25
                                r'_(\d{4})(\d{2})(\d{2})',          # _20241225
                            ]
                            for pattern in date_patterns:
                                match = re.search(pattern, url)
                                if match:
                                    try:
                                        year, month, day = match.groups()
                                        from datetime import datetime
                                        date_obj = datetime(int(year), int(month), int(day))
                                        return date_obj.strftime('%b %d, %Y')
                                    except:
                                        continue
                        
                        # Method 3: Use processed date as fallback if recent
                        processed_date = row.get('Processed Date', '')
                        if processed_date:
                            try:
                                import dateutil.parser
                                from datetime import datetime, timedelta
                                parsed_date = dateutil.parser.parse(str(processed_date))
                                # Only use if within last 30 days (likely recent article)
                                if (datetime.now() - parsed_date).days <= 30:
                                    return parsed_date.strftime('%b %d, %Y')
                            except:
                                pass
                        
                        return "—"
                    except:
                        return "—"
                
                clean_df['📅 Published Date'] = display_df.apply(get_published_date, axis=1)
                
                # ===== NEW: Add Attribution Information columns =====
                def smart_attribution_analysis(row):
                    """Determine attribution strength using smart comparison logic"""
                    try:
                        contact_person = str(row.get('To', '')).strip()
                        actual_byline = str(row.get('Actual_Byline', '')).strip()
                        affiliation = str(row.get('Affiliation', '')).strip()
                        
                        # Clean up names for comparison (remove titles, normalize spaces)
                        import re
                        def normalize_name(name):
                            if not name or name.lower() in ['nan', 'none', '']:
                                return ''
                            # Remove common titles and normalize
                            name = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr)\.?\b', '', name, flags=re.IGNORECASE)
                            name = re.sub(r'\s+', ' ', name).strip()
                            return name.lower()
                        
                        contact_normalized = normalize_name(contact_person)
                        byline_normalized = normalize_name(actual_byline)
                        
                        # Strong attribution: Contact person matches article byline
                        if contact_normalized and byline_normalized:
                            # Check for exact match or partial match (handle middle names, etc.)
                            if contact_normalized == byline_normalized:
                                return 'strong', actual_byline
                            # Check if one name is contained in the other (e.g., "John Smith" vs "John A. Smith")
                            elif contact_normalized in byline_normalized or byline_normalized in contact_normalized:
                                return 'strong', actual_byline
                        
                        # Delegated: We have a contact person but different/no byline author
                        if contact_normalized and (not byline_normalized or byline_normalized != contact_normalized):
                            # Use the actual byline if available, otherwise mark as delegated content
                            return 'delegated', actual_byline if actual_byline else 'Staff/Contributor'
                        
                        # Unknown: No clear attribution info
                        return 'unknown', actual_byline if actual_byline else '—'
                    
                    except Exception as e:
                        print(f"Attribution analysis error: {e}")
                        return 'unknown', '—'

                def format_attribution_strength(row):
                    """Format attribution strength for display with smart logic"""
                    attribution_strength, _ = smart_attribution_analysis(row)
                    
                    if attribution_strength == 'strong':
                        return '✅ Direct'
                    elif attribution_strength == 'delegated':
                        return '⚠️ Delegated'
                    else:
                        return '❓ Unknown'

                def get_actual_byline(row):
                    """Get actual byline author with smart fallbacks"""
                    try:
                        _, byline_author = smart_attribution_analysis(row)
                        
                        # If we still don't have a byline, try additional fallbacks
                        if not byline_author or byline_author in ['—', 'Staff/Contributor']:
                            # Fallback 1: Use contact person if available
                            contact_person = str(row.get('To', '')).strip()
                            if contact_person and contact_person.lower() not in ['nan', 'none', '']:
                                return f"{contact_person} (Contact)"
                            
                            # Fallback 2: Try to extract from summary or content if available
                            summary = str(row.get('Summary', ''))
                            if 'by ' in summary.lower():
                                import re
                                author_match = re.search(r'by\s+([A-Za-z\s\.]+)', summary, re.IGNORECASE)
                                if author_match:
                                    potential_author = author_match.group(1).strip()
                                    if len(potential_author) > 2 and len(potential_author) < 50:  # Reasonable author name length
                                        return potential_author
                    
                        return byline_author if byline_author else '—'
                    
                    except:
                        return '—'

                clean_df['✍️ Attribution'] = display_df.apply(format_attribution_strength, axis=1)
                clean_df['📝 Byline Author'] = display_df.apply(get_actual_byline, axis=1)
                
                # Store the full URL tracking data for popup (hidden column)
                clean_df['URL_Tracking_Data'] = display_df.apply(lambda row: json.dumps(parse_url_tracking(row)), axis=1)
                
                # Add mark viewed column
                clean_df['👁️ Mark Viewed'] = False
                
                # Add action columns with session state persistence
                clean_df['✅ Approve'] = clean_df['WO #'].apply(lambda wo: str(wo) in st.session_state.approved_records)
                clean_df['❌ Reject'] = clean_df['WO #'].apply(lambda wo: str(wo) in st.session_state.rejected_records)
                
                # Create simpler view renderer with better visual feedback
                cellRenderer_view = JsCode("""
                class UrlCellRenderer {
                  init(params) {
                    const isViewed = params.data['Viewed'];
                    
                    this.eGui = document.createElement('div');
                    this.eGui.style.display = 'flex';
                    this.eGui.style.alignItems = 'center';
                    this.eGui.style.gap = '5px';
                    
                    // Add checkmark for viewed records
                    if (isViewed) {
                      const checkmark = document.createElement('span');
                      checkmark.innerHTML = '✓ ';
                      checkmark.style.color = '#28a745';
                      checkmark.style.fontWeight = 'bold';
                      checkmark.style.fontSize = '12px';
                      this.eGui.appendChild(checkmark);
                    }
                    
                    // Create the link
                    this.link = document.createElement('a');
                    this.link.innerText = '📄 View';
                    this.link.href = params.data['Clip URL'];
                    this.link.target = '_blank';
                    this.link.style.color = isViewed ? '#6c757d' : '#1f77b4';
                    this.link.style.textDecoration = 'underline';
                    this.link.style.cursor = 'pointer';
                    this.link.style.opacity = isViewed ? '0.7' : '1';
                    
                    this.eGui.appendChild(this.link);
                  }

                  getGui() {
                    return this.eGui;
                  }

                  refresh(params) {
                    const isViewed = params.data['Viewed'];
                    this.link.style.color = isViewed ? '#6c757d' : '#1f77b4';
                    this.link.style.opacity = isViewed ? '0.7' : '1';
                    return true;
                  }
                }
                """)
                
                # Create checkbox cell renderer for Approve column
                cellRenderer_approve = JsCode("""
                class ApproveCellRenderer {
                  init(params) {
                    this.eGui = document.createElement('div');
                    this.eGui.style.display = 'flex';
                    this.eGui.style.justifyContent = 'flex-start';
                    this.eGui.style.alignItems = 'center';
                    this.eGui.style.height = '100%';
                    this.eGui.style.paddingLeft = '8px';
                    
                    this.checkbox = document.createElement('input');
                    this.checkbox.type = 'checkbox';
                    this.checkbox.checked = params.value === true;
                    this.checkbox.style.cursor = 'pointer';
                    this.checkbox.style.transform = 'scale(1.2)';
                    
                    this.checkbox.addEventListener('change', () => {
                      if (this.checkbox.checked) {
                        // If approve is checked, uncheck reject
                        const rowNode = params.node;
                        rowNode.setDataValue('❌ Reject', false);
                      }
                      params.setValue(this.checkbox.checked);
                      
                      params.api.refreshCells({
                        force: true,
                        columns: ['✅ Approve', '❌ Reject'],
                        rowNodes: [params.node]
                      });
                    });
                    
                    this.eGui.appendChild(this.checkbox);
                  }

                  getGui() {
                    return this.eGui;
                  }

                  refresh(params) {
                    this.checkbox.checked = params.value === true;
                    return true;
                  }
                }
                """)
                
                # Create checkbox cell renderer for Reject column
                cellRenderer_reject = JsCode("""
                class RejectCellRenderer {
                  init(params) {
                    this.eGui = document.createElement('div');
                    this.eGui.style.display = 'flex';
                    this.eGui.style.justifyContent = 'flex-start';
                    this.eGui.style.alignItems = 'center';
                    this.eGui.style.height = '100%';
                    this.eGui.style.paddingLeft = '8px';
                    
                    this.checkbox = document.createElement('input');
                    this.checkbox.type = 'checkbox';
                    this.checkbox.checked = params.value === true;
                    this.checkbox.style.cursor = 'pointer';
                    this.checkbox.style.transform = 'scale(1.2)';
                    
                    this.checkbox.addEventListener('change', () => {
                      if (this.checkbox.checked) {
                        // If reject is checked, uncheck approve
                        const rowNode = params.node;
                        rowNode.setDataValue('✅ Approve', false);
                      }
                      params.setValue(this.checkbox.checked);
                      
                      params.api.refreshCells({
                        force: true,
                        columns: ['✅ Approve', '❌ Reject'],
                        rowNodes: [params.node]
                      });
                    });
                    
                    this.eGui.appendChild(this.checkbox);
                  }

                  getGui() {
                    return this.eGui;
                  }

                  refresh(params) {
                    this.checkbox.checked = params.value === true;
                    return true;
                  }
                }
                """)
                
                # Create Mark Viewed button renderer
                cellRenderer_mark_viewed = JsCode("""
                class MarkViewedRenderer {
                  init(params) {
                    const isViewed = params.data['Viewed'];
                    
                    this.eGui = document.createElement('div');
                    this.eGui.style.display = 'flex';
                    this.eGui.style.justifyContent = 'center';
                    this.eGui.style.alignItems = 'center';
                    this.eGui.style.height = '100%';
                    
                    this.button = document.createElement('button');
                    this.button.innerHTML = isViewed ? '✓ Viewed' : '👁️ Mark';
                    this.button.style.padding = '4px 8px';
                    this.button.style.fontSize = '11px';
                    this.button.style.border = '1px solid #ccc';
                    this.button.style.borderRadius = '4px';
                    this.button.style.cursor = 'pointer';
                    this.button.style.backgroundColor = isViewed ? '#d4edda' : '#f8f9fa';
                    this.button.style.color = isViewed ? '#155724' : '#495057';
                    
                    this.button.addEventListener('click', () => {
                      const newValue = !params.data['Viewed'];
                      params.setValue(newValue);
                      
                      // Update the row data
                      params.node.setDataValue('Viewed', newValue);
                      
                      // Update button appearance
                      this.button.innerHTML = newValue ? '✓ Viewed' : '👁️ Mark';
                      this.button.style.backgroundColor = newValue ? '#d4edda' : '#f8f9fa';
                      this.button.style.color = newValue ? '#155724' : '#495057';
                      
                      // Refresh the entire row to update styling
                      params.api.refreshCells({
                        force: true,
                        rowNodes: [params.node]
                      });
                    });
                    
                    this.eGui.appendChild(this.button);
                  }

                  getGui() {
                    return this.eGui;
                  }

                  refresh(params) {
                    const isViewed = params.data['Viewed'];
                    this.button.innerHTML = isViewed ? '✓ Viewed' : '👁️ Mark';
                    this.button.style.backgroundColor = isViewed ? '#d4edda' : '#f8f9fa';
                    this.button.style.color = isViewed ? '#155724' : '#495057';
                    return true;
                  }
                }
                """)
                


                # Configure the grid
                gb = GridOptionsBuilder.from_dataframe(clean_df)
                
                # *** RESTORE ADVANCED FEATURES WITH SET FILTERS (CHECKBOXES) ***
                gb.configure_side_bar()  # Enable filtering sidebar
                gb.configure_default_column(
                    filter="agSetColumnFilter",  # CHECKBOX FILTERS with search
                    sortable=True,  # Enable sorting
                    resizable=True,  # Enable column resizing
                    editable=False, 
                    groupable=True, 
                    value=True, 
                    enableRowGroup=True, 
                    enablePivot=True, 
                    enableValue=True,
                    filterParams={
                        "buttons": ["reset", "apply"],
                        "closeOnApply": True,
                        "newRowsAction": "keep"
                    }
                )
                
                # Hide the original URL column and tracking data
                gb.configure_column("Clip URL", hide=True)
                gb.configure_column("URL_Tracking_Data", hide=True)
                gb.configure_column("Viewed", hide=True)  # Hide the viewed status column
                
                # Configure the View column with the custom renderer
                gb.configure_column(
                    "📄 View", 
                    cellRenderer=cellRenderer_view,
                    width=120,
                    sortable=False,
                    filter=False
                )
                
                # Add row styling for viewed records with better visibility
                gb.configure_grid_options(
                    getRowStyle=JsCode("""
                    function(params) {
                        if (params.data.Viewed === true) {
                            return {
                                'background-color': '#e8f5e8',
                                'border-left': '4px solid #28a745',
                                'opacity': '0.85'
                            };
                        }
                        return {};
                    }
                    """)
                )

                # Configure selection
                gb.configure_selection(selection_mode="multiple", use_checkbox=False)
                
                # Configure other columns as before
                gb.configure_column("Office", width=100)
                gb.configure_column("WO #", width=100)
                gb.configure_column("Make", width=100)
                gb.configure_column("Model", width=120)
                gb.configure_column("Contact", width=150)
                gb.configure_column("Media Outlet", width=180)
                gb.configure_column("Person_ID", width=80)  # Narrow for small ID numbers
                gb.configure_column("Relevance", width=80)
                gb.configure_column("📅 Published Date", width=120)
                
                # Load Person_ID to Media Outlets mapping for dropdown
                person_outlets_mapping = load_person_outlets_mapping()
                
                # Configure Media Outlet dropdown column if mapping is available
                if person_outlets_mapping:
                    # Media Outlet column already exists, just configure it as dropdown
                    
                    # Configure the Media Outlet dropdown column
                    gb.configure_column(
                        "Media Outlet",
                        cellEditor="agSelectCellEditor",
                        cellEditorParams={
                            "values": []  # Will be populated dynamically per row
                        },
                        width=180,
                        editable=True,
                        sortable=True,
                        filter=True
                    )
                    
                    # Create custom cell renderer for dynamic dropdown options
                    cellRenderer_outlet_dropdown = JsCode("""
                    class OutletDropdownRenderer {
                      init(params) {
                        this.eGui = document.createElement('select');
                        this.eGui.style.width = '100%';
                        this.eGui.style.height = '100%';
                        this.eGui.style.border = 'none';
                        this.eGui.style.background = 'transparent';
                        this.eGui.style.fontSize = '12px';
                        
                        // Get Person_ID from the row data
                        const personId = params.data['Person_ID'] || params.data['Contact'];
                        const currentValue = params.value || '';
                        
                        // Debug log to see what value we're working with
                        console.log('Outlet Dropdown - Person:', personId, 'Current Value:', currentValue);
                        
                        // Get outlet options based on Person_ID
                        const outletOptions = params.data['Outlet_Options'] || [];
                        
                        // Add empty option only if no current value is set
                        if (!currentValue) {
                          const emptyOption = document.createElement('option');
                          emptyOption.value = '';
                          emptyOption.text = 'Select outlet...';
                          emptyOption.selected = true;
                          this.eGui.appendChild(emptyOption);
                        }
                        
                        // Add outlet options based on Person_ID (these are the valid Outlet_Names)
                        outletOptions.forEach(outlet => {
                          const option = document.createElement('option');
                          option.value = outlet;
                          option.text = outlet;
                          option.selected = currentValue === outlet;
                          this.eGui.appendChild(option);
                        });
                        
                        // Set the current value (should be pre-selected by backend smart matching)
                        this.eGui.value = currentValue;
                        
                        // Add change event listener
                        this.eGui.addEventListener('change', () => {
                          params.setValue(this.eGui.value);
                        });
                      }

                      getGui() {
                        return this.eGui;
                      }

                      refresh(params) {
                        return false;
                      }
                    }
                    """)
                    
                    # Configure the dropdown with custom renderer
                    gb.configure_column(
                        "Media Outlet",
                        cellRenderer=cellRenderer_outlet_dropdown,
                        width=180,
                        editable=True,
                        sortable=True,
                        filter=True
                    )
                    
                    # Add outlet options to each row based on Person_ID
                    def add_outlet_options(row):
                        person_id = row.get('Person_ID')
                        outlet_options = get_outlet_options_for_person(person_id, person_outlets_mapping)
                        # --- FIX: Ensure options are a list of strings ---
                        row['Outlet_Options'] = [str(opt) for opt in outlet_options] if outlet_options else []
                        return row
                    
                    # Apply outlet options to each row
                    clean_df = clean_df.apply(add_outlet_options, axis=1)
                
                # Configure Mark Viewed button column
                gb.configure_column(
                    "👁️ Mark Viewed",
                    cellRenderer=cellRenderer_mark_viewed,
                    width=110,
                    editable=True,
                    sortable=False,
                    filter=False,
                    pinned='left'  # Keep it visible when scrolling
                )
                
                # Configure Approve and Reject columns with checkbox renderers
                gb.configure_column(
                    "✅ Approve", 
                    cellRenderer=cellRenderer_approve,
                    width=100,
                    editable=True,
                    sortable=False,
                    filter=False
                )
                gb.configure_column(
                    "❌ Reject", 
                    cellRenderer=cellRenderer_reject,
                    width=100,
                    editable=True,
                    sortable=False,
                    filter=False
                )
                
                # Build grid options
                grid_options = gb.build()
                
                # Call AgGrid with Enterprise modules enabled for Set Filters
                selected_rows = AgGrid(
                    clean_df,
                    gridOptions=grid_options,
                    allow_unsafe_jscode=True,
                    update_mode=GridUpdateMode.MODEL_CHANGED,  # Capture changes but process them carefully
                    height=400,  # Reduced height so action buttons are visible without scrolling
                    fit_columns_on_grid_load=True,
                    theme="alpine",
                    enable_enterprise_modules=True,  # REQUIRED for Set Filters with checkboxes
                    reload_data=False,  # Prevent automatic data reloading
                    key="bulk_review_grid_stable"  # Stable key to prevent unnecessary reruns
                )
                
                                                # Process grid changes to update session state (debounced to prevent flashing)
                if selected_rows["data"] is not None and not selected_rows["data"].empty:
                    grid_df = selected_rows["data"]
                    
                    # Update session state based on Mark Viewed button states
                    new_viewed_records = set()
                    new_approved_records = set()
                    new_rejected_records = set()
                    
                    for idx, row in grid_df.iterrows():
                        wo_num = str(row.get('WO #', ''))
                        if not wo_num:
                            continue
                            
                        # Track viewed records
                        if row.get('Viewed', False):
                            new_viewed_records.add(wo_num)
                        
                        # Track approved records
                        if row.get('✅ Approve', False):
                            new_approved_records.add(wo_num)
                        
                        # Track rejected records
                        if row.get('❌ Reject', False):
                            new_rejected_records.add(wo_num)
                    
                    # Silently update session state (avoid reruns that cause flashing)
                    st.session_state.viewed_records = new_viewed_records
                    st.session_state.approved_records = new_approved_records
                    st.session_state.rejected_records = new_rejected_records
                    
                    # Also update legacy session state for compatibility
                    st.session_state.selected_for_approval = new_approved_records.copy()
                    st.session_state.selected_for_rejection = new_rejected_records.copy()
                
                # Initialize session state tracking
                if 'last_saved_outlets' not in st.session_state:
                    st.session_state.last_saved_outlets = {}
                if 'selected_for_approval' not in st.session_state:
                    st.session_state.selected_for_approval = set()
                if 'selected_for_rejection' not in st.session_state:
                    st.session_state.selected_for_rejection = set()
                if 'show_rejection_dialog' not in st.session_state:
                    st.session_state.show_rejection_dialog = False
                
                # Process changes from AgGrid WITHOUT triggering reruns
                if not selected_rows["data"].empty:
                    # Debug: Print current checkbox states
                    approved_rows = selected_rows["data"][selected_rows["data"]["✅ Approve"] == True]
                    rejected_rows = selected_rows["data"][selected_rows["data"]["❌ Reject"] == True]
                    if not approved_rows.empty or not rejected_rows.empty:
                        print(f"🔍 Checkbox changes detected: {len(approved_rows)} approved, {len(rejected_rows)} rejected")
                    
                    # 1. First handle Media Outlet changes (save to database)
                    outlet_changed = False
                    changed_count = 0
                    changed_wos = []
                    
                    for idx, row in selected_rows["data"].iterrows():
                        wo_num = str(row.get('WO #', ''))
                        new_outlet = row.get('Media Outlet', '')
                        
                        if wo_num and new_outlet:
                            # Get the last saved value to avoid duplicate saves
                            last_saved = st.session_state.last_saved_outlets.get(wo_num, '')
                            
                            # Save if different from last saved
                            if new_outlet != last_saved:
                                outlet_changed = True
                                changed_count += 1
                                changed_wos.append(wo_num)
                                st.session_state.last_saved_outlets[wo_num] = new_outlet
                                print(f"💾 Saving Media Outlet change for WO# {wo_num}: → '{new_outlet}'")
                    
                    # Save outlet changes to database (background operation)
                    if outlet_changed:
                        try:
                            # Update the database with new media outlet selections
                            # Since there's no dedicated media_outlet field, we'll store it in the contact field temporarily
                            # or add a new field to the database schema
                            
                            # Update clips in the database
                            for wo_num in changed_wos:
                                new_outlet = st.session_state.last_saved_outlets[wo_num]
                                try:
                                    # Update the clip in database using the new method
                                    success = db.update_clip_media_outlet(wo_num, new_outlet)
                                    if success:
                                        print(f"✅ Updated WO# {wo_num} media outlet to: {new_outlet}")
                                    else:
                                        print(f"⚠️ Failed to update WO# {wo_num} in database")
                                except Exception as e:
                                    print(f"❌ Error updating WO# {wo_num}: {e}")
                            
                            # Use session state to show success message without rerun
                            from datetime import datetime
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            if changed_count == 1:
                                st.session_state.outlet_save_message = f"💾 Media Outlet saved for WO# {changed_wos[0]} at {timestamp}"
                            else:
                                st.session_state.outlet_save_message = f"💾 {changed_count} Media Outlet selections saved at {timestamp}"
                            print(f"✅ Updated database with {changed_count} Media Outlet changes")
                        except Exception as e:
                            st.session_state.outlet_save_message = f"❌ Error saving Media Outlet changes: {e}"
                            print(f"❌ Error saving changes: {e}")
                    
                    # 2. Then handle approval/rejection checkboxes (stable tracking)
                    approved_rows = selected_rows["data"][selected_rows["data"]["✅ Approve"] == True]
                    rejected_rows = selected_rows["data"][selected_rows["data"]["❌ Reject"] == True]
                    
                    # Get current checkbox states
                    current_approved_wos = set(approved_rows['WO #'].astype(str))
                    current_rejected_wos = set(rejected_rows['WO #'].astype(str))
                    
                    # REPLACE the session state entirely with current checkbox states
                    # This prevents accumulation and refresh issues
                    st.session_state.selected_for_approval = current_approved_wos.copy()
                    st.session_state.selected_for_rejection = current_rejected_wos.copy()
                    
                    # Also sync with persistent session state
                    st.session_state.approved_records = current_approved_wos.copy()
                    st.session_state.rejected_records = current_rejected_wos.copy()
                    
                    # Debug: Print session state updates
                    if current_approved_wos or current_rejected_wos:
                        print(f"📊 Session state updated: {len(current_approved_wos)} approved, {len(current_rejected_wos)} rejected")
                        print(f"   Approved WOs: {list(current_approved_wos)[:5]}...")  # Show first 5
                    
                    # Ensure mutual exclusivity (approve overrides reject)
                    if current_approved_wos:
                        st.session_state.selected_for_rejection -= current_approved_wos
                        st.session_state.rejected_records -= current_approved_wos
                
                # Display persistent messages
                if hasattr(st.session_state, 'outlet_save_message') and st.session_state.outlet_save_message:
                    if st.session_state.outlet_save_message.startswith("💾"):
                        st.success(st.session_state.outlet_save_message)
                    else:
                        st.error(st.session_state.outlet_save_message)
                    # Clear message after showing
                    st.session_state.outlet_save_message = None
                
                # Show current selection counts
                approved_count = len(st.session_state.selected_for_approval)
                rejected_count = len(st.session_state.selected_for_rejection)
                if approved_count > 0:
                    st.info(f"📋 {approved_count} clips selected for approval")
                if rejected_count > 0:
                    st.info(f"📋 {rejected_count} clips selected for rejection")
                
                # Action buttons below table
                st.markdown("---")
                
                # Create sticky action bar container
                st.markdown('<div class="sticky-action-bar">', unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    # Submit Approved Clips Button
                    selected_count = len(st.session_state.get('selected_for_approval', set()))
                    if st.button(f"✅ Submit {selected_count} Approved Clips", disabled=selected_count == 0, key="submit_approved_main"):
                        if selected_count > 0:
                            # Show confirmation dialog
                            st.session_state.show_approval_dialog = True
                
                with col2:
                    # Submit Rejected Clips Button (side by side with approved)
                    rejected_count = len(st.session_state.get('selected_for_rejection', set()))
                    if st.button(f"❌ Submit {rejected_count} Rejected Clips", disabled=rejected_count == 0, key="submit_rejected_main"):
                        if rejected_count > 0:
                            # Show rejection confirmation dialog
                            st.session_state.show_rejection_dialog = True
                
                with col3:
                    if st.button("✅ Auto-Approve High Quality (9+)"):
                        high_quality_df = df[df['Relevance Score'] >= 9]
                        if not high_quality_df.empty:
                            # Add to session state selections
                            if 'selected_for_approval' not in st.session_state:
                                st.session_state.selected_for_approval = set()
                            high_quality_wos = set(high_quality_df['WO #'].astype(str))
                            st.session_state.selected_for_approval.update(high_quality_wos)
                            st.success(f"📋 Added {len(high_quality_wos)} high-quality clips to selection!")
                            st.rerun()
                        else:
                            st.info("No high-quality clips (9+) found")
                
                with col4:
                    # Clear All Selections Button
                    if st.button("🗑️ Clear All"):
                        st.session_state.selected_for_approval = set()
                        st.session_state.selected_for_rejection = set()
                        st.session_state.approved_records = set()
                        st.session_state.rejected_records = set()
                        st.success("✅ All selections cleared")
                        st.rerun()
                
                # Close sticky action bar container
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Approval confirmation dialog
                if st.session_state.get('show_approval_dialog', False):
                    st.markdown("---")
                    st.warning(f"⚠️ **Approve {selected_count} clips?** This will save them and generate client files.")
                    
                    col_confirm, col_cancel = st.columns(2)
                    with col_confirm:
                        if st.button("✅ Confirm Approval", type="primary", key="confirm_approval_btn"):
                            # Process the approvals - SIMPLIFIED WORKFLOW
                            selected_wos = st.session_state.selected_for_approval
                            if selected_wos:
                                # Update clips in database to approved status (workflow_stage stays 'found' for Approved Queue)
                                try:
                                    for wo_number in selected_wos:
                                        db.supabase.table('clips').update({
                                            'status': 'approved',
                                            'workflow_stage': 'found'  # Clips go to Approved Queue first
                                        }).eq('wo_number', wo_number).execute()
                                    
                                    logger.info(f"✅ Approved {len(selected_wos)} clips - moved to Approved Queue")
                                    
                                    # Success message and cleanup
                                    st.success(f"✅ Successfully approved {len(selected_wos)} clips!")
                                    st.info("📋 **Clips moved to Approved Queue** - ready for batch processing")
                                    
                                    # Clear selections and dialog
                                    st.session_state.selected_for_approval = set()
                                    st.session_state.approved_records = set()
                                    st.session_state.show_approval_dialog = False
                                    
                                    # Refresh the page to update the Bulk Review table
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Error approving clips in database: {e}")
                                    logger.error(f"Database approval error: {e}")
                    
                    with col_cancel:
                        if st.button("❌ Cancel", key="cancel_approval_btn"):
                            st.session_state.show_approval_dialog = False
                            st.rerun()
                
                # NEW: Rejection confirmation dialog
                if st.session_state.get('show_rejection_dialog', False):
                    st.markdown("---")
                    rejected_count = len(st.session_state.get('selected_for_rejection', set()))
                    st.error(f"⚠️ **Reject {rejected_count} clips?** This will move them to Rejected/Issues tab.")
                    
                    col_confirm, col_cancel = st.columns(2)
                    with col_confirm:
                        if st.button("❌ Confirm Rejection", type="secondary", key="confirm_rejection_btn"):
                            # Process the rejections
                            selected_rejected_wos = st.session_state.selected_for_rejection
                            if selected_rejected_wos:
                                try:
                                    # Reload the DataFrame to ensure it's in scope
                                    results_file = os.path.join(project_root, "data", "loan_results.csv")
                                    df = pd.read_csv(results_file)
                                    df['WO #'] = df['WO #'].astype(str)
                                    
                                    rejected_file = os.path.join(project_root, "data", "rejected_clips.csv")
                                    selected_rejected_rows = df[df['WO #'].astype(str).isin(selected_rejected_wos)]
                                    
                                    # Prepare rejected records with proper format
                                    rejected_records = []
                                    for _, row in selected_rejected_rows.iterrows():
                                        # Get office value for rejection record
                                        office_value = row.get('Office', '')
                                        
                                        rejected_record = {
                                            'WO #': str(row.get('WO #', '')),
                                            'Activity_ID': str(row.get('Activity_ID', '')),
                                            'Make': str(row.get('Make', '')),
                                            'Model': str(row.get('Model', '')),
                                            'To': str(row.get('To', '')),
                                            'Affiliation': str(row.get('Affiliation', '')),
                                            'Office': str(office_value),  # Use the debug variable
                                            'Links': str(row.get('Links', '')),
                                            'URLs_Processed': row.get('URLs_Processed', 0),
                                            'URLs_Successful': row.get('URLs_Successful', 0),
                                            'Rejection_Reason': 'Manual rejection by reviewer',
                                            'URL_Details': str(row.get('URL_Tracking', '')),
                                            'Processed_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                            'Loan_Start_Date': str(row.get('Start Date', '')),
                                            # PRESERVE the original working Clip URL and relevance score for move-back
                                            'Original_Clip_URL': str(row.get('Clip URL', '')),
                                            'Original_Relevance_Score': row.get('Relevance Score', 5)
                                        }
                                        rejected_records.append(rejected_record)
                                    
                                    # Save to rejected clips CSV
                                    if os.path.exists(rejected_file):
                                        # Load existing rejected records and append
                                        existing_rejected_df = pd.read_csv(rejected_file)
                                        if 'WO #' in existing_rejected_df.columns:
                                            existing_rejected_df['WO #'] = existing_rejected_df['WO #'].astype(str)
                                        # Only add rows that aren't already rejected
                                        new_rejected_df = pd.DataFrame(rejected_records)
                                        new_rejected_df['WO #'] = new_rejected_df['WO #'].astype(str)
                                        new_rows = new_rejected_df[~new_rejected_df['WO #'].isin(existing_rejected_df['WO #'])]
                                        if not new_rows.empty:
                                            combined_rejected_df = pd.concat([existing_rejected_df, new_rows], ignore_index=True)
                                            combined_rejected_df.to_csv(rejected_file, index=False)
                                    else:
                                        # Create new rejected file
                                        pd.DataFrame(rejected_records).to_csv(rejected_file, index=False)
                                    
                                    # Remove rejected records from the main results file
                                    # This makes them disappear from Bulk Review table
                                    remaining_df = df[~df['WO #'].astype(str).isin(selected_rejected_wos)]
                                    remaining_df.to_csv(results_file, index=False)
                                    
                                    # Clear selections and dialog (both new and legacy tracking)
                                    st.session_state.selected_for_rejection = set()
                                    st.session_state.rejected_records = set()  # Clear new tracking too
                                    st.session_state.show_rejection_dialog = False
                                    
                                    # Also clear any approved selections for the rejected items
                                    st.session_state.approved_records -= selected_rejected_wos
                                    st.session_state.selected_for_approval -= selected_rejected_wos
                                    
                                    # Force a cache clear and state refresh to ensure AgGrid updates
                                    if hasattr(st, 'cache_data'):
                                        st.cache_data.clear()
                                    
                                    # Set a flag to indicate successful rejection for next page load
                                    st.session_state.rejection_success = True
                                    
                                    # Immediate rerun without messages to update the UI
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"Error processing rejection: {e}")
                                    print(f"Rejection error: {e}")
                                    import traceback
                                    print(f"Full traceback: {traceback.format_exc()}")
                                    # Clear dialog even on error
                                    st.session_state.show_rejection_dialog = False
                                    st.rerun()  # Force rerun even on error
                    
                    with col_cancel:
                        if st.button("❌ Cancel Rejection", key="cancel_rejection_btn"):
                            st.session_state.show_rejection_dialog = False
                            st.rerun()

            else:
                st.info("No clips to review. Process loans first.")
        except Exception as e:
            st.error(f"Error loading clips: {e}")
    else:
        st.info("No results file found. Upload and process loans to begin.")

    # ========== WORKFLOW PROGRESS SECTION ==========
    # Show current workflow status
    if len(df) > 0:
        st.markdown("---")
        st.markdown("### 🔄 Workflow Status")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            pending_count = len(df)
            st.metric("📋 Pending Review", pending_count)
        
        with col2:
            try:
                approved_queue_clips = db.get_approved_queue_clips()
                approved_count = len(approved_queue_clips)
            except:
                approved_count = 0
            st.metric("✅ Approved Queue", approved_count)
        
        with col3:
            # This will be implemented in Phase 2
            st.metric("🧠 Sentiment Ready", "Phase 2")
        
        with col4:
            # This will be implemented in Phase 3
            st.metric("📤 Export Ready", "Phase 3")
        
        if approved_count > 0:
            st.info(f"💡 **Next Step:** Visit the **Approved Queue** tab to manage {approved_count} approved clips")
    
    # Add bottom padding to prevent UI elements from touching the bottom (CORRECTLY PLACED)
    st.markdown('<div style="height: 100px;"></div>', unsafe_allow_html=True)


# ========== APPROVED QUEUE TAB (Enhanced with FMS Export) ==========
with approved_queue_tab:
    st.markdown('<h4 style="margin-top: 0; margin-bottom: 0.5rem; font-size: 1.2rem; font-weight: 600; color: #2c3e50;">✅ Approved Queue</h4>', unsafe_allow_html=True)
    st.markdown('<p style="margin-top: 0; margin-bottom: 1rem; font-size: 0.9rem; color: #6c757d; font-style: italic;">Manage approved clips through the FMS export workflow</p>', unsafe_allow_html=True)
    
    # Initialize session state for workflow filtering
    if 'approved_queue_filter' not in st.session_state:
        st.session_state.approved_queue_filter = 'ready_for_export'
    
    # Workflow filtering tabs
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    
    with filter_col1:
        if st.button("📋 Ready for Export", key="filter_ready", 
                    type="primary" if st.session_state.approved_queue_filter == 'ready_for_export' else "secondary"):
            st.session_state.approved_queue_filter = 'ready_for_export'
            st.rerun()
    
    with filter_col2:
        if st.button("🧠 Needs Sentiment", key="filter_sentiment",
                    type="primary" if st.session_state.approved_queue_filter == 'needs_sentiment' else "secondary"):
            st.session_state.approved_queue_filter = 'needs_sentiment'
            st.rerun()
    
    with filter_col3:
        if st.button("📊 Recent Complete", key="filter_complete",
                    type="primary" if st.session_state.approved_queue_filter == 'recent_complete' else "secondary"):
            st.session_state.approved_queue_filter = 'recent_complete'
            st.rerun()
    
    with filter_col4:
        if st.button("🗑️ Archive Mgmt", key="filter_archive",
                    type="primary" if st.session_state.approved_queue_filter == 'archive_mgmt' else "secondary"):
            st.session_state.approved_queue_filter = 'archive_mgmt'
            st.rerun()
    
    # Load clips based on selected filter
    try:
        db = get_database()
        
        if st.session_state.approved_queue_filter == 'ready_for_export':
            clips_data = db.get_clips_ready_for_export()
            tab_title = "📋 Ready for Export"
            tab_description = "Clips ready for FMS export (basic data without sentiment)"
            
        elif st.session_state.approved_queue_filter == 'needs_sentiment':
            clips_data = db.get_clips_needing_sentiment_analysis()
            tab_title = "🧠 Needs Sentiment Analysis"
            tab_description = "Clips exported to FMS, awaiting sentiment analysis"
            
        elif st.session_state.approved_queue_filter == 'recent_complete':
            clips_data = db.get_clips_complete_recent(days=30)
            tab_title = "📊 Recent Complete (Last 30 Days)"
            tab_description = "Fully processed clips with sentiment analysis"
            
        else:  # archive_mgmt
            clips_data = []
            tab_title = "🗑️ Archive Management"
            tab_description = "Delete old clips to manage database size"
        
        # Display current filter info
        st.markdown(f'<h5 style="margin-top: 0.5rem; margin-bottom: 0.3rem; font-size: 1.1rem; font-weight: 600; color: #2c3e50;">{tab_title}</h5>', unsafe_allow_html=True)
        st.markdown(f'<p style="margin-top: 0; margin-bottom: 1rem; font-size: 0.85rem; color: #6c757d; font-style: italic;">{tab_description}</p>', unsafe_allow_html=True)
        
        if st.session_state.approved_queue_filter == 'archive_mgmt':
            # Archive Management Section
            st.markdown('<hr style="margin: 1rem 0; border: none; height: 1px; background-color: #e0e0e0;">', unsafe_allow_html=True)
            st.markdown('<h5 style="margin-top: 0.5rem; margin-bottom: 0.5rem; font-size: 1.1rem; font-weight: 600; color: #2c3e50;">🗑️ Archive Management</h5>', unsafe_allow_html=True)
            
            col_days, col_action = st.columns([1, 2])
            
            with col_days:
                days_to_delete = st.number_input("Delete clips older than (days):", min_value=30, max_value=365, value=90, step=30)
            
            with col_action:
                st.markdown("<br>", unsafe_allow_html=True)  # Add spacing
                col_export, col_delete = st.columns(2)
                
                with col_export:
                    if st.button("📤 Export Before Delete", help="Export old clips before deletion"):
                        try:
                            result = db.delete_clips_older_than_days(days_to_delete, export_before_delete=True)
                            if result['exported_clips']:
                                # Create export file
                                import json
                                export_data = json.dumps(result['exported_clips'], indent=2)
                                filename = f"archived_clips_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                                
                                st.download_button(
                                    label="📥 Download Archive",
                                    data=export_data,
                                    file_name=filename,
                                    mime="application/json"
                                )
                                st.success(f"✅ Exported {len(result['exported_clips'])} clips for archive")
                            else:
                                st.info("No clips found older than specified days")
                        except Exception as e:
                            st.error(f"❌ Error creating archive: {e}")
                
                with col_delete:
                    if st.button("🗑️ Delete Old Clips", help="Permanently delete old clips"):
                        try:
                            result = db.delete_clips_older_than_days(days_to_delete, export_before_delete=False)
                            if result['deleted_count'] > 0:
                                st.success(f"✅ Deleted {result['deleted_count']} clips older than {days_to_delete} days")
                            else:
                                st.info("No clips found older than specified days")
                        except Exception as e:
                            st.error(f"❌ Error deleting clips: {e}")
            
            # Show warning
            st.warning(f"⚠️ This will permanently delete clips older than {days_to_delete} days. Use 'Export Before Delete' to backup data first.")
        
        elif clips_data:
            # Convert to DataFrame for display
            approved_df = pd.DataFrame(clips_data)
            
            # Ensure WO # is treated as string
            if 'wo_number' in approved_df.columns:
                approved_df['wo_number'] = approved_df['wo_number'].astype(str)
            
            # Quick stats overview
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Clips", len(approved_df))
            with col2:
                avg_score = approved_df['relevance_score'].mean() if 'relevance_score' in approved_df.columns and not approved_df.empty else 0
                st.metric("Avg Relevance", f"{avg_score:.1f}/10")
            with col3:
                unique_contacts = approved_df['contact'].nunique() if 'contact' in approved_df.columns else 0
                st.metric("Media Contacts", unique_contacts)
            with col4:
                unique_outlets = approved_df['media_outlet'].nunique() if 'media_outlet' in approved_df.columns else 0
                st.metric("Media Outlets", unique_outlets)
            
            # Create display DataFrame
            clean_df = pd.DataFrame()
            clean_df['WO #'] = approved_df['wo_number'] if 'wo_number' in approved_df.columns else ''
            clean_df['Office'] = approved_df['office'] if 'office' in approved_df.columns else ''
            clean_df['Make'] = approved_df['make'] if 'make' in approved_df.columns else ''
            clean_df['Model'] = approved_df['model'] if 'model' in approved_df.columns else ''
            clean_df['Contact'] = approved_df['contact'] if 'contact' in approved_df.columns else ''
            clean_df['Media Outlet'] = approved_df['media_outlet'] if 'media_outlet' in approved_df.columns else ''
            clean_df['Relevance'] = approved_df['relevance_score'].apply(lambda x: f"{x}/10" if pd.notna(x) and x != 'N/A' else 'N/A') if 'relevance_score' in approved_df.columns else 'N/A'
            clean_df['Date'] = pd.to_datetime(approved_df['processed_date']).dt.strftime('%b %d') if 'processed_date' in approved_df.columns else ''
            
            # Add View column for URLs
            clean_df['Clip URL'] = approved_df['clip_url'] if 'clip_url' in approved_df.columns else ''
            clean_df['📄 View'] = clean_df['Clip URL']
            
            # Add workflow status indicator
            clean_df['Stage'] = approved_df['workflow_stage'].apply(
                lambda x: "📋 Ready" if x == 'found' else 
                         "📤 Exported" if x == 'exported' else 
                         "✅ Complete" if x == 'complete' else 
                         f"📊 {x.replace('_', ' ').title()}"
            ) if 'workflow_stage' in approved_df.columns else 'Unknown'
            
            # Configure AgGrid for approved queue
            gb = GridOptionsBuilder.from_dataframe(clean_df)
            
            # Enable selection for batch operations
            gb.configure_selection('multiple', use_checkbox=True)
            
            # Configure columns
            gb.configure_column("WO #", width=100, pinned='left')
            gb.configure_column("Office", width=80)
            gb.configure_column("Make", width=100)
            gb.configure_column("Model", width=120)
            gb.configure_column("Contact", width=150)
            gb.configure_column("Media Outlet", width=180)
            gb.configure_column("Relevance", width=100)
            gb.configure_column("Date", width=80)
            gb.configure_column("Stage", width=100)
            
            # Hide raw URL column
            gb.configure_column("Clip URL", hide=True)
            
            # Configure View column with URL renderer
            cellRenderer_view = JsCode("""
            class UrlCellRenderer {
              init(params) {
                this.eGui = document.createElement('a');
                this.eGui.innerText = '📄 View';
                this.eGui.href = params.data['Clip URL'];
                this.eGui.target = '_blank';
                this.eGui.style.color = '#1f77b4';
                this.eGui.style.textDecoration = 'underline';
                this.eGui.style.cursor = 'pointer';
              }

              getGui() {
                return this.eGui;
              }

              refresh(params) {
                return false;
              }
            }
            """)
            
            gb.configure_column(
                "📄 View", 
                cellRenderer=cellRenderer_view,
                width=100,
                sortable=False,
                filter=False
            )
            
            # Build and display grid
            grid_options = gb.build()
            
            selected_clips = AgGrid(
                clean_df,
                gridOptions=grid_options,
                allow_unsafe_jscode=True,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                height=400,
                fit_columns_on_grid_load=True,
                theme="alpine"
            )
            
            # Action buttons based on current filter
            st.markdown("---")
            
            if st.session_state.approved_queue_filter == 'ready_for_export':
                # FMS Export Actions
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📤 Export to FMS", help="Generate JSON for FMS import"):
                        # Fix: Handle AgGrid response properly
                        selected_data = selected_clips.get('selected_rows', [])
                        
                        # Debug: Check what we're getting
                        print(f"DEBUG: selected_data type: {type(selected_data)}")
                        print(f"DEBUG: selected_data content: {selected_data}")
                        
                        # Convert to list if it's a DataFrame
                        if hasattr(selected_data, 'to_dict'):
                            selected_rows = selected_data.to_dict('records')
                        elif isinstance(selected_data, list):
                            selected_rows = selected_data
                        else:
                            selected_rows = []
                        
                        if selected_rows and len(selected_rows) > 0:
                            # Generate FMS export JSON
                            try:
                                fms_export_data = []
                                wo_numbers_to_update = []
                                
                                for row in selected_rows:
                                    wo_number = str(row.get('WO #', ''))
                                    if wo_number:
                                        wo_numbers_to_update.append(wo_number)
                                        
                                        # Get full clip data from database
                                        clip_data = next((clip for clip in clips_data if str(clip['wo_number']) == wo_number), None)
                                        if clip_data:
                                            fms_export_data.append({
                                                "work_order": wo_number,
                                                "activity_id": clip_data.get('activity_id', ''),
                                                "make": clip_data.get('make', ''),
                                                "vehicle_model": clip_data.get('model', ''),
                                                "contact": clip_data.get('contact', ''),
                                                "media_outlet": clip_data.get('media_outlet', ''),
                                                "office": clip_data.get('office', ''),
                                                "clip_url": clip_data.get('clip_url', ''),
                                                "relevance_score": clip_data.get('relevance_score', 0),
                                                "processed_date": clip_data.get('processed_date', ''),
                                                "export_timestamp": datetime.now().isoformat(),
                                                "export_type": "basic"
                                            })
                                
                                if fms_export_data:
                                    # Update workflow stage to exported_basic
                                    success = db.update_clips_to_exported_basic(wo_numbers_to_update)
                                    
                                    if success:
                                        # Generate download
                                        export_filename = f"fms_export_basic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                                        
                                        st.download_button(
                                            label="📥 Download FMS Export",
                                            data=json.dumps(fms_export_data, indent=2),
                                            file_name=export_filename,
                                            mime="application/json"
                                        )
                                        
                                        st.success(f"✅ Exported {len(selected_rows)} clips to FMS format")
                                        st.info("📋 Clips moved to 'Needs Sentiment' - ready for sentiment analysis")
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to update clip workflow stages")
                                else:
                                    st.error("❌ No valid clips found for export")
                            except Exception as e:
                                st.error(f"❌ Error generating FMS export: {e}")
                        else:
                            st.warning("Please select clips to export")
                
                with col2:
                    if st.button("🔄 Move Back to Review", help="Move selected clips back to Bulk Review"):
                        # Fix: Handle AgGrid response properly
                        selected_data = selected_clips.get('selected_rows', [])
                        if hasattr(selected_data, 'to_dict'):
                            selected_rows = selected_data.to_dict('records')
                        elif isinstance(selected_data, list):
                            selected_rows = selected_data
                        else:
                            selected_rows = []
                        
                        if selected_rows and len(selected_rows) > 0:
                            # Move clips back to pending_review status
                            try:
                                for row in selected_rows:
                                    wo_number = str(row.get('WO #', ''))
                                    if wo_number:
                                        db.supabase.table('clips').update({
                                            'status': 'pending_review'
                                        }).eq('wo_number', wo_number).execute()
                                
                                st.success(f"✅ Moved {len(selected_rows)} clips back to Bulk Review")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error moving clips: {e}")
                        else:
                            st.warning("Please select clips to move back")
                
                with col3:
                    if st.button("📊 Select All", help="Select all clips for batch export"):
                        st.info("💡 Use the checkboxes in the table to select clips for export")
            
            elif st.session_state.approved_queue_filter == 'needs_sentiment':
                # Sentiment Analysis Actions
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🧠 Run Sentiment Analysis", help="Analyze sentiment for selected clips"):
                        # Fix: Handle AgGrid response properly
                        selected_data = selected_clips.get('selected_rows', [])
                        if hasattr(selected_data, 'to_dict'):
                            selected_rows = selected_data.to_dict('records')
                        elif isinstance(selected_data, list):
                            selected_rows = selected_data
                        else:
                            selected_rows = []
                        
                        if selected_rows and len(selected_rows) > 0:
                            st.info(f"📊 Sentiment analysis for {len(selected_rows)} clips will be implemented in Phase 2")
                            # TODO: Implement sentiment analysis batch job
                        else:
                            st.warning("Please select clips for sentiment analysis")
                
                with col2:
                    if st.button("📤 Export Enhanced", help="Export clips with sentiment data"):
                        st.info("📊 Enhanced export will be available after sentiment analysis is implemented")
        
        else:
            # No clips found for current filter
            if st.session_state.approved_queue_filter == 'ready_for_export':
                st.info("📋 No clips ready for export. Approve clips in Bulk Review to see them here.")
            elif st.session_state.approved_queue_filter == 'needs_sentiment':
                st.info("🧠 No clips awaiting sentiment analysis. Export clips first to populate this section.")
            elif st.session_state.approved_queue_filter == 'recent_complete':
                st.info("📊 No completed clips in the last 30 days.")
            
            # Show helpful instructions
            st.markdown("""
            **Enhanced Approved Queue Workflow:**
            1. **📋 Ready for Export** - Clips approved in Bulk Review, ready for FMS export
            2. **🧠 Needs Sentiment** - Clips exported to FMS, awaiting sentiment analysis  
            3. **📊 Recent Complete** - Fully processed clips (last 30 days)
            4. **🗑️ Archive Management** - Delete old clips to manage database size
            
            **Workflow Progression:**
            `Bulk Review` → `Ready for Export` → `Export to FMS` → `Needs Sentiment` → `Complete`
            """)
    
    except Exception as e:
        st.error(f"❌ Error loading approved queue: {e}")
        import traceback
        st.error(f"Full error: {traceback.format_exc()}")
    
    # Add bottom padding to prevent UI elements from being cut off
    st.markdown('<div style="height: 150px;"></div>', unsafe_allow_html=True)


# ========== REJECTED/ISSUES TAB (Enhanced with Current Run + Historical + Date Range) ==========
with rejected_tab:
    # Initialize session state for filtering mode
    if 'rejected_view_mode' not in st.session_state:
        st.session_state.rejected_view_mode = 'current_run'  # Default to current run
    
    # Compact Filtering Controls - Single Row
    col_toggle, col_dates, col_info = st.columns([1, 2, 2])
    
    with col_toggle:
        if st.session_state.rejected_view_mode == 'current_run':
            if st.button("📊 Show Historical", key="show_historical", help="View all historical failed attempts"):
                st.session_state.rejected_view_mode = 'historical'
                st.rerun()
        else:
            if st.button("🔄 Current Run", key="show_current", help="View only the most recent processing run"):
                st.session_state.rejected_view_mode = 'current_run'
                st.rerun()
    
    # Date range filtering (only shown in historical mode)
    start_date = None
    end_date = None
    
    with col_dates:
        if st.session_state.rejected_view_mode == 'historical':
            col_start, col_end = st.columns(2)
            with col_start:
                # Default to 30 days ago
                from datetime import datetime, timedelta
                default_start = datetime.now() - timedelta(days=30)
                start_date = st.date_input("From", value=default_start, key="rejected_start_date")
            with col_end:
                # Default to today
                default_end = datetime.now()
                end_date = st.date_input("To", value=default_end, key="rejected_end_date")
    
    with col_info:
        if st.session_state.rejected_view_mode == 'current_run':
            st.caption("🔄 Current run failures only")
        else:
            date_range = ""
            if start_date and end_date:
                date_range = f" ({start_date} to {end_date})"
            st.caption(f"📊 Historical view{date_range}")
    
    # Load rejected clips and failed processing attempts from database
    try:
        # Choose data source based on mode
        if st.session_state.rejected_view_mode == 'current_run':
            # Current run mode - get only the most recent processing run
            current_run_failed_clips = db.get_current_run_failed_clips()
            
            # Get run info for display
            if current_run_failed_clips:
                latest_run_id = db.get_latest_processing_run_id()
                run_info = db.get_processing_run_info(latest_run_id) if latest_run_id else None
                
                if run_info:
                    run_name = run_info.get('run_name', 'Unknown')
                    run_date = run_info.get('start_time', 'Unknown')[:19] if run_info.get('start_time') else 'Unknown'  # Truncate timestamp
                    st.caption(f"🔄 **{run_name}** - {run_date}")
            
            # Convert to combined issues format
            combined_issues = []
            for clip in current_run_failed_clips:
                combined_issues.append({
                    'WO #': clip['wo_number'],
                    'Office': clip.get('office', ''),
                    'Make': clip.get('make', ''),
                    'Model': clip.get('model', ''),
                    'To': clip.get('contact', ''),
                    'Affiliation': clip.get('office', ''),
                    'Rejection_Reason': 'No Content Found' if clip['status'] == 'no_content_found' else 'Processing Failed',
                    'URL_Details': f"Processed with {clip.get('tier_used', 'Unknown')}",
                    'Processed_Date': clip.get('processed_date', ''),
                    'Type': 'No Content Found' if clip['status'] == 'no_content_found' else 'Processing Failed',
                    'original_urls': clip.get('original_urls', ''),
                    'urls_attempted': clip.get('urls_attempted', 0),
                    'failure_reason': clip.get('failure_reason', '')
                })
            
        else:
            # Historical mode - get all failed clips with optional date filtering
            start_date_str = start_date.strftime('%Y-%m-%d') if start_date else None
            end_date_str = end_date.strftime('%Y-%m-%d') if end_date else None
            
            all_failed_clips = db.get_all_failed_clips(
                start_date=start_date_str,
                end_date=end_date_str
            )
            
            # Display date range info compactly
            if start_date_str and end_date_str:
                st.caption(f"📊 **Historical:** {start_date_str} to {end_date_str}")
            elif start_date_str:
                st.caption(f"📊 **Historical:** From {start_date_str}")
            elif end_date_str:
                st.caption(f"📊 **Historical:** Until {end_date_str}")
            else:
                st.caption("📊 **Historical:** All Time")
            
            # Convert to combined issues format
            combined_issues = []
            for clip in all_failed_clips:
                combined_issues.append({
                    'WO #': clip['wo_number'],
                    'Office': clip.get('office', ''),
                    'Make': clip.get('make', ''),
                    'Model': clip.get('model', ''),
                    'To': clip.get('contact', ''),
                    'Affiliation': clip.get('office', ''),
                    'Rejection_Reason': 'No Content Found' if clip['status'] == 'no_content_found' else 'Processing Failed',
                    'URL_Details': f"Processed with {clip.get('tier_used', 'Unknown')}",
                    'Processed_Date': clip.get('processed_date', ''),
                    'Type': 'No Content Found' if clip['status'] == 'no_content_found' else 'Processing Failed',
                    'original_urls': clip.get('original_urls', ''),
                    'urls_attempted': clip.get('urls_attempted', 0),
                    'failure_reason': clip.get('failure_reason', '')
                })
        
        # Also add manually rejected clips (always shown regardless of mode)
        rejected_clips = db.get_rejected_clips()
        for clip in rejected_clips:
            combined_issues.append({
                'WO #': clip['wo_number'],
                'Office': clip.get('office', ''),
                'Make': clip.get('make', ''),
                'Model': clip.get('model', ''),
                'To': clip.get('contact', ''),
                'Affiliation': clip.get('office', ''),
                'Rejection_Reason': 'User Rejected Clip',
                'URL_Details': clip.get('clip_url', ''),
                'Processed_Date': clip.get('processed_date', ''),
                'Type': 'Rejected Clip',
                'original_urls': '',  # Rejected clips don't have original URLs
                'urls_attempted': 0,
                'failure_reason': ''
            })
        
        # Create DataFrame from combined issues
        if combined_issues:
            rejected_df = pd.DataFrame(combined_issues)
        else:
            rejected_df = pd.DataFrame()
            
    except Exception as e:
        st.error(f"❌ Error loading rejected clips from database: {e}")
        rejected_df = pd.DataFrame()  # Empty DataFrame on error
    
    # Process results
    if len(rejected_df) > 0:
        # Ensure WO # is treated as string for consistency
        if 'WO #' in rejected_df.columns:
            rejected_df['WO #'] = rejected_df['WO #'].astype(str)
        
        if not rejected_df.empty:
            # Compact metrics in a single row
            st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 8px; border-radius: 4px; margin: 8px 0;">
                <small>
                    📝 <strong>{len(rejected_df)}</strong> rejected  •  
                    🚫 <strong>{rejected_df['Rejection_Reason'].value_counts().index[0] if 'Rejection_Reason' in rejected_df.columns and len(rejected_df) > 0 else 'N/A'}</strong> top issue  •  
                    ⚡ <strong>{len(rejected_df[rejected_df['Rejection_Reason'].str.contains('No Content Found|Processing Failed', case=False, na=False)] if 'Rejection_Reason' in rejected_df.columns else [])}/{len(rejected_df)}</strong> technical failures
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # Create AgGrid table (same format as bulk review but for rejected records)
            clean_df = rejected_df.copy()
            
            # Prepare columns for display
            if 'WO #' in clean_df.columns:
                clean_df['WO #'] = clean_df['WO #'].astype(str)
            
            # Add Office column if it exists
            if 'Office' in rejected_df.columns:
                pass  # Keep original name
            
            # Extract the searched URL from database fields for the View column  
            def extract_searched_url(row):
                """
                Extract the original source URL(s) from database fields for the View link.
                Handles both single and multiple URLs per WO# intelligently.
                """
                # NEW: Try the database original_urls field first
                original_urls = row.get('original_urls', '')
                if original_urls and not pd.isna(original_urls):
                    original_urls = str(original_urls).strip()
                    if original_urls:
                        # Handle multiple URLs separated by semicolon
                        urls = [url.strip() for url in original_urls.split(';') if url.strip()]
                        if urls:
                            # If multiple URLs, return the first one (most common case)
                            # We'll show a count indicator if there are multiple
                            first_url = urls[0]
                            print(f"DEBUG: Found {len(urls)} original URLs for WO#, using first: {first_url}")
                            return first_url
                
                # FALLBACK: Try the old URL_Details field for backward compatibility
                url_details = row.get('URL_Details', '')
                if pd.isna(url_details) or not url_details:
                    return ""
                
                url_details_str = str(url_details).strip()
                print(f"DEBUG: Fallback to URL_Details parsing: {url_details_str[:100]}...")
                
                # First try JSON parsing (new format)
                try:
                    import json
                    url_data = json.loads(url_details_str)
                    
                    if isinstance(url_data, list) and len(url_data) > 0:
                        # For rejected records, we want the ORIGINAL source URL (not the found clip)
                        first_entry = url_data[0]
                        if isinstance(first_entry, dict) and 'original_url' in first_entry:
                            original_url = first_entry['original_url']
                            print(f"DEBUG: Successfully extracted original_url from JSON: {original_url}")
                            return original_url
                except (json.JSONDecodeError, KeyError, TypeError):
                    # Not JSON format, continue to old string parsing
                    pass
                
                # Handle OLD string format used by rejected records
                # Format: "https://example.com: status; https://example2.com: status"
                print(f"DEBUG: Using old string format parsing for: {url_details_str}")
                
                # Split by semicolon to get individual URL entries
                url_entries = url_details_str.split(';')
                
                for entry in url_entries:
                    entry = entry.strip()
                    if entry:
                        # Split by first colon to separate URL from status
                        if ':' in entry:
                            # Find the URL part (everything before " :")
                            colon_pos = entry.find(': ')
                            if colon_pos > 0:
                                url_part = entry[:colon_pos].strip()
                                # Validate it looks like a URL
                                if url_part.startswith(('http://', 'https://')):
                                    print(f"DEBUG: Successfully extracted URL from old format: {url_part}")
                                    return url_part
                        else:
                            # No colon, treat entire entry as URL
                            if entry.startswith(('http://', 'https://')):
                                print(f"DEBUG: Successfully extracted URL (no status): {entry}")
                                return entry
                
                # Final fallback - return empty string if no parsing worked
                print(f"DEBUG: No valid URL found, returning empty string")
                return ""
            
            # Add the View column with the searched URL (using row-based function)
            clean_df['Searched URL'] = clean_df.apply(extract_searched_url, axis=1)
            clean_df['📄 View'] = clean_df['Searched URL']  # Create View column for cellRenderer
            
            # Rename columns for better display
            column_mapping = {
                'Office': 'Office',  # Add office column first
                'WO #': 'WO #',
                'Model': 'Model', 
                'To': 'Media Contact',
                'Affiliation': 'Publication',
                '📄 View': '📄 View',  # Add View column
                'Rejection_Reason': '⚠️ Rejection Reason',
                'URL_Details': '📋 Details',
                'Processed_Date': '📅 Processed',
                # Include new fields but don't display them (for JavaScript access)
                'urls_attempted': 'urls_attempted',
                'failure_reason': 'failure_reason'
            }
            
            # Only keep columns that exist and separate display vs hidden columns
            display_columns = []
            hidden_columns = ['urls_attempted', 'failure_reason']  # Keep these for JavaScript but don't display
            
            for old_col, new_col in column_mapping.items():
                if old_col in clean_df.columns:
                    if old_col != new_col:
                        clean_df = clean_df.rename(columns={old_col: new_col})
                    if new_col not in hidden_columns:
                        display_columns.append(new_col)
            
            # Create cellRenderer for View column with multiple URL indicator
            cellRenderer_view = JsCode("""
            class UrlCellRenderer {
              init(params) {
                const urls_attempted = params.data['urls_attempted'] || 0;
                
                this.eGui = document.createElement('div');
                this.eGui.style.display = 'flex';
                this.eGui.style.alignItems = 'center';
                this.eGui.style.gap = '5px';
                
                // Create the link
                this.link = document.createElement('a');
                this.link.innerText = '📄 View';
                this.link.href = params.value;
                this.link.target = '_blank';
                this.link.style.color = '#1f77b4';
                this.link.style.textDecoration = 'underline';
                this.link.style.cursor = 'pointer';
                
                this.eGui.appendChild(this.link);
                
                // Add multiple URL indicator if more than 1 URL was attempted
                if (urls_attempted > 1) {
                  const indicator = document.createElement('span');
                  indicator.innerText = `(+${urls_attempted - 1})`;
                  indicator.style.fontSize = '11px';
                  indicator.style.color = '#6c757d';
                  indicator.style.fontStyle = 'italic';
                  indicator.title = `${urls_attempted} URLs were searched for this WO#`;
                  this.eGui.appendChild(indicator);
                }
              }

              getGui() {
                return this.eGui;
              }

              refresh(params) {
                return false;
              }
            }
            """)
            

            # Configure AgGrid for rejected records (no pagination for full transparency)
            gb = GridOptionsBuilder.from_dataframe(clean_df)
            
            # Hide columns that shouldn't be displayed
            for hidden_col in hidden_columns:
                if hidden_col in clean_df.columns:
                    gb.configure_column(hidden_col, hide=True)
            # Enable row selection for moving records back to Bulk Review
            gb.configure_selection('multiple', use_checkbox=True, groupSelectsChildren=True, groupSelectsFiltered=True)
            # Removed pagination to show all rejected records at once
            gb.configure_side_bar()
            gb.configure_default_column(
                filter="agSetColumnFilter",  # CHECKBOX FILTERS with search
                sortable=True,  # Enable sorting
                resizable=True,  # Enable column resizing
                editable=False, 
                groupable=True, 
                value=True, 
                enableRowGroup=True, 
                enablePivot=True, 
                enableValue=True,
                filterParams={
                    "buttons": ["reset", "apply"],
                    "closeOnApply": True,
                    "newRowsAction": "keep"
                }
            )
            
            # Configure columns with auto-sizing (no fixed widths) for balanced layout
            if "Office" in display_columns:
                gb.configure_column("Office", pinned='left')  # Keep pinned but auto-size
            gb.configure_column("WO #", pinned='left')  # Keep pinned but auto-size
            
            # Configure the View column with the custom renderer (same as bulk review) 
            if "📄 View" in display_columns:
                gb.configure_column(
                    "📄 View", 
                    cellRenderer=cellRenderer_view,
                    width=100,  # Small fixed width for View column
                    sortable=False,
                    filter=False
                )
                # Hide the Searched URL column since it's only used for the cellRenderer
                gb.configure_column("Searched URL", hide=True)
            
            # Configure text columns with wrapping but no fixed width
            gb.configure_column("⚠️ Rejection Reason", wrapText=True, autoHeight=True)
            gb.configure_column("📋 Details", wrapText=True, autoHeight=True)
            
            # Enable auto-sizing for all columns
            gb.configure_grid_options(
                autoSizeStrategy={
                    'type': 'fitGridWidth',
                    'defaultMinWidth': 100,
                    'columnLimits': [
                        {'key': 'Office', 'minWidth': 80},
                        {'key': 'WO #', 'minWidth': 80},
                        {'key': 'Model', 'minWidth': 120},
                        {'key': 'Media Contact', 'minWidth': 120},
                        {'key': 'Publication', 'minWidth': 120},
                        {'key': '📄 View', 'minWidth': 80, 'maxWidth': 100},
                        {'key': '⚠️ Rejection Reason', 'minWidth': 150},
                        {'key': '📋 Details', 'minWidth': 200},
                        {'key': '📅 Processed', 'minWidth': 100}
                    ]
                }
            )
            
            # Build grid options
            grid_options = gb.build()
            
            # Display AgGrid table for rejected records
            st.markdown("**📋 Rejected Records**")
            selected_rejected = AgGrid(
                clean_df,  # Pass full dataframe so JavaScript can access hidden columns
                gridOptions=grid_options,
                height=400,
                width='100%',
                data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                fit_columns_on_grid_load=False,  # Disable to allow auto-sizing
                theme='streamlit',
                enable_enterprise_modules=True,
                allow_unsafe_jscode=True,
                reload_data=True,
                columns_auto_size_mode='FIT_ALL_COLUMNS_TO_VIEW'  # Enable auto-sizing
            )
            
            # Optional: Add functionality to move selected rejected records back to Bulk Review
            if st.button("🔄 Move Selected to Bulk Review", key="move_to_bulk_review"):
                selected_rows = selected_rejected.get('selected_rows', [])
                if selected_rows is not None and len(selected_rows) > 0:
                    st.success(f"Selected {len(selected_rows)} records to move back to Bulk Review")
                    # Implementation would go here - mark these as pending_review again
                else:
                    st.warning("No records selected")
    else:
        st.info("📊 No rejected records found")
        # ... existing code ...

# ========== DETAILED ANALYSIS TAB (Existing 40/60 Interface) ==========
with analysis_tab:
    # Create 40/60 split columns for detailed analysis
    left_pane, right_pane = st.columns([0.4, 0.6])
    
    with left_pane:
        st.markdown('<p style="font-size: 1rem; font-weight: 600; color: #2c3e50; margin-bottom: 0.8rem;">📊 Command Center</p>', unsafe_allow_html=True)
        
        # Try to load results file for summary
        results_file = os.path.join(project_root, "data", "loan_results.csv")
        if os.path.exists(results_file):
            try:
                df = pd.read_csv(results_file)
                
                # Ensure WO # is treated as string
                if 'WO #' in df.columns:
                    df['WO #'] = df['WO #'].astype(str)
                
                if not df.empty:
                    # Overview Stats
                    st.markdown('<p style="font-size: 0.85rem; font-weight: 600; color: #5a6c7d; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">🎯 Overview</p>', unsafe_allow_html=True)
                    total_loans = len(df)
                    avg_relevance = df['Relevance Score'].mean() if 'Relevance Score' in df.columns else 0
                    high_relevance = len(df[df['Relevance Score'] >= 8]) if 'Relevance Score' in df.columns else 0
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Loans", total_loans)
                    with col2:
                        st.metric("Avg Relevance", f"{avg_relevance:.1f}/10")
                    with col3:
                        st.metric("High Quality", f"{high_relevance}/{total_loans}")
                    
                    # Group by Media Personality
                    st.markdown('<p style="font-size: 0.85rem; font-weight: 600; color: #5a6c7d; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">👥 By Media Personality</p>', unsafe_allow_html=True)
                    
                    # Create grouping by 'To' field (media contact)
                    if 'To' in df.columns:
                        personality_stats = df.groupby('To').agg({
                            'WO #': 'count',
                            'Relevance Score': ['mean', 'min'] if 'Relevance Score' in df.columns else 'count'
                        }).round(1)
                        
                        # Flatten column names
                        if 'Relevance Score' in df.columns:
                            personality_stats.columns = ['Count', 'Avg_Score', 'Min_Score']
                            personality_stats['Success_Rate'] = (personality_stats['Min_Score'] >= 7).astype(int) * 100
                        else:
                            personality_stats.columns = ['Count']
                            personality_stats['Avg_Score'] = 10.0
                            personality_stats['Success_Rate'] = 100
                        
                        # Sort by count and avg score
                        personality_stats = personality_stats.sort_values(['Count', 'Avg_Score'], ascending=[False, False])
                        
                        # Display as interactive table
                        selected_personality = st.selectbox(
                            "Select Media Personality:",
                            options=[''] + list(personality_stats.index),
                            format_func=lambda x: f"{x} ({personality_stats.loc[x, 'Count']} loans, {personality_stats.loc[x, 'Avg_Score']:.1f}/10)" if x else "-- Select --"
                        )
                        
                        # Show personality stats as metrics
                        if selected_personality:
                            stats = personality_stats.loc[selected_personality]
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Loans", int(stats['Count']))
                            with col2:
                                st.metric("Avg Score", f"{stats['Avg_Score']:.1f}/10")
                    
                    # Compact Loans List
                    st.markdown('<p style="font-size: 0.85rem; font-weight: 600; color: #5a6c7d; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">📋 Loans List</p>', unsafe_allow_html=True)
                    
                    # Filter to selected personality if any
                    filtered_df = df.copy()
                    if selected_personality:
                        filtered_df = filtered_df[filtered_df['To'] == selected_personality]
                    
                    # Display compact table
                    if not filtered_df.empty:
                        display_cols = ['WO #', 'Model', 'To']
                        if 'Relevance Score' in filtered_df.columns:
                            display_cols.append('Relevance Score')
                        
                        # Make table clickable by using selectbox
                        selected_wo = st.selectbox(
                            "Select Work Order:",
                            options=[''] + list(filtered_df['WO #'].values),
                            format_func=lambda x: f"{x} - {filtered_df[filtered_df['WO #']==x]['Model'].iloc[0]} ({filtered_df[filtered_df['WO #']==x]['Relevance Score'].iloc[0]}/10)" if x else "-- Select Loan --"
                        )
                        
                        # Store selected work order in session state
                        if selected_wo:
                            st.session_state.selected_work_order = selected_wo
                    
                    # Action Buttons
                    st.markdown('<p style="font-size: 0.85rem; font-weight: 600; color: #5a6c7d; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">⚡ Quick Actions</p>', unsafe_allow_html=True)
                    if st.button("📤 Export All Approved", use_container_width=True, key="export_detailed"):
                        approved_data = df.to_csv(index=False)
                        st.download_button(
                            "📥 Download CSV",
                            data=approved_data,
                            file_name=f"approved_clips_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key="download_detailed"
                        )
                    
                    # CLIENT EXPORT SECTION
                    st.markdown('<p style="font-size: 0.85rem; font-weight: 600; color: #5a6c7d; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">🎯 Client Reports</p>', unsafe_allow_html=True)
                    
                    if st.button("📊 Professional Excel Report", use_container_width=True, key="client_excel"):
                        try:
                            # Load approved clips if available
                            approved_file = os.path.join(project_root, "data", "approved_clips.csv")
                            approved_df = None
                            if os.path.exists(approved_file):
                                approved_df = pd.read_csv(approved_file)
                            
                            # Create professional Excel report
                            wb = create_client_excel_report(df, approved_df)
                            
                            # Save to bytes
                            excel_buffer = io.BytesIO()
                            wb.save(excel_buffer)
                            excel_buffer.seek(0)
                            
                            st.download_button(
                                label="📥 Download Excel Report",
                                data=excel_buffer.getvalue(),
                                file_name=f"DriveShop_Media_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                                key="download_client_excel"
                            )
                        except Exception as e:
                            st.error(f"Error creating Excel report: {e}")
                    
                    if st.button("📈 Executive Summary", use_container_width=True, key="exec_summary"):
                        # Create executive summary data
                        summary_data = {
                            'Metric': [
                                'Total Vehicles Monitored',
                                'Media Clips Found',
                                'Average Relevance Score',
                                'High-Quality Clips (8+)',
                                'Coverage Rate',
                                'Positive Sentiment',
                                'Brand Alignment Rate'
                            ],
                            'Value': [
                                len(df),
                                len(df[df['Relevance Score'] > 0]) if 'Relevance Score' in df.columns else len(df),
                                f"{df['Relevance Score'].mean():.1f}/10" if 'Relevance Score' in df.columns else "N/A",
                                len(df[df['Relevance Score'] >= 8]) if 'Relevance Score' in df.columns else 0,
                                f"{(len(df[df['Relevance Score'] > 0])/len(df)*100):.1f}%" if 'Relevance Score' in df.columns and len(df) > 0 else "0%",
                                len(df[df['Sentiment'] == 'positive']) if 'Sentiment' in df.columns else 0,
                                f"{(len(df[df['Brand Alignment'] == True])/len(df)*100):.1f}%" if 'Brand Alignment' in df.columns and len(df) > 0 else "N/A"
                            ]
                        }
                        
                        summary_df = pd.DataFrame(summary_data)
                        csv_data = summary_df.to_csv(index=False)
                        
                        st.download_button(
                            label="📥 Download Executive Summary",
                            data=csv_data,
                            file_name=f"Executive_Summary_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key="download_exec_summary"
                        )
                else:
                    st.info("No data available. Process loans to see summary.")
            except Exception as e:
                st.error(f"Error loading data: {e}")
        else:
            st.info("No results file found. Upload and process loans to begin.")
    
    with right_pane:
        st.markdown('<p style="font-size: 1rem; font-weight: 600; color: #2c3e50; margin-bottom: 0.8rem;">🔍 Loan Inspector</p>', unsafe_allow_html=True)
        
        # Show details if a work order is selected
        selected_wo = st.session_state.get('selected_work_order', None)
        
        if selected_wo and os.path.exists(results_file):
            try:
                df = pd.read_csv(results_file)
                if 'WO #' in df.columns:
                    df['WO #'] = df['WO #'].astype(str)
                
                selected_row = df[df['WO #'] == selected_wo]
                if not selected_row.empty:
                    selected_row = selected_row.iloc[0]
                    
                    # Header with model info
                    st.markdown(f"#### {selected_row.get('Model', 'Unknown Model')} - WO #{selected_wo}")
                    
                    # Rebalanced info in 4 columns for better distribution (added attribution column)
                    info_col1, info_col2, info_col3, info_col4 = st.columns(4)
                    with info_col1:
                        st.markdown(f"**👤 Contact**  \n{selected_row.get('To', 'N/A')}")
                    with info_col2:
                        st.markdown(f"**📰 Publication**  \n{selected_row.get('Affiliation', 'N/A')}")
                    with info_col3:
                        # NEW: Attribution Information
                        attribution_strength = selected_row.get('Attribution_Strength', 'unknown')
                        actual_byline = selected_row.get('Actual_Byline', '')
                        
                        if attribution_strength == 'strong':
                            attribution_text = "✅ **Direct Attribution**"
                        elif attribution_strength == 'delegated':
                            attribution_text = "⚠️ **Delegated Content**"
                            if actual_byline:
                                attribution_text += f"  \n*By: {actual_byline}*"
                        else:
                            attribution_text = "❓ **Attribution Unknown**"
                        
                        st.markdown(f"**✍️ Attribution**  \n{attribution_text}")
                    with info_col4:
                        link_html = ""
                        if 'Clip URL' in selected_row and selected_row['Clip URL']:
                            link_html += f"**[📄 Review Link]({selected_row['Clip URL']})**  \n"
                        if 'Links' in selected_row and selected_row['Links']:
                            link_html += f"**[🔗 Original]({selected_row['Links']})**"
                        if link_html:
                            st.markdown(link_html)
                    
                    # Key metrics in prominent display
                    st.markdown("---")
                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                    
                    with metric_col1:
                        overall_score = selected_row.get('Overall Score', 'N/A')
                        st.metric("📊 Overall", f"{overall_score}/10" if overall_score != 'N/A' else 'N/A')
                    
                    with metric_col2:
                        relevance_score = selected_row.get('Relevance Score', 'N/A')
                        st.metric("🎯 Relevance", f"{relevance_score}/10" if relevance_score != 'N/A' else 'N/A')
                    
                    with metric_col3:
                        sentiment = selected_row.get('Overall Sentiment', 'N/A')
                        sentiment_emoji = "😊" if sentiment == "positive" else "😞" if sentiment == "negative" else "😐"
                        st.metric("💭 Sentiment", f"{sentiment_emoji} {sentiment.title()}" if sentiment != 'N/A' else 'N/A')
                    
                    with metric_col4:
                        alignment = selected_row.get('Brand Alignment', False)
                        st.metric("🎨 Brand Fit", "✅ Yes" if alignment else "❌ No")
                    
                    # Decision buttons
                    st.markdown("---")
                    st.markdown('<p style="font-size: 0.85rem; font-weight: 600; color: #5a6c7d; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;">📋 Review Decision</p>', unsafe_allow_html=True)
                    
                    decision_col1, decision_col2, decision_col3 = st.columns([1, 1, 2])
                    with decision_col1:
                        if st.button("✓", key=f"approve_detailed_{selected_wo}", use_container_width=True, help="Approve"):
                            # Move to approved list logic
                            approved_file = os.path.join(project_root, "data", "approved_clips.csv")
                            if os.path.exists(approved_file):
                                approved_df = pd.read_csv(approved_file)
                                if 'WO #' in approved_df.columns and selected_wo not in approved_df['WO #'].astype(str).values:
                                    approved_df = pd.concat([approved_df, pd.DataFrame([selected_row])], ignore_index=True)
                            else:
                                approved_df = pd.DataFrame([selected_row])
                            approved_df.to_csv(approved_file, index=False)
                            st.success(f"✅ Approved WO #{selected_wo}")
                            
                    with decision_col2:
                        if st.button("✗", key=f"reject_detailed_{selected_wo}", use_container_width=True, help="Reject"):
                            st.warning(f"⚠️ Flagged WO #{selected_wo}")
                    
                    with decision_col3:
                        rec = selected_row.get('Recommendation', '')
                        if rec:
                            if 'would recommend' in rec.lower():
                                st.info("🤖 **AI:** 👍 Recommend")
                            elif 'would not recommend' in rec.lower():
                                st.info("🤖 **AI:** 👎 Not Recommend")
                            else:
                                st.info("🤖 **AI:** 🤔 Consider")
                    
                    # Detailed analysis sections (keep all existing functionality)
                    with st.expander("📈 Aspect Breakdown", expanded=False):
                        aspect_col1, aspect_col2, aspect_col3, aspect_col4, aspect_col5 = st.columns(5)
                        
                        aspects = [
                            ('Performance Score', 'Performance Note', '🏎️ Performance', aspect_col1),
                            ('Design Score', 'Design Note', '🎨 Design', aspect_col2),
                            ('Interior Score', 'Interior Note', '🪑 Interior', aspect_col3),
                            ('Technology Score', 'Technology Note', '💻 Technology', aspect_col4),
                            ('Value Score', 'Value Note', '💰 Value', aspect_col5)
                        ]
                        
                        for score_field, note_field, label, col in aspects:
                            with col:
                                score = selected_row.get(score_field, 0)
                                note = selected_row.get(note_field, '')
                                if score and score != 0:
                                    st.metric(label, f"{score}/10", help=note if note else None)
                                else:
                                    st.metric(label, "N/A")
                    
                    # Summary
                    if 'Summary' in selected_row and selected_row['Summary']:
                        with st.expander("📝 AI Summary", expanded=True):
                            st.markdown(f"*{selected_row['Summary']}*")
                    
                    # Pros and Cons
                    pros_text = selected_row.get('Pros', '')
                    cons_text = selected_row.get('Cons', '')
                    if pros_text or cons_text:
                        with st.expander("⚖️ Pros & Cons", expanded=False):
                            pros_col, cons_col = st.columns(2)
                            
                            with pros_col:
                                st.markdown("**✅ Strengths**")
                                if pros_text and pros_text.strip():
                                    pros_list = [p.strip() for p in pros_text.split('|') if p.strip()]
                                    for pro in pros_list:
                                        st.markdown(f"• {pro}")
                                else:
                                    st.markdown("*No specific strengths highlighted*")
                            
                            with cons_col:
                                st.markdown("**❌ Areas for Improvement**")
                                if cons_text and cons_text.strip():
                                    cons_list = [c.strip() for c in cons_text.split('|') if c.strip()]
                                    for con in cons_list:
                                        st.markdown(f"• {con}")
                                else:
                                    st.markdown("*No specific concerns noted*")
                    
                    # Add bottom spacing for better visual separation
                    st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
                else:
                    st.warning("Selected work order not found in data.")
            except Exception as e:
                st.error(f"Error loading loan details: {e}")
        else:
            st.info("👈 Select a loan from the Command Center to view details")
            
            # Show helpful instructions
            st.markdown("""
            **How to use:**
            1. 📤 **Upload/Process** loans in the sidebar
            2. 👥 **Select** a media personality or filter loans  
            3. 📋 **Choose** a specific work order to review
            4. ✅ **Approve** or ⚠️ **flag** the clip
            5. 📤 **Export** approved clips when ready
            """)
            
            # Add extra bottom spacing
            st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)

# ========== FILE HISTORY TAB ==========
with history_tab:
    st.markdown("## 📚 File History")
    st.markdown("*Access all your previous approval session files and generate reports*")
    
    # Get all JSON files from data directory
    data_dir = os.path.join(project_root, "data")
    json_files = []
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.startswith("approved_clips_") and file.endswith(".json"):
                file_path = os.path.join(data_dir, file)
                file_stats = os.stat(file_path)
                # Extract date from filename: approved_clips_20250625_163543.json
                try:
                    date_str = file.replace("approved_clips_", "").replace(".json", "")
                    date_part = date_str.split("_")[0]  # 20250625
                    time_part = date_str.split("_")[1]  # 163543
                    formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                    formatted_time = f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                    display_name = f"{formatted_date} at {formatted_time}"
                except:
                    display_name = file.replace("approved_clips_", "").replace(".json", "")
                
                json_files.append({
                    'filename': file,
                    'filepath': file_path,
                    'display_name': display_name,
                    'size': file_stats.st_size,
                    'modified': file_stats.st_mtime
                })
    
    # Sort by modification time (newest first)
    json_files.sort(key=lambda x: x['modified'], reverse=True)
    
    if json_files:
        st.markdown(f"**Found {len(json_files)} previous approval sessions:**")
        
        # Create a more compact display
        for i, file_info in enumerate(json_files):
            # Use filename as unique identifier to avoid key conflicts
            file_key = file_info['filename'].replace('.json', '').replace('approved_clips_', '')
            
            with st.expander(f"📅 {file_info['display_name']} ({file_info['size']/1024:.1f} KB)", expanded=(i==0)):
                col_json_hist, col_excel_hist, col_info = st.columns([1, 1, 1])
                
                with col_json_hist:
                    # Load and provide JSON download
                    try:
                        with open(file_info['filepath'], 'r') as f:
                            json_data = json.load(f)
                        st.download_button(
                            label="📋 Download JSON",
                            data=json.dumps(json_data, indent=2),
                            file_name=file_info['filename'],
                            mime="application/json",
                            key=f"json_download_{file_key}",
                            help="Download this JSON file"
                        )
                    except Exception as e:
                        st.error(f"Error loading JSON: {e}")
                
                with col_excel_hist:
                    # Excel generation temporarily disabled for historical files
                    # to avoid compatibility issues
                    st.info("💡 **Excel Generation**\n\nFor historical sessions, use the JSON download and import into the current session for Excel generation.")
                    st.caption("This ensures compatibility with the latest Excel format.")
                
                with col_info:
                    # Show file info
                    try:
                        with open(file_info['filepath'], 'r') as f:
                            json_data = json.load(f)
                        if json_data:
                            st.metric("Clips", len(json_data))
                            avg_relevance = sum(clip.get('relevance_score', 0) for clip in json_data) / len(json_data)
                            st.metric("Avg Score", f"{avg_relevance:.1f}")
                        else:
                            st.metric("Clips", 0)
                    except:
                        st.metric("Clips", "Error")
    else:
        st.info("No previous approval sessions found. Approve some clips to create downloadable files!")
        
        # Show helpful instructions
        st.markdown("""
        **How File History works:**
        1. 📋 **Approve clips** in the Bulk Review tab
        2. 📁 **Files are automatically saved** with timestamps
        3. 📚 **Access them here** anytime - even after browser restart
        4. 📊 **Generate fresh Excel reports** from any historical session
        5. 📋 **Download original JSON** for data integration
        
        **File naming:** `approved_clips_YYYYMMDD_HHMMSS.json`
        **Example:** `approved_clips_20250625_163543.json` = June 25th, 2025 at 4:35 PM
        """)

 