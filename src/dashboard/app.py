import streamlit as st
import pandas as pd
import os
import sys
from pathlib import Path
from datetime import datetime
import time

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
    from src.ingest.ingest import run_ingest
except ImportError:
    # Define a stub for when the module is not yet implemented
    def run_ingest(file_path):
        st.error("Ingest module not implemented yet")
        return False

# Load environment variables
def load_env():
    """Load environment variables from .env file"""
    from dotenv import load_dotenv
    load_dotenv()
    return os.environ.get("STREAMLIT_PASSWORD", "password")

# Page configuration
st.set_page_config(
    page_title="DriveShop Clip Tracking",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# DEVELOPMENT MODE: Skip password check
# Main application
st.title("DriveShop Clip Tracking Dashboard")

# Debug section
with st.expander("Debug Information", expanded=False):
    st.write("App is running")
    st.write(f"Project root: {project_root}")
    
    results_file = os.path.join(project_root, "data", "loan_results.csv")
    if os.path.exists(results_file):
        st.write(f"Results file exists at: {results_file}")
        
        try:
            df = pd.read_csv(results_file)
            st.write(f"Results file contains {len(df)} rows")
            st.write("Columns in results file:")
            st.write(df.columns.tolist())
            
            # Show first row as an example
            if not df.empty:
                st.write("First row example:")
                st.write(df.iloc[0].to_dict())
        except Exception as e:
            st.write(f"Error loading results file: {e}")
    else:
        st.write(f"Results file does not exist at: {results_file}")

# Sidebar for uploading files and running ingestion
with st.sidebar:
    st.header("Upload and Process")
    uploaded_file = st.file_uploader("Upload Loans without Clips CSV", type=['csv', 'xlsx'])
    
    if uploaded_file is not None:
        # Save the uploaded file temporarily
        temp_file_path = os.path.join(project_root, "data", "fixtures", "temp_upload.csv")
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Run ingestion button
        if st.button("Process Uploaded File"):
            with st.spinner("Processing loans..."):
                success = run_ingest(temp_file_path)
                if success:
                    st.success("Processing complete!")
                else:
                    st.error("Processing failed. Check logs for details.")
    
    # Alternatively, run the existing file
    st.divider()
    if st.button("Process Existing Data"):
        with st.spinner("Processing existing loan data..."):
            default_file = os.path.join(project_root, "data", "fixtures", "Loans_without_Clips.csv")
            success = run_ingest(default_file)
            if success:
                st.success("Processing complete!")
            else:
                st.error("Processing failed. Check logs for details.")

# Main content area with tabs
tab1, tab2 = st.tabs(["Pending Clips", "Approved Clips"])

with tab1:
    st.header("Pending Clips for Review")
    
    # Try to load results file if it exists
    results_file = os.path.join(project_root, "data", "loan_results.csv")
    if os.path.exists(results_file):
        try:
            df = pd.read_csv(results_file)
            
            if not df.empty:
                # Display the data in a table - use columns that exist in the file
                display_columns = ["WO #", "Model", "To", "Affiliation"]
                
                # Add optional columns if they exist
                optional_columns = ["Relevance Score", "Clip URL"]
                for col in optional_columns:
                    if col in df.columns:
                        display_columns.append(col)
                
                # Filter to columns that actually exist in the DataFrame
                actual_display_columns = [col for col in display_columns if col in df.columns]
                
                if actual_display_columns:
                    st.dataframe(
                        df[actual_display_columns],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.error("Could not find any expected columns in the results file. Please check the data format.")
                    st.write("Available columns:", df.columns.tolist())
                
                # When a row is selected, show details
                if "WO #" in df.columns:
                    selected_wo = st.selectbox("Select Work Order to Review", df["WO #"].unique())
                    
                    if selected_wo:
                        selected_row = df[df["WO #"] == selected_wo].iloc[0]
                        
                        col1, col2 = st.columns([1, 1])
                        
                        with col1:
                            st.subheader(f"{selected_row.get('Model', 'Unknown Model')}")
                            
                            # Display various fields if they exist
                            for field, label in [
                                ('To', 'Media Contact'),
                                ('Affiliation', 'Publication'),
                                ('Clip URL', 'Clip URL'),
                                ('Links', 'Original Link'),
                            ]:
                                if field in selected_row:
                                    st.write(f"**{label}:** {selected_row[field]}")
                            
                            # Decision buttons
                            approval_col1, approval_col2 = st.columns(2)
                            with approval_col1:
                                if st.button("✅ Approve Clip", key=f"approve_{selected_wo}"):
                                    # Logic to move to approved list
                                    st.success(f"Clip for WO #{selected_wo} approved!")
                                    
                                    # Try to load or create approved clips file
                                    approved_file = os.path.join(project_root, "data", "approved_clips.csv")
                                    
                                    if os.path.exists(approved_file):
                                        approved_df = pd.read_csv(approved_file)
                                        # Check if this WO is already in the approved list
                                        if "WO #" in approved_df.columns and selected_wo not in approved_df["WO #"].values:
                                            approved_df = pd.concat([approved_df, pd.DataFrame([selected_row])], ignore_index=True)
                                    else:
                                        approved_df = pd.DataFrame([selected_row])
                                    
                                    # Save the updated approved clips
                                    approved_df.to_csv(approved_file, index=False)
                                    
                                    # Rerun the app to update the UI
                                    st.rerun()
                            
                            with approval_col2:
                                if st.button("❌ Flag for Review", key=f"flag_{selected_wo}"):
                                    st.warning(f"Clip for WO #{selected_wo} flagged for review")
                        
                        with col2:
                            st.subheader("AI Analysis")
                            
                            # Display various analysis fields if they exist
                            for field, label, suffix in [
                                ('Relevance Score', 'Relevance Score', '/10'),
                                ('Sentiment', 'Sentiment', ''),
                            ]:
                                if field in selected_row:
                                    st.metric(label, f"{selected_row.get(field, 'N/A')}{suffix}")
                            
                            # Display summary if it exists
                            if 'Summary' in selected_row:
                                st.subheader("Summary")
                                st.write(selected_row['Summary'])
                            else:
                                st.info("No AI summary available yet")
                            
                            # Display brand alignment if it exists
                            if 'Brand Alignment' in selected_row:
                                st.subheader("Brand Alignment")
                                st.write(selected_row['Brand Alignment'])
            else:
                st.info("No pending clips to review. Upload a CSV file or process existing data.")
        
        except Exception as e:
            st.error(f"Error loading results: {str(e)}")
            st.info("Try uploading a CSV file or processing existing data.")
    else:
        st.info("No results file found. Upload a CSV file or process existing data to begin.")

with tab2:
    st.header("Approved Clips")
    
    # Try to load approved clips file if it exists
    approved_file = os.path.join(project_root, "data", "approved_clips.csv")
    if os.path.exists(approved_file):
        try:
            approved_df = pd.read_csv(approved_file)
            
            if not approved_df.empty:
                # Display the approved clips - use columns that exist in the file
                display_columns = ["WO #", "Model", "To", "Affiliation"]
                
                # Add optional columns if they exist
                optional_columns = ["Clip URL", "Links"]
                for col in optional_columns:
                    if col in approved_df.columns:
                        display_columns.append(col)
                
                # Filter to columns that actually exist in the DataFrame
                actual_display_columns = [col for col in display_columns if col in approved_df.columns]
                
                if actual_display_columns:
                    st.dataframe(
                        approved_df[actual_display_columns],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.error("Could not find any expected columns in the approved file. Please check the data format.")
                    st.write("Available columns:", approved_df.columns.tolist())
                
                # Export button
                if st.download_button(
                    "Export Approved Clips",
                    data=approved_df.to_csv(index=False),
                    file_name="approved_clips.csv",
                    mime="text/csv"
                ):
                    st.success("File downloaded successfully")
            else:
                st.info("No approved clips yet. Review and approve clips from the Pending Clips tab.")
        
        except Exception as e:
            st.error(f"Error loading approved clips: {str(e)}")
    else:
        st.info("No approved clips file found. Review and approve clips from the Pending Clips tab.") 