"""
Historical Clips Re-Processing UI Component
Allows bulk re-processing of clips with enhanced sentiment analysis
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
from typing import List, Dict, Any, Optional
import time
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode, JsCode

from src.utils.logger import setup_logger
from src.utils.database import get_database
from src.analysis.gpt_analysis_enhanced import analyze_clip_enhanced
from src.utils.rate_limiter import rate_limiter
from src.utils.youtube_handler import extract_video_id, get_transcript

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
    """Process the selected clips with enhanced sentiment analysis"""
    
    # Safety check - don't process if no clips selected
    if not queue_ids:
        logger.warning("process_clips_queue called with no queue_ids")
        return
    
    # Update status
    st.session_state.reprocess_status = 'processing'
    st.session_state.reprocess_progress = {
        'current': 0,
        'total': len(queue_ids),
        'succeeded': 0,
        'failed': 0,
        'current_clip': ''
    }
    
    # Get clips to process - fetch full data if needed
    clips_to_process = []
    for clip_id in queue_ids:
        # First check if we have the clip in our list
        clip = next((c for c in all_clips if c['id'] == clip_id), None)
        
        if clip:
            # Check if we have extracted_content, if not fetch full clip
            if not clip.get('extracted_content'):
                try:
                    # Fetch full clip data
                    full_clip_result = db.supabase.table('clips').select('*').eq('id', clip_id).single().execute()
                    if full_clip_result.data:
                        clips_to_process.append(full_clip_result.data)
                    else:
                        clips_to_process.append(clip)  # Use partial data
                except Exception as e:
                    logger.error(f"Failed to fetch full clip data for {clip_id}: {e}")
                    clips_to_process.append(clip)  # Use partial data
            else:
                clips_to_process.append(clip)
    
    # Create a progress dialog
    with st.container():
        progress_container = st.empty()
        
        with progress_container.container():
            st.markdown("### 🔄 Processing Clips")
            
            # Progress bar
            progress_bar = st.progress(0)
            
            # Status text
            status_text = st.empty()
            status_text.markdown("Initializing...")
            
            # Metrics row
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                current_metric = st.empty()
            with col2:
                success_metric = st.empty()
            with col3:
                failed_metric = st.empty()
            with col4:
                rate_metric = st.empty()
            
            # Current clip details
            current_clip_container = st.empty()
            
            # Log area
            with st.expander("Processing Log", expanded=False):
                log_container = st.empty()
                processing_log = []
    
    for idx, clip in enumerate(clips_to_process):
        # Check if processing should stop
        if st.session_state.reprocess_status == 'stopped':
            status_text.warning("⏹️ Processing stopped by user")
            break
        
        # Update progress
        st.session_state.reprocess_progress['current'] = idx + 1
        st.session_state.reprocess_progress['current_clip'] = clip['wo_number']
        
        # Update UI elements
        progress_value = (idx + 1) / len(clips_to_process)
        progress_bar.progress(progress_value)
        
        status_text.markdown(f"**Processing clip {idx + 1} of {len(clips_to_process)}**")
        
        # Update metrics
        current_metric.metric("Progress", f"{idx + 1}/{len(clips_to_process)}")
        success_metric.metric("✅ Succeeded", st.session_state.reprocess_progress['succeeded'])
        failed_metric.metric("❌ Failed", st.session_state.reprocess_progress['failed'])
        
        if st.session_state.reprocess_progress['current'] > 0:
            success_rate = (st.session_state.reprocess_progress['succeeded'] / st.session_state.reprocess_progress['current']) * 100
            rate_metric.metric("Success Rate", f"{success_rate:.1f}%")
        
        # Show current clip details
        current_clip_container.info(
            f"**Current Clip:** WO# {clip['wo_number']} - {clip.get('make', '')} {clip.get('model', '')} "
            f"({clip.get('year', 'N/A')})"
        )
        
        try:
            # Apply rate limiting for OpenAI API
            rate_limiter.wait_if_needed('openai.com')
            
            # Get content for analysis
            content = clip.get('extracted_content', '')
            
            # Check if this is a YouTube video with insufficient content
            clip_url = clip.get('clip_url', '')
            if 'youtube.com' in clip_url or 'youtu.be' in clip_url:
                # Check if content is too short OR looks like metadata
                is_metadata = (
                    'Video Title:' in content and 'Channel:' in content and 'Video Description:' in content
                ) or (
                    'video_title' in content.lower() or 'channel_name' in content.lower()
                )
                
                # If content is too short (likely just metadata), re-extract
                if not content or len(content) < 1000 or is_metadata:
                    status_text.markdown(f"**📹 Extracting YouTube transcript for WO# {clip['wo_number']}...**")
                    processing_log.append(f"YouTube clip has insufficient content ({len(content or '')} chars), re-extracting...")
                    log_container.text('\n'.join(processing_log[-10:]))  # Show last 10 log entries
                    
                    logger.info(f"YouTube clip WO# {clip['wo_number']} has insufficient content ({len(content or '')} chars), re-extracting...")
                    
                    video_id = extract_video_id(clip_url)
                    if video_id:
                        # Re-extract with Whisper fallback
                        status_text.markdown(f"**🎙️ Getting transcript (with Whisper fallback if needed)...**")
                        new_content = get_transcript(video_id, video_url=clip_url, use_whisper_fallback=True)
                        
                        if new_content and len(new_content) > len(content or ''):
                            logger.info(f"✅ Re-extracted YouTube content: {len(new_content)} chars (was {len(content or '')} chars)")
                            processing_log.append(f"✅ Extracted {len(new_content)} chars of content")
                            log_container.text('\n'.join(processing_log[-10:]))
                            content = new_content
                            
                            # Update the database with new content
                            db.supabase.table('clips').update({
                                'extracted_content': content
                            }).eq('id', clip['id']).execute()
                        else:
                            logger.warning(f"Failed to get better content for YouTube video {video_id}")
                            processing_log.append(f"⚠️ Failed to extract better content")
                            log_container.text('\n'.join(processing_log[-10:]))
            
            if not content:
                logger.warning(f"No content found for WO# {clip['wo_number']}")
                st.session_state.reprocess_progress['failed'] += 1
                continue
            
            # Run enhanced sentiment analysis
            status_text.markdown(f"**🤖 Analyzing sentiment with AI...**")
            processing_log.append(f"Running enhanced sentiment analysis...")
            log_container.text('\n'.join(processing_log[-10:]))
            
            logger.info(f"Running enhanced sentiment analysis for WO# {clip['wo_number']}")
            
            sentiment_result = analyze_clip_enhanced(
                content=content,
                make=clip.get('make', ''),
                model=clip.get('model', ''),
                trim=clip.get('trim'),
                url=clip.get('clip_url')
            )
            
            if sentiment_result:
                # Update the clip with enhanced sentiment
                status_text.markdown(f"**💾 Saving results to database...**")
                success = db.update_clip_sentiment(clip['id'], sentiment_result)
                
                if success:
                    st.session_state.reprocess_progress['succeeded'] += 1
                    processing_log.append(f"✅ Successfully analyzed WO# {clip['wo_number']}")
                    log_container.text('\n'.join(processing_log[-10:]))
                    logger.info(f"✅ Successfully updated sentiment for WO# {clip['wo_number']}")
                else:
                    st.session_state.reprocess_progress['failed'] += 1
                    processing_log.append(f"❌ Failed to save results for WO# {clip['wo_number']}")
                    log_container.text('\n'.join(processing_log[-10:]))
                    logger.error(f"Failed to update database for WO# {clip['wo_number']}")
            else:
                st.session_state.reprocess_progress['failed'] += 1
                processing_log.append(f"❌ No sentiment result for WO# {clip['wo_number']}")
                log_container.text('\n'.join(processing_log[-10:]))
                logger.error(f"No sentiment result for WO# {clip['wo_number']}")
        
        except Exception as e:
            st.session_state.reprocess_progress['failed'] += 1
            processing_log.append(f"❌ Error: {str(e)}")
            log_container.text('\n'.join(processing_log[-10:]))
            logger.error(f"Error processing WO# {clip['wo_number']}: {e}")
        
        # Small delay to respect API limits
        time.sleep(0.5)
    
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