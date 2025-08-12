"""
Active Jobs tab for monitoring background job processing
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
from typing import Optional
from src.utils.database import get_database
from src.utils.logger import logger
try:
    # Smooth periodic refresh without manual rerun logic
    from streamlit_extras.st_autorefresh import st_autorefresh as _st_autorefresh
except Exception:
    _st_autorefresh = None

def format_time_ago(timestamp):
    """Format timestamp as 'X minutes ago' """
    if not timestamp:
        return "Never"
    
    # Handle both string and datetime inputs
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    
    # Ensure timezone awareness
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    delta = now - timestamp
    
    if delta.total_seconds() < 60:
        return "Just now"
    elif delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(delta.total_seconds() / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"

def format_duration(seconds):
    """Format duration in seconds to human-readable format"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

def get_job_status_color(status):
    """Get color for job status"""
    colors = {
        'queued': '🔵',
        'running': '🟢',
        'completed': '✅',
        'failed': '❌',
        'cancelled': '⚫'
    }
    return colors.get(status, '⚪')

def display_active_jobs_tab():
    """Display the Active Jobs monitoring tab"""
    # Smaller, cleaner headline without emoji to match other tabs
    st.subheader("Active Jobs")
    
    # Get database connection
    db = get_database()
    if not db:
        st.error("Database connection not available")
        return
    
    # Auto-refresh toggle
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        auto_refresh = st.checkbox(
            "Auto-refresh (every 5 seconds)",
            value=st.session_state.get('auto_refresh_jobs', False),
            key='auto_refresh_jobs'
        )
    with col2:
        if st.button("🔄 Refresh Now"):
            st.rerun()
    with col3:
        if st.button("🧹 Clean Stale Jobs"):
            try:
                result = db.supabase.rpc('cleanup_stale_jobs').execute()
                if result.data:
                    st.success(f"Cleaned up {result.data} stale jobs")
            except Exception as e:
                st.error(f"Failed to cleanup stale jobs: {e}")
    
    # Auto-refresh logic (smoother): trigger periodic reruns without countdown/flicker
    if st.session_state.get('auto_refresh_jobs', False):
        if _st_autorefresh is not None:
            _st_autorefresh(interval=5000, key="jobs_autorefresh_counter")
        else:
            st.markdown("<script>setTimeout(() => window.location.reload(), 5000);</script>", unsafe_allow_html=True)
        st.caption(f"Auto-refreshing every 5s · Last updated {datetime.now().strftime('%H:%M:%S')}")
    
    # Get current user email
    user_email = st.session_state.get('user_email')
    
    # Tabs for different views - just Active Jobs and History
    tab1, tab2 = st.tabs(["Active Jobs", "Job History"])
    
    with tab1:
        st.subheader("Active Jobs")
        display_all_active_jobs(db)
    
    with tab2:
        st.subheader("Job History")
        display_job_history(db, user_email)


def display_job_logs(db, job_id):
    """Display logs for a specific job"""
    try:
        result = db.supabase.table('job_logs').select('*').eq(
            'job_id', job_id
        ).order('timestamp', desc=True).limit(50).execute()
        
        if result.data:
            st.markdown("**Recent Logs:**")
            for log in reversed(result.data):  # Show oldest first
                level = log.get('level', 'INFO')
                timestamp = format_time_ago(log.get('timestamp'))
                message = log.get('message', '')
                
                # Color code by level
                if level == 'ERROR':
                    st.error(f"[{timestamp}] {message}")
                elif level == 'WARNING':
                    st.warning(f"[{timestamp}] {message}")
                else:
                    st.info(f"[{timestamp}] {message}")
        else:
            st.info("No logs available for this job")
    except Exception as e:
        st.error(f"Failed to load logs: {e}")

def display_all_active_jobs(db):
    """Display all active jobs in the system"""
    try:
        # Get all active jobs
        result = db.supabase.table('processing_runs').select('*').in_(
            'job_status', ['queued', 'running']
        ).order('created_at', desc=True).execute()
        
        if not result.data:
            st.info("No active jobs in the system")
            return
        
        # Display each job with a progress bar
        for job in result.data:
            status_icon = get_job_status_color(job.get('job_status', 'unknown'))
            
            # Create columns for job display
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            
            with col1:
                st.markdown(f"**{status_icon} {job.get('run_name', 'Unnamed Job')}**")
                st.caption(f"Type: {job.get('job_type', 'unknown')} | User: {job.get('created_by', 'System')}")
            
            with col2:
                if job.get('job_status') == 'running':
                    progress_current = job.get('progress_current', 0)
                    progress_total = job.get('progress_total', 0)
                    started_at = job.get('started_at')
                    eta_text = ""
                    if started_at and progress_total:
                        try:
                            start_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                            elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds()
                            rate = progress_current / max(elapsed, 1)
                            remaining = (progress_total - progress_current) / max(rate, 1e-6)
                            eta_text = f" · ETA {int(remaining//60)}m {int(remaining%60)}s"
                        except Exception:
                            eta_text = ""
                    
                    if progress_total > 0:
                        progress_pct = (progress_current / progress_total)
                        st.progress(progress_pct)
                        st.caption(f"{progress_current}/{progress_total} ({progress_pct*100:.1f}%){eta_text}")
                    else:
                        st.progress(0)
                        st.caption("Initializing...")
                else:
                    st.caption("Queued - waiting to start")
            
            with col3:
                st.caption(f"Created: {format_time_ago(job.get('created_at'))}")
                if job.get('last_heartbeat'):
                    st.caption(f"Updated: {format_time_ago(job.get('last_heartbeat'))}")
            
            with col4:
                # Show different button text based on status
                button_text = "🛑 Stop" if job.get('job_status') == 'running' else "❌ Cancel"
                if st.button(button_text, key=f"cancel_all_{job['id']}"):
                    try:
                        db.supabase.table('processing_runs').update({
                            'job_status': 'cancelled',
                            'completed_at': datetime.now(timezone.utc).isoformat(),
                            'error_message': 'Cancelled by user'
                        }).eq('id', job['id']).execute()
                        st.success("Job cancelled")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to cancel: {e}")
            
            st.divider()
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            queued_count = len([j for j in result.data if j.get('job_status') == 'queued'])
            st.metric("Queued Jobs", queued_count)
        with col2:
            running_count = len([j for j in result.data if j.get('job_status') == 'running'])
            st.metric("Running Jobs", running_count)
        with col3:
            unique_users = len(set([j.get('created_by', 'System') for j in result.data]))
            st.metric("Active Users", unique_users)
            
    except Exception as e:
        st.error(f"Failed to load active jobs: {e}")


def display_job_history(db, user_email: Optional[str]):
    """Display historical jobs"""
    st.markdown("### Recent Job History")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        show_my_jobs = st.checkbox("Show only my jobs", value=True if user_email else False)
    
    with col2:
        status_filter = st.selectbox(
            "Status Filter",
            ["All", "completed", "failed", "cancelled"]
        )
    
    with col3:
        job_type_filter = st.selectbox(
            "Job Type",
            ["All", "csv_upload", "sentiment_analysis", "historical_reprocessing", "fms_export"]
        )
    
    try:
        # Build query
        query = db.supabase.table('processing_runs').select('*')
        
        # Apply filters
        if show_my_jobs and user_email:
            query = query.eq('created_by', user_email)
        
        if status_filter != "All":
            query = query.eq('job_status', status_filter)
        
        if job_type_filter != "All":
            query = query.eq('job_type', job_type_filter)
        
        # Get recent jobs
        result = query.order('created_at', desc=True).limit(50).execute()
        
        if not result.data:
            st.info("No job history found with the selected filters")
            return
        
        # Create DataFrame
        df = pd.DataFrame(result.data)
        
        # Format for display
        df['Status'] = df['job_status'].apply(lambda x: f"{get_job_status_color(x)} {x}")
        
        # Extract numbers from each job - use actual values from database
        df['Processed'] = df['total_records'].fillna(0).astype(int)
        df['Successful'] = df['successful_finds'].fillna(0).astype(int)
        df['Failed'] = df['failed_attempts'].fillna(0).astype(int)
        
        # Use actual skipped count if available, otherwise calculate
        if 'skipped_count' in df.columns:
            df['Skipped'] = df['skipped_count'].fillna(0).astype(int)
        else:
            df['Skipped'] = df.apply(lambda row: max(0, row['Processed'] - row['Successful'] - row['Failed']), axis=1)
        
        # Use actual error count if available
        if 'error_count' in df.columns:
            df['Errors'] = df['error_count'].fillna(0).astype(int)
        else:
            df['Errors'] = df['failed_attempts'].fillna(0).astype(int)
        
        # Calculate duration
        def calculate_duration(row):
            if row.get('started_at') and row.get('completed_at'):
                start = datetime.fromisoformat(row['started_at'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(row['completed_at'].replace('Z', '+00:00'))
                return format_duration((end - start).total_seconds())
            elif row.get('job_status') == 'running':
                return "Running"
            elif row.get('job_status') == 'queued':
                return "Queued"
            return "N/A"
        
        df['Duration'] = df.apply(calculate_duration, axis=1)
        
        # Format created date
        df['Created'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
        
        # Show actual user email
        df['User'] = df['created_by'].fillna('System')
        
        # Display table with individual columns for each statistic
        st.dataframe(
            df[['Status', 'Processed', 'Successful', 'Failed', 'Skipped', 'Errors', 'Duration', 'Created', 'User']],
            use_container_width=True,
            hide_index=True
        )
        
        # Summary stats
        st.markdown("### Summary Statistics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_jobs = len(df)
            st.metric("Total Jobs", total_jobs)
        
        with col2:
            completed = len(df[df['job_status'] == 'completed'])
            st.metric("Completed", completed)
        
        with col3:
            failed = len(df[df['job_status'] == 'failed'])
            st.metric("Failed", failed)
        
        with col4:
            if completed > 0:
                success_rate = (completed / (completed + failed)) * 100 if (completed + failed) > 0 else 0
                st.metric("Success Rate", f"{success_rate:.1f}%")
            else:
                st.metric("Success Rate", "N/A")
                
    except Exception as e:
        st.error(f"Failed to load job history: {e}")

# Helper function to submit a new job
def submit_job_to_queue(job_type: str, job_params: dict, run_name: str, user_email: str) -> str:
    """Submit a new job to the queue"""
    db = get_database()
    
    try:
        # Normalize user email
        created_by = user_email or 'System'
        # Create job record
        result = db.supabase.table('processing_runs').insert({
            'run_name': run_name,
            'job_type': job_type,
            'job_status': 'queued',
            'job_params': job_params,
            'created_by': created_by,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'total_records': 0,
            'successful_finds': 0,
            'failed_attempts': 0,
            'run_status': 'running'  # For backward compatibility
        }).execute()
        
        if result.data:
            job_id = result.data[0]['id']
            logger.info(f"Job {job_id} submitted to queue: {run_name}")
            return job_id
        else:
            raise Exception("Failed to create job record")
            
    except Exception as e:
        logger.error(f"Failed to submit job: {e}")
        raise e