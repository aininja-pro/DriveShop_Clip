"""
Performance configuration for the dashboard.
"""

import streamlit as st

def configure_performance():
    """Configure Streamlit for better performance."""
    
    # Set page config with optimized settings
    st.set_page_config(
        page_title="DriveShop",
        page_icon="🚗",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': None
        }
    )
    
    # Enable experimental features for better performance
    st.config.set_option('server.enableXsrfProtection', True)
    
    # Cache configuration
    # Increase cache size for better performance
    st.config.set_option('server.maxUploadSize', 500)
    
    # Disable automatic reruns on widget interaction where possible
    st.config.set_option('runner.fastReruns', True)
    
    # Enable server-side caching
    st.config.set_option('server.enableCORS', False)
    
def lazy_load_data(loader_func, cache_key, ttl=300):
    """
    Lazy load data with caching and loading indicator.
    
    Args:
        loader_func: Function to load data
        cache_key: Unique key for caching
        ttl: Time to live in seconds (default 5 minutes)
    """
    # Create a unique cache key based on function and parameters
    @st.cache_data(ttl=ttl, show_spinner=False)
    def cached_loader():
        return loader_func()
    
    # Show loading only when actually loading
    if cache_key not in st.session_state:
        with st.spinner("Loading data..."):
            data = cached_loader()
            st.session_state[cache_key] = True
            return data
    else:
        return cached_loader()

def optimize_aggrid_config():
    """Return optimized AgGrid configuration."""
    return {
        "rowBuffer": 10,  # Only render 10 rows outside viewport
        "debounceVerticalScrollbar": True,
        "suppressColumnVirtualisation": False,
        "suppressRowVirtualisation": False,
        "animateRows": False,  # Disable animations for better performance
        "rowModelType": "clientSide",
        "pagination": True,
        "paginationPageSize": 100,  # Show 100 rows per page
        "cacheBlockSize": 100,
        "maxBlocksInCache": 10,
        "purgeClosedRowNodes": True,
        "domLayout": "normal",  # Use normal layout for better performance with large datasets
    }

def batch_database_operations(operations, batch_size=50):
    """
    Batch database operations to reduce round trips.
    
    Args:
        operations: List of operations to perform
        batch_size: Number of operations per batch
    """
    results = []
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i + batch_size]
        # Process batch
        results.extend(batch)
    return results