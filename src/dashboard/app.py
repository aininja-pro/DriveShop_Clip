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

# Custom CSS for better styling
st.markdown("""
<style>
    /* Modern, tighter typography */
    .main > div {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
        padding-top: 1.5rem !important;
    }
    
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }
    
    /* Fix main title visibility */
    h1 {
        font-size: 1.8rem !important;
        font-weight: 600 !important;
        line-height: 1.3 !important;
        margin-bottom: 1rem !important;
        margin-top: 0.5rem !important;
        padding-top: 0.5rem !important;
        color: #1a1a1a !important;
        display: block !important;
        visibility: visible !important;
        position: relative !important;
        z-index: 999 !important;
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
    
    /* Compact metrics */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 0.5rem;
        border-radius: 0.25rem;
        margin: 0.2rem 0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    div[data-testid="metric-container"] > div {
        font-size: 0.55rem;
        line-height: 1.3;
    }
    
    div[data-testid="metric-container"] > div:first-child {
        font-size: 0.5rem;
        font-weight: 600;
        color: #6c757d;
        margin-bottom: 0.1rem;
    }
    
    /* Add breathing room after header */
    .first-row {
        padding-top: 18px !important;
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
</style>
""", unsafe_allow_html=True)

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
                success = run_ingest_concurrent(temp_file_path)
                if success:
                    st.success("Processing complete!")
                else:
                    st.error("Processing failed. Check logs for details.")
    
    # Alternatively, run the existing file
    st.divider()
    if st.button("Process Existing Data"):
        with st.spinner("Processing existing loan data..."):
            default_file = os.path.join(project_root, "data", "fixtures", "Loans_without_Clips.csv")
            success = run_ingest_concurrent(default_file)
            if success:
                st.success("Processing complete!")
            else:
                st.error("Processing failed. Check logs for details.")

# Main content area with tabs for different workflows
st.markdown("---")

# Create tabs for different user workflows
bulk_tab, analysis_tab = st.tabs(["📋 Bulk Review", "🔍 Detailed Analysis"])

# ========== BULK REVIEW TAB (New Worker Interface) ==========
with bulk_tab:
    st.markdown('<p style="font-size: 1rem; font-weight: 600; color: #2c3e50; margin-bottom: 0.8rem;">📋 Quick Clip Review</p>', unsafe_allow_html=True)
    
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
                    avg_score = df['Relevance Score'].mean() if 'Relevance Score' in df.columns else 0
                    st.metric("Avg Score", f"{avg_score:.1f}/10")
                with col3:
                    high_quality = len(df[df['Relevance Score'] >= 8]) if 'Relevance Score' in df.columns else 0
                    st.metric("High Quality", high_quality)
                with col4:
                    # Check approved count
                    approved_file = os.path.join(project_root, "data", "approved_clips.csv")
                    approved_count = 0
                    if os.path.exists(approved_file):
                        approved_df = pd.read_csv(approved_file)
                        approved_count = len(approved_df)
                    st.metric("Approved", approved_count)
                
                st.markdown("---")
                
                # Compact table with headers
                st.markdown('<p style="font-size: 0.85rem; font-weight: 600; color: #5a6c7d; margin-bottom: 0.5rem;">📊 All Clips</p>', unsafe_allow_html=True)
                
                # Use native Streamlit dataframe with LinkColumn - MUCH more reliable!
                display_df = df.copy()
                
                # Format columns for better display
                display_df['Contact'] = display_df['To'].apply(lambda x: x[:20] + "..." if len(str(x)) > 20 else str(x))
                display_df['Publication'] = display_df['Affiliation'].apply(lambda x: x[:20] + "..." if len(str(x)) > 20 else str(x))
                display_df['Score'] = display_df['Relevance Score'].apply(lambda x: f"{x}/10")
                display_df['Sentiment'] = display_df['Overall Sentiment'].apply(
                    lambda x: "😊 Pos" if x == "positive" else "😞 Neg" if x == "negative" else "😐 Neu"
                )
                
                # Select and reorder columns for display
                display_columns = ['WO #', 'Model', 'Contact', 'Publication', 'Score', 'Sentiment', 'Clip URL']
                display_df = display_df[display_columns]
                
                # Add interactive approve/reject columns
                display_df['Approve'] = False
                display_df['Reject'] = False
                
                # Use st.data_editor with column_config for clickable links AND interactive checkboxes
                edited_df = st.data_editor(
                    display_df,
                    column_config={
                        "WO #": st.column_config.TextColumn("WO #", width="small", disabled=True),
                        "Model": st.column_config.TextColumn("Model", width="medium", disabled=True),
                        "Contact": st.column_config.TextColumn("Contact", width="medium", disabled=True),
                        "Publication": st.column_config.TextColumn("Publication", width="medium", disabled=True),
                        "Score": st.column_config.TextColumn("Score", width="small", disabled=True),
                        "Sentiment": st.column_config.TextColumn("Sentiment", width="small", disabled=True),
                        "Clip URL": st.column_config.LinkColumn(
                            "Link",
                            width="small",
                            disabled=True
                        ),
                        "Approve": st.column_config.CheckboxColumn(
                            "✅ Approve",
                            width="small",
                            default=False
                        ),
                        "Reject": st.column_config.CheckboxColumn(
                            "❌ Reject", 
                            width="small",
                            default=False
                        ),
                    },
                    use_container_width=True,
                    height=500,
                    hide_index=True,
                    key="clip_editor"
                )
                
                # Process approve/reject actions
                approved_wos = edited_df[edited_df['Approve'] == True]['WO #'].tolist()
                rejected_wos = edited_df[edited_df['Reject'] == True]['WO #'].tolist()
                
                if approved_wos:
                    st.success(f"✅ {len(approved_wos)} clips marked for approval: {', '.join(map(str, approved_wos))}")
                    
                    # Auto-save approved clips
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
                
                if rejected_wos:
                    st.warning(f"❌ {len(rejected_wos)} clips marked for rejection: {', '.join(map(str, rejected_wos))}")
                
                st.markdown("---")
                
                # Bulk actions
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
                            st.success(f"✅ Approved {len(high_quality_df)} clips!")
                            st.rerun()
                
                with col2:
                    if st.button("📤 Export Approved"):
                        approved_file = os.path.join(project_root, "data", "approved_clips.csv")
                        if os.path.exists(approved_file):
                            approved_df = pd.read_csv(approved_file)
                            csv_data = approved_df.to_csv(index=False)
                            st.download_button(
                                "📥 Download CSV",
                                data=csv_data,
                                file_name=f"approved_clips_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv"
                            )
                        else:
                            st.warning("No approved clips to export")
                
                with col3:
                    if st.button("🔄 Refresh"):
                        st.rerun()
            else:
                st.info("No clips to review. Process loans first.")
        except Exception as e:
            st.error(f"Error loading clips: {e}")
    else:
        st.info("No results file found. Upload and process loans to begin.")

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