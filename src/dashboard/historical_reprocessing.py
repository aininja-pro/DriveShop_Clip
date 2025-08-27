"""
Historical Clips Re-Processing UI Component
Allows bulk re-processing of clips with enhanced sentiment analysis
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from typing import List, Dict, Any, Optional
import time
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode, JsCode

from src.utils.logger import setup_logger
from src.utils.database import get_database
from src.utils.sentiment_analysis import run_sentiment_analysis
from src.utils.trim_extractor import extract_trim_from_model

logger = setup_logger(__name__)

@st.fragment
def display_grid_fragment(display_df, clips, db, get_reprocessing_clips_func):
    """Display the AgGrid in an isolated fragment to prevent full page reruns"""
    # Configure AgGrid - EXACTLY like Approved Queue
    gb = GridOptionsBuilder.from_dataframe(display_df)
    
    # Enable selection for batch operations - EXACTLY like Approved Queue
    gb.configure_selection('multiple', use_checkbox=True, groupSelectsChildren=True, groupSelectsFiltered=True)
    
    # Configure sidebar with filters
    gb.configure_side_bar()
    gb.configure_default_column(
        filter="agSetColumnFilter",
        sortable=True,
        resizable=True,
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
    
    # Configure columns - checkbox IN WO # column like Approved Queue
    gb.configure_column("WO #", minWidth=100, pinned='left', checkboxSelection=True, headerCheckboxSelection=True)
    gb.configure_column("Make", minWidth=100)
    gb.configure_column("Model", minWidth=120)
    gb.configure_column("Published Date", minWidth=120)
    gb.configure_column("Sentiment Status", minWidth=150)
    gb.configure_column("id", hide=True)  # Hide but keep for processing
    
    # Build grid options
    grid_options = gb.build()
    
    # Display the grid
    st.markdown("### Select Clips to Re-Process")
    st.markdown("*Use the checkboxes to select clips. Filter using the sidebar on the right.*")
    
    grid_response = AgGrid(
        display_df,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED,  # EXACTLY like Approved Queue
        height=600,
        fit_columns_on_grid_load=True,
        columns_auto_size_mode='FIT_ALL_COLUMNS_TO_VIEW',
        theme="alpine",
        enable_enterprise_modules=True  # EXACTLY like Approved Queue - no other params
    )
    
    # Get selected rows - EXACTLY like Approved Queue
    selected_count = len(grid_response.selected_rows) if hasattr(grid_response, 'selected_rows') and grid_response.selected_rows is not None else 0
    
    # Show actions section
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.metric("Selected", f"{selected_count}/{len(display_df)}")
    
    with col2:
        # Check if we have selections
        button_disabled = selected_count == 0
        
        if st.button("🚀 Re-Process Selected", 
                     disabled=button_disabled,
                     help="Run enhanced sentiment analysis on selected clips",
                     use_container_width=True,
                     type="primary"):
            # Get selected rows data - EXACTLY like Approved Queue
            if hasattr(grid_response, 'selected_rows') and grid_response.selected_rows is not None:
                selected_data = grid_response.selected_rows
                if hasattr(selected_data, 'to_dict'):
                    selected_rows = selected_data.to_dict('records')
                else:
                    selected_rows = []
                
                selected_ids = [row['id'] for row in selected_rows if row.get('id')]
                
                if selected_ids:
                    # Process directly in the fragment
                    with st.spinner("Processing selected clips..."):
                        process_clips_queue(db, clips, selected_ids)
                    # Clear cache and refresh after processing
                    get_reprocessing_clips_func.clear()
                    st.success("✅ Processing completed! Refreshing...")
                    time.sleep(2)
                    st.rerun()


# Removed show_processing_dialog - processing now happens in the fragment


def display_historical_reprocessing_tab(db=None):
    """Display the Historical Clips Re-Processing interface
    
    Args:
        db: Optional database connection. If not provided, will create one.
    """
    
    st.markdown("Re-process historical clips with enhanced Message Pull-Through sentiment analysis")
    
    # Initialize session state - ALWAYS reset on page load to prevent background processing
    if 'reprocess_queue' not in st.session_state:
        st.session_state.reprocess_queue = []
    if 'reprocess_status' not in st.session_state:
        st.session_state.reprocess_status = 'idle'  # idle, processing, completed
    else:
        # Reset status if it was processing (prevent auto-continue on restart)
        if st.session_state.reprocess_status == 'processing':
            st.session_state.reprocess_status = 'idle'
            st.warning("⚠️ Previous processing was interrupted. Please select clips and start again.")
    
    if 'reprocess_progress' not in st.session_state:
        st.session_state.reprocess_progress = {'current': 0, 'total': 0, 'succeeded': 0, 'failed': 0}
    if 'reprocess_page' not in st.session_state:
        st.session_state.reprocess_page = 1
    
    # Use provided database connection or create one
    if db is None:
        # Only create if not provided
        @st.cache_resource
        def get_cached_db():
            return get_database()
        
        db = get_cached_db()

    # Controls: search + paging
    if 'reprocess_limit' not in st.session_state:
        st.session_state.reprocess_limit = 100
    if 'reprocess_search_wo' not in st.session_state:
        st.session_state.reprocess_search_wo = ''

    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 1, 1])
    with ctrl_col1:
        st.session_state.reprocess_search_wo = st.text_input(
            "Search by WO # (exact match)",
            value=st.session_state.reprocess_search_wo,
            placeholder="e.g., 1182796"
        )
    with ctrl_col2:
        if st.button("Load more (+100)"):
            st.session_state.reprocess_limit += 100
            get_reprocessing_clips.clear()
            st.rerun()
    with ctrl_col3:
        if st.button("Reset"):
            st.session_state.reprocess_limit = 100
            st.session_state.reprocess_search_wo = ''
            get_reprocessing_clips.clear()
            st.rerun()

    # Load clips with cache - EXACTLY like Approved Queue
    @st.cache_data(ttl=300, show_spinner=False)
    def get_reprocessing_clips(limit: int, search_wo: str):
        # Only get clips that need work; cached for snappy tab load
        return load_clips_for_reprocessing(db, True, limit=limit, search_wo=search_wo)

    clips = get_reprocessing_clips(st.session_state.reprocess_limit, st.session_state.reprocess_search_wo.strip())
    
    # Display summary
    if clips:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Clips", len(clips))
        with col2:
            missing_enhanced = len([c for c in clips if not c.get('sentiment_data_enhanced')])
            st.metric("Missing Enhanced", missing_enhanced)
        with col3:
            old_version = len([c for c in clips if c.get('sentiment_version') == 'v1'])
            st.metric("Old Version (v1)", old_version)
        with col4:
            never_analyzed = len([c for c in clips if not c.get('sentiment_completed')])
            st.metric("Never Analyzed", never_analyzed)
    
    if clips:
        # Convert to DataFrame for AgGrid
        display_df = prepare_display_dataframe_for_grid(clips)
        
        # Call the fragment to display the grid - pass the cache function
        display_grid_fragment(display_df, clips, db, get_reprocessing_clips)
    
    else:
        st.warning("No clips found matching the selected filters")


def load_clips_for_reprocessing(db, only_needs_reprocessing: bool = False, *, limit: int = 100, search_wo: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load approved clips that might need reprocessing with a reasonable limit"""
    try:
        # More selective query - only get necessary columns first
        # Note: removed 'year' and 'trim' as they don't exist in clips table
        columns = 'id, wo_number, make, model, published_date, sentiment_completed, sentiment_version, sentiment_data_enhanced, status, processed_date, media_outlet, clip_url, extracted_content'
        
        # Get recent approved clips - smaller batch to avoid timeout
        query = db.supabase.table('clips').select(columns).eq('status', 'approved')

        # Optional server-side search by WO
        if search_wo:
            query = query.eq('wo_number', search_wo)
        
        # Order by processed_date and limit to avoid timeout
        # Use a higher cap (200) to allow room for post-filtering, but slice to `limit` later
        result = query.order('processed_date', desc=True).limit(max(200, limit)).execute()
        
        if only_needs_reprocessing and result.data:
            # Filter in Python instead of complex SQL
            filtered_clips = []
            for clip in result.data:
                # Check if needs reprocessing
                needs_work = False
                
                # Check various conditions
                if not clip.get('sentiment_completed'):
                    needs_work = True  # Never analyzed
                elif not clip.get('sentiment_data_enhanced'):
                    needs_work = True  # Missing enhanced data
                elif clip.get('sentiment_version') == 'v1':
                    needs_work = True  # Old version
                
                if needs_work:
                    filtered_clips.append(clip)
            
            # If we need more data for a full clip, fetch it separately
            # This is more efficient than fetching everything upfront
            return filtered_clips[:limit]
        
        return result.data[:limit] if result.data else []
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to load clips: {error_msg}")
        
        # Check for specific timeout error
        if '57014' in error_msg or 'timeout' in error_msg.lower():
            st.error("⏱️ Database query timed out. Loading a smaller dataset...")
            # Try with even smaller limit
            try:
                columns = 'id, wo_number, make, model, published_date, sentiment_completed, sentiment_version, status'
                result = db.supabase.table('clips').select(columns).eq('status', 'approved').limit(min(50, limit)).execute()
                return result.data if result.data else []
            except:
                st.error("Unable to load clips. Please try again later.")
                return []
        else:
            st.error(f"Failed to load clips: {error_msg}")
            return []


def prepare_display_dataframe_for_grid(clips: List[Dict[str, Any]]) -> pd.DataFrame:
    """Prepare clips data for AgGrid display"""
    display_data = []
    
    for clip in clips:
        sentiment_status = get_sentiment_status(clip)
        
        display_data.append({
            'id': clip.get('id'),  # Keep for processing
            'WO #': clip.get('wo_number', ''),
            'Make': clip.get('make', ''),
            'Model': clip.get('model', ''),
            'Published Date': clip.get('published_date', ''),
            'Sentiment Status': sentiment_status,
            'Sentiment Version': clip.get('sentiment_version', 'None'),
            'Has Enhanced': '✅' if clip.get('sentiment_data_enhanced') else '❌',
            'Analyzed': '✅' if clip.get('sentiment_completed') else '❌'
        })
    
    return pd.DataFrame(display_data)


def get_sentiment_status(clip: Dict[str, Any]) -> str:
    """Determine the sentiment analysis status of a clip"""
    if not clip.get('sentiment_completed'):
        return "Never Analyzed"
    elif not clip.get('sentiment_data_enhanced'):
        return "Missing Enhanced"
    elif clip.get('sentiment_version') == 'v1':
        return "Old Version (v1)"
    elif clip.get('sentiment_version') == 'v2':
        return "Current (v2)"
    else:
        return "Unknown"


def get_status_color(status: str) -> str:
    """Get color for status display"""
    colors = {
        "Never Analyzed": "#ff4b4b",
        "Missing Enhanced": "#ffa500",
        "Old Version (v1)": "#ffaa00",
        "Current (v2)": "#00cc88",
        "Unknown": "#888888"
    }
    return colors.get(status, "#888888")


def process_clips_queue(db, all_clips: List[Dict[str, Any]], queue_ids: List[str]):
    """Process clips using EXACT same workflow as approval process"""
    
    if not queue_ids:
        logger.warning("No clips selected for processing")
        return
    
    # Get full clip data for processing
    clips_to_process = []
    for clip_id in queue_ids:
        try:
            # Always fetch full clip data to ensure we have all fields
            result = db.supabase.table('clips').select('*').eq('id', clip_id).single().execute()
            if result.data:
                clips_to_process.append(result.data)
        except Exception as e:
            logger.error(f"Failed to fetch clip {clip_id}: {e}")
    
    if not clips_to_process:
        st.error("No clips could be loaded for processing")
        return
    
    # Progress display
    with st.container():
        st.markdown("### 🚀 Processing with EXACT Approval Workflow")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Log area
        with st.expander("Processing Log", expanded=True):
            log_container = st.empty()
            processing_log = []
        
        def add_log(message):
            timestamp = datetime.now().strftime("%H:%M:%S")
            processing_log.append(f"[{timestamp}] {message}")
            log_container.text_area("Live Processing Logs", "\n".join(processing_log), height=300)
        
        add_log(f"🎯 Processing {len(clips_to_process)} approved clips")
        
        # STEP 1: Extract trim for clips that don't have it (EXACT same as approval)
        add_log("📋 Step 1: Extracting trim information...")
        status_text.info("📋 Extracting trim information...")
        
        for clip in clips_to_process:
            if not clip.get('trim'):
                make = clip.get('make', '')
                model = clip.get('model', '')
                if model:
                    base_model, extracted_trim = extract_trim_from_model(model, make)
                    if extracted_trim:
                        try:
                            # Update database with trim
                            db.supabase.table('clips').update({
                                'trim': extracted_trim,
                                'model': base_model
                            }).eq('wo_number', clip['wo_number']).execute()
                            
                            # Update clip object
                            clip['trim'] = extracted_trim
                            clip['model'] = base_model
                            add_log(f"✅ Extracted trim '{extracted_trim}' for WO# {clip['wo_number']}")
                        except Exception as e:
                            add_log(f"❌ Failed to update trim for WO# {clip['wo_number']}: {e}")
        
        # STEP 2: Run sentiment analysis (EXACT same as approval)
        add_log("🧠 Step 2: Running enhanced sentiment analysis...")
        status_text.info("🧠 Running enhanced sentiment analysis...")
        
        # Progress callback
        def progress_callback(progress, message):
            progress_bar.progress(progress)
            status_text.info(f"🧠 {message}")
            add_log(f"Progress: {message}")
        
        # Check OpenAI API key
        if not os.environ.get('OPENAI_API_KEY'):
            add_log("❌ OpenAI API key not found")
            st.error("❌ OpenAI API key not found")
            return
        
        add_log("🤖 Calling run_sentiment_analysis() - EXACT same function as approval")
        
        # EXACT same call as approval workflow
        try:
            results = run_sentiment_analysis(clips_to_process, progress_callback)
        except Exception as e:
            add_log(f"❌ Sentiment analysis error: {str(e)}")
            st.error(f"❌ Sentiment analysis error: {str(e)}")
            return
        
        # STEP 3: Process results (EXACT same as approval)
        add_log("💾 Step 3: Saving results to database...")
        status_text.info("💾 Saving results to database...")
        
        success_count = 0
        if results and 'results' in results:
            for clip, result in zip(clips_to_process, results['results']):
                clip_wo = clip.get('wo_number', 'N/A')
                
                if result.get('sentiment_completed'):
                    # EXACT same database update as approval
                    success = db.update_clip_sentiment(clip['id'], result)
                    if success:
                        # EXACT same workflow stage update as approval
                        db.supabase.table('clips').update({
                            'workflow_stage': 'sentiment_analyzed'
                        }).eq('id', clip['id']).execute()
                        
                        success_count += 1
                        add_log(f"✅ Successfully processed WO# {clip_wo}")
                    else:
                        add_log(f"❌ Failed to save results for WO# {clip_wo}")
                else:
                    # EXACT same failure handling as approval
                    db.supabase.table('clips').update({
                        'workflow_stage': 'sentiment_analyzed',
                        'sentiment_completed': False
                    }).eq('id', clip['id']).execute()
                    
                    error_msg = result.get('error', 'Unknown error')
                    add_log(f"❌ Analysis failed for WO# {clip_wo}: {error_msg}")
        
        # Final results
        progress_bar.progress(1.0)
        add_log(f"🎉 Processing complete: {success_count}/{len(clips_to_process)} successful")
        
        if success_count > 0:
            status_text.success(f"✅ Successfully processed {success_count}/{len(clips_to_process)} clips!")
        else:
            status_text.error("❌ No clips were processed successfully")
    
    # Update final status
    if st.session_state.reprocess_status == 'stopped':
        st.session_state.reprocess_status = 'stopped'
        status_text.warning("⏹️ Processing stopped by user")
        processing_log.append(f"Processing stopped. Total processed: {st.session_state.reprocess_progress['current']}")
    else:
        st.session_state.reprocess_status = 'completed'
        status_text.success("✅ Processing completed!")
        processing_log.append(f"Processing completed. Total processed: {st.session_state.reprocess_progress['current']}")
    
    log_container.text('\n'.join(processing_log[-10:]))
    
    # Show final summary
    st.markdown("---")
    st.markdown("### 📊 Final Results")
    final_col1, final_col2, final_col3, final_col4 = st.columns(4)
    with final_col1:
        st.metric("Total Processed", st.session_state.reprocess_progress['current'])
    with final_col2:
        st.metric("✅ Succeeded", st.session_state.reprocess_progress['succeeded'])
    with final_col3:
        st.metric("❌ Failed", st.session_state.reprocess_progress['failed'])
    with final_col4:
        if st.session_state.reprocess_progress['current'] > 0:
            final_rate = (st.session_state.reprocess_progress['succeeded'] / st.session_state.reprocess_progress['current']) * 100
            st.metric("Success Rate", f"{final_rate:.1f}%")
    
    # Clear the queue
    st.session_state.reprocess_queue = []
    
    # Cache is cleared in the fragment after processing
    
    # Add a button to refresh the page
    if st.button("🔄 Refresh Page", type="primary"):
        st.rerun()