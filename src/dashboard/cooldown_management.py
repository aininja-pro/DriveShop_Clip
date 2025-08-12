"""
Cooldown Management Tab for Streamlit Dashboard
Allows users to manage and reset cooldowns for clips during testing
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from src.utils.database import get_database
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def display_cooldown_management_tab():
    """Display the cooldown management interface"""
    
    st.header("🔧 Cooldown Management")
    
    # Warning message
    st.warning("""
    ⚠️ **Testing Tool**: This tab allows you to manage cooldowns for clips that failed processing.
    Use with caution as it bypasses the normal retry intervals.
    """)
    
    db = get_database()
    
    # Create two columns for stats
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Cooldown Statistics")
        
        try:
            # Get WOs in cooldown
            result = db.supabase.table('wo_tracking')\
                .select('*')\
                .gt('retry_after_date', datetime.now().isoformat())\
                .execute()
            
            wo_in_cooldown = len(result.data) if result.data else 0
            
            # Get failed clips
            result = db.supabase.table('clips')\
                .select('wo_number, status')\
                .in_('status', ['no_content_found', 'processing_failed'])\
                .execute()
            
            failed_clips = len(result.data) if result.data else 0
            
            st.metric("WOs in Cooldown", wo_in_cooldown)
            st.metric("Failed Clips", failed_clips)
            
        except Exception as e:
            st.error(f"Error fetching statistics: {e}")
    
    with col2:
        st.subheader("⚡ Quick Actions")
        
        if st.button("🔄 Reset ALL Cooldowns", type="primary", use_container_width=True):
            if st.checkbox("I understand this will reset all cooldowns"):
                reset_all_cooldowns(db)
        
        if st.button("⏰ Make All Ready to Retry", use_container_width=True):
            set_cooldowns_to_past(db)
        
        if st.button("🔍 Refresh View", use_container_width=True):
            st.rerun()
    
    st.divider()
    
    # Detailed view of clips in cooldown
    st.subheader("📋 Clips in Cooldown")
    
    try:
        # Get detailed cooldown information
        result = db.supabase.table('wo_tracking')\
            .select('*')\
            .gt('retry_after_date', datetime.now().isoformat())\
            .order('retry_after_date')\
            .execute()
        
        if result.data:
            cooldown_df = pd.DataFrame(result.data)
            
            # Calculate time remaining
            cooldown_df['Time Remaining'] = cooldown_df['retry_after_date'].apply(
                lambda x: calculate_time_remaining(x) if x else 'N/A'
            )
            
            # Format dates for display
            cooldown_df['Retry After'] = pd.to_datetime(cooldown_df['retry_after_date']).dt.strftime('%Y-%m-%d %H:%M')
            cooldown_df['Last Attempt'] = pd.to_datetime(cooldown_df['last_attempt_date']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Select columns to display
            display_cols = ['wo_number', 'status', 'attempt_count', 'Last Attempt', 'Retry After', 'Time Remaining']
            display_df = cooldown_df[display_cols].rename(columns={
                'wo_number': 'WO #',
                'status': 'Status',
                'attempt_count': 'Attempts'
            })
            
            # Add selection checkboxes
            selected_wos = st.multiselect(
                "Select WOs to reset:",
                options=display_df['WO #'].tolist(),
                key="selected_wos_for_reset"
            )
            
            if selected_wos:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"Reset {len(selected_wos)} Selected WOs", type="primary"):
                        reset_specific_cooldowns(db, selected_wos)
                with col2:
                    st.info(f"{len(selected_wos)} WOs selected")
            
            # Display the dataframe
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "WO #": st.column_config.TextColumn("WO #", width="small"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "Attempts": st.column_config.NumberColumn("Attempts", width="small"),
                    "Time Remaining": st.column_config.TextColumn("Time Remaining", width="medium"),
                }
            )
        else:
            st.success("✅ No WOs currently in cooldown!")
            
    except Exception as e:
        st.error(f"Error loading cooldown data: {e}")
    
    st.divider()
    
    # Failed clips section
    st.subheader("❌ Failed Clips")
    
    try:
        result = db.supabase.table('clips')\
            .select('wo_number, clip_url, status, attempt_count, last_attempt_date')\
            .in_('status', ['no_content_found', 'processing_failed'])\
            .order('last_attempt_date', desc=True)\
            .limit(50)\
            .execute()
        
        if result.data:
            failed_df = pd.DataFrame(result.data)
            
            # Format dates
            failed_df['Last Attempt'] = pd.to_datetime(failed_df['last_attempt_date']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Select columns to display
            display_cols = ['wo_number', 'clip_url', 'status', 'attempt_count', 'Last Attempt']
            display_df = failed_df[display_cols].rename(columns={
                'wo_number': 'WO #',
                'clip_url': 'URL',
                'status': 'Status',
                'attempt_count': 'Attempts'
            })
            
            # Add option to reset these clips
            if st.button("🔄 Reset All Failed Clips to Pending", type="secondary"):
                reset_failed_clips(db)
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "URL": st.column_config.LinkColumn("URL", width="large"),
                    "Status": st.column_config.TextColumn("Status", width="medium"),
                }
            )
            
            st.caption(f"Showing up to 50 most recent failed clips")
        else:
            st.success("✅ No failed clips!")
            
    except Exception as e:
        st.error(f"Error loading failed clips: {e}")

def calculate_time_remaining(retry_after_str):
    """Calculate human-readable time remaining"""
    try:
        retry_after = datetime.fromisoformat(retry_after_str.replace('Z', '+00:00'))
        now = datetime.now(retry_after.tzinfo)
        
        if now >= retry_after:
            return "Ready"
        
        diff = retry_after - now
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
            
    except Exception:
        return "Unknown"

def reset_all_cooldowns(db):
    """Reset all cooldowns in the database"""
    try:
        with st.spinner("Resetting all cooldowns..."):
            # Reset wo_tracking
            result = db.supabase.table('wo_tracking').update({
                'retry_after_date': None,
                'attempt_count': 0
            }).neq('status', 'found').execute()
            
            wo_count = len(result.data) if result.data else 0
            
            # Reset failed clips
            result = db.supabase.table('clips').update({
                'status': 'pending_review',
                'attempt_count': 0
            }).in_('status', ['no_content_found', 'processing_failed']).execute()
            
            clip_count = len(result.data) if result.data else 0
            
            st.success(f"✅ Reset {wo_count} WO cooldowns and {clip_count} failed clips!")
            st.balloons()
            st.rerun()
            
    except Exception as e:
        st.error(f"Error resetting cooldowns: {e}")

def set_cooldowns_to_past(db):
    """Set all cooldowns to past date to make them immediately retryable"""
    try:
        with st.spinner("Setting cooldowns to past..."):
            past_date = (datetime.now() - timedelta(days=1)).isoformat()
            
            result = db.supabase.table('wo_tracking').update({
                'retry_after_date': past_date
            }).neq('status', 'found').not_.is_('retry_after_date', None).execute()
            
            count = len(result.data) if result.data else 0
            
            st.success(f"✅ Made {count} WOs ready for immediate retry!")
            st.rerun()
            
    except Exception as e:
        st.error(f"Error updating cooldowns: {e}")

def reset_specific_cooldowns(db, wo_numbers):
    """Reset cooldowns for specific WO numbers"""
    try:
        with st.spinner(f"Resetting {len(wo_numbers)} selected WOs..."):
            # Reset wo_tracking
            result = db.supabase.table('wo_tracking').update({
                'retry_after_date': None,
                'attempt_count': 0
            }).in_('wo_number', wo_numbers).execute()
            
            # Reset clips
            result = db.supabase.table('clips').update({
                'status': 'pending_review',
                'attempt_count': 0
            }).in_('wo_number', wo_numbers).execute()
            
            st.success(f"✅ Reset cooldowns for {len(wo_numbers)} selected WOs!")
            st.rerun()
            
    except Exception as e:
        st.error(f"Error resetting specific cooldowns: {e}")

def reset_failed_clips(db):
    """Reset all failed clips to pending_review status"""
    try:
        with st.spinner("Resetting failed clips..."):
            result = db.supabase.table('clips').update({
                'status': 'pending_review',
                'attempt_count': 0
            }).in_('status', ['no_content_found', 'processing_failed']).execute()
            
            count = len(result.data) if result.data else 0
            
            st.success(f"✅ Reset {count} failed clips to pending review!")
            st.rerun()
            
    except Exception as e:
        st.error(f"Error resetting failed clips: {e}")