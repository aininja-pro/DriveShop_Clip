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

# Add explicit .env loading with debug output
from dotenv import load_dotenv

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
    from src.ingest.ingest import run_ingest_concurrent
except ImportError:
    # Define a stub for when the module is not yet implemented
    def run_ingest_concurrent(file_path):
        st.error("Concurrent ingest module not implemented yet")
        return False

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

def create_client_excel_report(df, approved_df=None):
    """Create a professional Excel report for client presentation"""
    
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
            clips_not_found = 0
    except:
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
    bulk_review_columns = [
        'Office', 'WO #', 'Model', 'Contact', 'Publication', 
        'Relevance', 'Sentiment', 'URLs', 'Other URLs'
    ]
    
    # Map our data columns to Bulk Review column names
    column_mapping = {
        'Office': 'Office',
        'WO #': 'WO #',
        'Model': 'Model',
        'To': 'Contact',
        'Affiliation': 'Publication',
        'Relevance Score': 'Relevance',
        'Overall Sentiment': 'Sentiment',  # Fix: Use the correct sentiment column
        'Clip URL': 'URLs',
        'Links': 'Other URLs'
    }
    
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
            # Check if this is a URL column and make it clickable
            elif col_name in ['URLs', 'Other URLs'] and value and str(value).startswith('http'):
                # We'll handle URL linking after adding the data
                row_data.append(str(value))
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
            
            # Make URL columns clickable
            if col_name in ['URLs', 'Other URLs'] and cell.value and str(cell.value).startswith('http'):
                url = str(cell.value)
                cell.hyperlink = url
                cell.font = url_font
                cell.value = url  # Keep full URL visible
    
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
    
    # 3. Approved Clips Sheet (if available)
    if approved_df is not None and len(approved_df) > 0:
        approved_ws = wb.create_sheet("Approved Clips")
        
        # Add approved clips data
        for r in dataframe_to_rows(approved_df, index=False, header=True):
            approved_ws.append(r)
        
        # Style header
        for cell in approved_ws[1]:
            cell.font = header_font
            cell.fill = PatternFill(start_color="28a745", end_color="28a745", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Auto-size columns
        for col in approved_ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            approved_ws.column_dimensions[column].width = adjusted_width
    
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
    initial_sidebar_state="collapsed"
)

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

# Compact sidebar
with st.sidebar:
    st.markdown("**🔄 Process**")
    uploaded_file = st.file_uploader("CSV/XLSX", type=['csv', 'xlsx'], label_visibility="collapsed")
    
    if uploaded_file is not None:
        temp_file_path = os.path.join(project_root, "data", "fixtures", "temp_upload.csv")
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        if st.button("🚀 Process", use_container_width=True):
            with st.spinner("Processing..."):
                success = run_ingest_concurrent(temp_file_path)
                if success:
                    st.success("✅ Done!")
                else:
                    st.error("❌ Failed")
    
    if st.button("🔄 Process Existing", use_container_width=True):
        with st.spinner("Processing..."):
            default_file = os.path.join(project_root, "data", "fixtures", "Loans_without_Clips.csv")
            success = run_ingest_concurrent(default_file)
            if success:
                st.success("✅ Done!")
            else:
                st.error("❌ Failed")

# Create tabs for different user workflows  
bulk_tab, rejected_tab, analysis_tab = st.tabs(["📋 Bulk Review", "⚠️ Rejected/Issues", "🔍 Detailed Analysis"])

# ========== BULK REVIEW TAB (Compact Interface) ==========
with bulk_tab:
    
    # Try to load results file
    results_file = os.path.join(project_root, "data", "loan_results.csv")
    if os.path.exists(results_file):
        try:
            df = pd.read_csv(results_file)
            
            # Ensure WO # is treated as string
            if 'WO #' in df.columns:
                df['WO #'] = df['WO #'].astype(str)
            
            if not df.empty:
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
                    # Check approved count
                    approved_file = os.path.join(project_root, "data", "approved_clips.csv")
                    approved_count = 0
                    if os.path.exists(approved_file):
                        approved_df = pd.read_csv(approved_file)
                        approved_count = len(approved_df)
                    st.metric("Approved", approved_count)
                
                # Display filtered results with AgGrid
                display_df = df.copy()
                
                # Create the EXACT table structure from the working version (Image 1)
                clean_df = pd.DataFrame()
                clean_df['Office'] = display_df['Office'] if 'Office' in display_df.columns else 'N/A'
                clean_df['WO #'] = display_df['WO #'] if 'WO #' in display_df.columns else ''
                clean_df['Model'] = display_df['Model'] if 'Model' in display_df.columns else ''
                clean_df['Contact'] = display_df['To'] if 'To' in display_df.columns else ''
                clean_df['Publication'] = display_df['Affiliation'] if 'Affiliation' in display_df.columns else 'N/A'
                
                # Format relevance score as "8/10" format
                if 'Relevance Score' in display_df.columns:
                    clean_df['Relevance'] = display_df['Relevance Score'].apply(lambda x: f"{x}/10" if pd.notna(x) and x != 'N/A' else 'N/A')
                else:
                    clean_df['Relevance'] = 'N/A'
                
                # Format sentiment with abbreviations and emojis for display
                if 'Overall Sentiment' in display_df.columns:
                    def format_sentiment(sentiment):
                        if pd.isna(sentiment) or sentiment == 'N/A':
                            return 'N/A'
                        sentiment_map = {
                            'positive': 'POS 😊',
                            'negative': 'NEG 😞',
                            'neutral': 'NEU 😐'
                        }
                        cleaned_sentiment = str(sentiment).lower().strip()
                        return sentiment_map.get(cleaned_sentiment, str(sentiment))
                    
                    clean_df['Sentiment'] = display_df['Overall Sentiment'].apply(format_sentiment)
                else:
                    clean_df['Sentiment'] = 'N/A'
                
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
                # Add URLs count column (e.g., "2/2", "1/1")
                def get_url_count(row):
                    try:
                        # Check if new URL tracking fields exist
                        if 'URLs_Processed' in row and pd.notna(row['URLs_Processed']):
                            urls_processed = int(row['URLs_Processed'])
                            urls_successful = int(row.get('URLs_Successful', 1))
                            return f"{urls_successful}/{urls_processed}"
                        else:
                            # Fallback for old data format - infer from Links field
                            links = str(row.get('Links', ''))
                            if ',' in links or ';' in links:
                                # Multiple URLs in Links field
                                separator = ',' if ',' in links else ';'
                                url_count = len([u for u in links.split(separator) if u.strip()])
                                return f"1/{url_count}"  # We know 1 was successful (this row exists)
                            else:
                                return "1/1"  # Single URL
                    except:
                        return "1/1"
                
                clean_df['URLs'] = display_df.apply(get_url_count, axis=1)
                
                # Add Other URLs column with direct clickable links
                def get_other_urls_html(row):
                    try:
                        if 'URL_Tracking' in row and pd.notna(row['URL_Tracking']):
                            url_tracking = parse_url_tracking(row)
                            successful_urls = [u for u in url_tracking if u.get('success', False)]
                            
                            if len(successful_urls) <= 1:
                                return "—"
                            else:
                                # Get the main URL (already shown in View column)
                                main_url = row.get('Clip URL', '')
                                other_urls = [u for u in successful_urls if u.get('actual_url') != main_url]
                                
                                if len(other_urls) == 0:
                                    return "—"
                                
                                # Create clickable links for other URLs
                                link_parts = []
                                for url_data in other_urls[:2]:  # Show max 2 additional links
                                    url = url_data.get('actual_url', url_data.get('original_url', ''))
                                    content_type = url_data.get('content_type', 'web')
                                    icon = "🎥" if "youtube" in content_type.lower() else "📄"
                                    
                                    # Create short name for link
                                    if "motor1" in url.lower():
                                        name = "Motor1"
                                    elif "youtube" in url.lower():
                                        name = "YouTube"
                                    elif "caranddriver" in url.lower():
                                        name = "C&D"
                                    elif "autoblog" in url.lower():
                                        name = "Autoblog"
                                    else:
                                        name = "Link"
                                    
                                    link_parts.append(f'<a href="{url}" target="_blank" style="color: #1f77b4; text-decoration: none;">{icon} {name}</a>')
                                
                                # If there are more than 2 additional URLs, show count
                                if len(other_urls) > 2:
                                    extra_count = len(other_urls) - 2
                                    link_parts.append(f'+{extra_count} more')
                                
                                return ' | '.join(link_parts)
                        else:
                            # Fallback for old data format
                            links = str(row.get('Links', ''))
                            if ',' in links or ';' in links:
                                separator = ',' if ',' in links else ';'
                                urls = [u.strip() for u in links.split(separator) if u.strip()]
                                if len(urls) > 1:
                                    return f"+{len(urls)-1} more*"
                                else:
                                    return "—"
                            else:
                                return "—"
                    except Exception as e:
                        return "—"
                
                clean_df['Other URLs'] = display_df.apply(get_other_urls_html, axis=1)
                
                # Store the full URL tracking data for popup (hidden column)
                clean_df['URL_Tracking_Data'] = display_df.apply(lambda row: json.dumps(parse_url_tracking(row)), axis=1)
                
                # Add action columns
                clean_df['✅ Approve'] = False
                clean_df['❌ Reject'] = False
                
                # Create the cellRenderer with proper JavaScript
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
                
                # Create HTML cell renderer for Other URLs column (clickable links)
                cellRenderer_other_urls = JsCode("""
                class OtherUrlsCellRenderer {
                  init(params) {
                    this.eGui = document.createElement('div');
                    this.eGui.style.display = 'flex';
                    this.eGui.style.justifyContent = 'center';
                    this.eGui.style.alignItems = 'center';
                    this.eGui.style.height = '100%';
                    this.eGui.style.fontSize = '0.8rem';
                    
                    const htmlContent = params.value;
                    if (htmlContent && htmlContent !== '—') {
                      // Render HTML content directly (contains clickable links)
                      this.eGui.innerHTML = htmlContent;
                    } else {
                      // Show plain text for "—"
                      this.eGui.innerText = htmlContent;
                      this.eGui.style.color = '#6c757d';
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
                
                # Configure the View column with the custom renderer
                gb.configure_column(
                    "📄 View", 
                    cellRenderer=cellRenderer_view,
                    width=80,
                    sortable=False,
                    filter=False
                )
                
                # Configure URLs column
                gb.configure_column("URLs", width=70)
                
                # Configure Other URLs column with HTML renderer
                gb.configure_column(
                    "Other URLs", 
                    cellRenderer=cellRenderer_other_urls,
                    width=150,  # Wider to accommodate multiple links
                    sortable=False,
                    filter=False
                )
                
                # Configure selection
                gb.configure_selection(selection_mode="multiple", use_checkbox=False)
                
                # Configure other columns as before
                gb.configure_column("Office", width=100)
                gb.configure_column("WO #", width=100)
                gb.configure_column("Model", width=120)
                gb.configure_column("Contact", width=150)
                gb.configure_column("Publication", width=180)
                gb.configure_column("Relevance", width=80)
                gb.configure_column("Sentiment", width=100)
                
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
                    update_mode=GridUpdateMode.SELECTION_CHANGED,
                    height=650,  # Increased height for better viewing
                    fit_columns_on_grid_load=True,
                    theme="alpine",
                    enable_enterprise_modules=True  # REQUIRED for Set Filters with checkboxes
                )
                
                # Note: URLs are now clickable directly in the "Other URLs" column
                
                # Process inline actions from AgGrid
                changed_df = selected_rows["data"]
                if not changed_df.empty:
                    # Find which rows were approved or rejected
                    approved_rows = changed_df[changed_df['✅ Approve'] == True]
                    rejected_rows = changed_df[changed_df['❌ Reject'] == True]
                    
                    # Process approvals
                    if not approved_rows.empty:
                        approved_wos = approved_rows['WO #'].tolist()
                        approved_file = os.path.join(project_root, "data", "approved_clips.csv")
                        selected_rows = df[df['WO #'].astype(str).isin(map(str, approved_wos))]
                        
                        if os.path.exists(approved_file):
                            approved_df = pd.read_csv(approved_file)
                            if 'WO #' in approved_df.columns:
                                approved_df['WO #'] = approved_df['WO #'].astype(str)
                            # Only add rows that aren't already approved
                            new_rows = selected_rows[~selected_rows['WO #'].astype(str).isin(approved_df['WO #'].astype(str))]
                            if not new_rows.empty:
                                approved_df = pd.concat([approved_df, new_rows], ignore_index=True)
                                approved_df.to_csv(approved_file, index=False)
                        else:
                            selected_rows.to_csv(approved_file, index=False)
                        
                        if len(approved_wos) > 0:
                            st.success(f"✅ Approved {len(approved_wos)} clips!")
                            st.rerun()
                    
                    # Process rejections  
                    if not rejected_rows.empty:
                        rejected_wos = rejected_rows['WO #'].tolist()
                        st.success(f"❌ Rejected {len(rejected_wos)} clips!")
                        st.rerun()
                
                # Quick bulk actions below table
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✅ Approve All High Quality (9+)"):
                        high_quality_df = df[df['Relevance Score'] >= 9]
                        if not high_quality_df.empty:
                            approved_file = os.path.join(project_root, "data", "approved_clips.csv")
                            if os.path.exists(approved_file):
                                approved_df = pd.read_csv(approved_file)
                                approved_df = pd.concat([approved_df, high_quality_df], ignore_index=True)
                            else:
                                approved_df = high_quality_df.copy()
                            approved_df.to_csv(approved_file, index=False)
                            st.success(f"✅ Approved {len(high_quality_df)} high-quality clips!")
                            st.rerun()
                        else:
                            st.info("No high-quality clips (9+) found")
                
                with col2:
                    if st.button("📄 Export Approved Clips"):
                        try:
                            approved_file = os.path.join(project_root, "data", "approved_clips.csv")
                            if os.path.exists(approved_file):
                                approved_df = pd.read_csv(approved_file)
                                if not approved_df.empty:
                                    csv_data = approved_df.to_csv(index=False)
                                    st.download_button(
                                        label="💾 Download Approved Clips CSV",
                                        data=csv_data,
                                        file_name=f"approved_clips_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                        mime="text/csv"
                                    )
                                else:
                                    st.warning("No approved clips to export")
                            else:
                                st.warning("No approved clips file found")
                        except Exception as e:
                            st.error(f"Error exporting clips: {e}")
                
                with col3:
                    if st.button("🔄 Refresh Data"):
                        st.rerun()
            else:
                st.info("No clips to review. Process loans first.")
        except Exception as e:
            st.error(f"Error loading clips: {e}")
    else:
        st.info("No results file found. Upload and process loans to begin.")

# ========== REJECTED/ISSUES TAB (Transparency Dashboard) ==========
with rejected_tab:
    st.markdown("## ⚠️ Rejected/Issues Dashboard")
    st.markdown("*Complete transparency: See everything that was processed but didn't make the cut*")
    
    # Try to load rejected records file
    rejected_file = os.path.join(project_root, "data", "rejected_clips.csv")
    if os.path.exists(rejected_file):
        try:
            rejected_df = pd.read_csv(rejected_file)
            
            # Ensure WO # is treated as string for consistency
            if 'WO #' in rejected_df.columns:
                rejected_df['WO #'] = rejected_df['WO #'].astype(str)
            
            if not rejected_df.empty:
                # Summary metrics for rejected records
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📝 Total Rejected", len(rejected_df))
                with col2:
                    urls_processed = rejected_df['URLs_Processed'].sum() if 'URLs_Processed' in rejected_df.columns else 0
                    st.metric("🔗 URLs Attempted", urls_processed)
                with col3:
                    # Count by rejection reason
                    rejection_counts = rejected_df['Rejection_Reason'].value_counts() if 'Rejection_Reason' in rejected_df.columns else {}
                    top_reason = rejection_counts.index[0] if len(rejection_counts) > 0 else "None"
                    st.metric("🚫 Top Issue", top_reason[:20] + "..." if len(top_reason) > 20 else top_reason)
                with col4:
                    # Processing efficiency
                    total_attempted = len(rejected_df)
                    failed_crawls = len(rejected_df[rejected_df['Rejection_Reason'].str.contains('No relevant clips|Low relevance', case=False, na=False)]) if 'Rejection_Reason' in rejected_df.columns else 0
                    st.metric("⚡ Technical Issues", f"{total_attempted - failed_crawls}/{total_attempted}")
                
                st.markdown("---")
                
                # Create AgGrid table (same format as bulk review but for rejected records)
                clean_df = rejected_df.copy()
                
                # Prepare columns for display
                if 'WO #' in clean_df.columns:
                    clean_df['WO #'] = clean_df['WO #'].astype(str)
                
                # Add Office column if it exists
                if 'Office' in rejected_df.columns:
                    pass  # Keep original name
                
                # Rename columns for better display
                column_mapping = {
                    'Office': 'Office',  # Add office column first
                    'WO #': 'WO #',
                    'Model': 'Model', 
                    'To': 'Media Contact',
                    'Affiliation': 'Publication',
                    'Links': '🔗 Original URLs',
                    'URLs_Processed': 'URLs',
                    'Rejection_Reason': '⚠️ Rejection Reason',
                    'URL_Details': '📋 Details',
                    'Processed_Date': '📅 Processed'
                }
                
                # Only keep columns that exist
                display_columns = []
                for old_col, new_col in column_mapping.items():
                    if old_col in clean_df.columns:
                        if old_col != new_col:
                            clean_df = clean_df.rename(columns={old_col: new_col})
                        display_columns.append(new_col)
                
                # Create HTML cell renderer for Original URLs column (clickable links - same as bulk review)
                cellRenderer_original_urls = JsCode("""
                class OriginalUrlsCellRenderer {
                  init(params) {
                    this.eGui = document.createElement('div');
                    this.eGui.style.display = 'flex';
                    this.eGui.style.justifyContent = 'flex-start';
                    this.eGui.style.alignItems = 'center';
                    this.eGui.style.height = '100%';
                    this.eGui.style.fontSize = '0.8rem';
                    this.eGui.style.lineHeight = '1.3';
                    
                    const urlsValue = params.value;
                    if (urlsValue && urlsValue.trim() !== '') {
                      // Split URLs by semicolon and create clickable links
                      const urls = urlsValue.split(';').map(url => url.trim()).filter(url => url);
                      const links = urls.map(url => {
                        try {
                          const domain = new URL(url).hostname.replace('www.', '');
                          return `<a href="${url}" target="_blank" style="color: #1f77b4; text-decoration: underline; margin-right: 8px;">${domain}</a>`;
                        } catch (e) {
                          // Fallback for invalid URLs
                          const domain = url.replace(/^https?:\\/\\//g, '').replace(/^www\\./g, '').split('/')[0];
                          return `<a href="${url}" target="_blank" style="color: #1f77b4; text-decoration: underline; margin-right: 8px;">${domain}</a>`;
                        }
                      });
                      this.eGui.innerHTML = links.join('<br/>');
                    } else {
                      this.eGui.innerText = '—';
                      this.eGui.style.color = '#6c757d';
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
                gb = GridOptionsBuilder.from_dataframe(clean_df[display_columns])
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
                
                # Configure specific columns
                if "Office" in display_columns:
                    gb.configure_column("Office", width=90, pinned='left')
                gb.configure_column("WO #", width=100, pinned='left')
                gb.configure_column("Model", width=120)
                gb.configure_column("Media Contact", width=120)
                gb.configure_column("Publication", width=120)
                
                # Configure Original URLs column with clickable links
                gb.configure_column(
                    "🔗 Original URLs", 
                    cellRenderer=cellRenderer_original_urls,
                    width=200, 
                    wrapText=True, 
                    autoHeight=True,
                    sortable=False,
                    filter=False
                )
                
                gb.configure_column("URLs", width=60, type=["numericColumn"])
                gb.configure_column("⚠️ Rejection Reason", width=150, wrapText=True, autoHeight=True)
                gb.configure_column("📋 Details", width=250, wrapText=True, autoHeight=True)
                gb.configure_column("📅 Processed", width=120)
                
                # Build grid options
                grid_options = gb.build()
                
                # Display AgGrid table for rejected records
                st.markdown("### 📋 Rejected Records Table")
                st.markdown(f"*Showing all {len(clean_df)} rejected records*")
                selected_rejected = AgGrid(
                    clean_df[display_columns],
                    gridOptions=grid_options,
                    allow_unsafe_jscode=True,  # Required for custom cellRenderer
                    update_mode=GridUpdateMode.SELECTION_CHANGED,
                    height=700,  # Increased height to show more records without pagination
                    fit_columns_on_grid_load=True,
                    theme="alpine",
                    enable_enterprise_modules=True  # REQUIRED for Set Filters with checkboxes
                )
                
                # Export rejected records option
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📄 Export Rejected Records"):
                        csv_data = rejected_df.to_csv(index=False)
                        st.download_button(
                            label="💾 Download Rejected Records CSV",
                            data=csv_data,
                            file_name=f"rejected_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                
                with col2:
                    # Rejection reason breakdown
                    if st.button("📊 View Rejection Breakdown"):
                        if 'Rejection_Reason' in rejected_df.columns:
                            reason_counts = rejected_df['Rejection_Reason'].value_counts()
                            st.markdown("#### Rejection Reason Breakdown:")
                            for reason, count in reason_counts.items():
                                st.write(f"- **{reason}**: {count} records")
                
                with col3:
                    if st.button("🔄 Refresh Rejected Data"):
                        st.rerun()
                        
                # Summary insights
                st.markdown("---")
                st.markdown("### 💡 Processing Insights")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**🔍 What This Shows:**")
                    st.markdown("""
                    - Every loan that was processed but didn't result in an approved clip
                    - Detailed reasons for why each loan was rejected
                    - URL-level details showing what was attempted
                    - Processing timestamps for audit purposes
                    """)
                
                with col2:
                    st.markdown("**📈 Business Value:**")
                    st.markdown("""
                    - **Complete Transparency**: Account for all 60+ daily loans
                    - **Process Improvement**: Identify common failure patterns
                    - **Media Partner Insights**: See which sources aren't producing content
                    - **Quality Assurance**: Verify strict filtering is working correctly
                    """)
                
            else:
                st.info("No rejected records found. All processed loans resulted in approved clips!")
                
        except Exception as e:
            st.error(f"Error loading rejected records: {e}")
    else:
        st.info("No rejected records file found. Process loans to see transparency data.")

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
                    
                    # Rebalanced info in 3 columns for better distribution
                    info_col1, info_col2, info_col3 = st.columns(3)
                    with info_col1:
                        st.markdown(f"**👤 Contact**  \n{selected_row.get('To', 'N/A')}")
                    with info_col2:
                        st.markdown(f"**📰 Publication**  \n{selected_row.get('Affiliation', 'N/A')}")
                    with info_col3:
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

 