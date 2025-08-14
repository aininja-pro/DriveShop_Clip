"""
Add this to your Streamlit dashboard to show process status
"""

import streamlit as st
from datetime import datetime, timedelta

def show_process_status(supabase_client):
    """Display current process status in the dashboard"""
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔄 Process Status")
    
    # Check for recent activity
    five_mins_ago = (datetime.now() - timedelta(minutes=5)).isoformat()
    
    recent_activity = supabase_client.table('clips') \
        .select('count') \
        .gte('created_at', five_mins_ago) \
        .execute()
    
    if recent_activity.count > 0:
        st.sidebar.success(f"✅ ACTIVE: {recent_activity.count} clips in last 5 min")
    else:
        st.sidebar.warning("⏸️ No recent activity")
    
    # Show last update time
    last_clip = supabase_client.table('clips') \
        .select('created_at') \
        .order('created_at', desc=True) \
        .limit(1) \
        .execute()
    
    if last_clip.data:
        last_time = datetime.fromisoformat(last_clip.data[0]['created_at'].replace('Z', '+00:00'))
        mins_ago = (datetime.now() - last_time).seconds // 60
        st.sidebar.text(f"Last clip: {mins_ago} mins ago")
    
    # Add refresh button
    if st.sidebar.button("🔄 Refresh Status"):
        st.rerun()

# Add to your main dashboard app
# show_process_status(supabase)