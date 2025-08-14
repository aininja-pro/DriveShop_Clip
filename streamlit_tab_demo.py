import streamlit as st

st.set_page_config(page_title="Tab Customization Demo", layout="wide")

st.title("Streamlit Tab Customization Demo")

# Custom CSS for colored tabs without icons
st.markdown("""
<style>
    /* Remove the default gray background of tabs */
    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent;
        gap: 8px;
    }
    
    /* Style for all tabs */
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
        border-radius: 8px;
        border: none;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    /* Hover effect for all tabs */
    .stTabs [data-baseweb="tab"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* Custom colors for each tab using nth-child selector */
    /* Tab 1 - Light Blue (like your Approve button) */
    .stTabs [data-baseweb="tab-list"] button[aria-controls="tabs-bui3-tabpanel-0"] {
        background-color: #e3f2fd;
        color: #1565c0;
    }
    
    /* Tab 2 - Light Green */
    .stTabs [data-baseweb="tab-list"] button[aria-controls="tabs-bui3-tabpanel-1"] {
        background-color: #e8f5e9;
        color: #2e7d32;
    }
    
    /* Tab 3 - Light Yellow/Orange */
    .stTabs [data-baseweb="tab-list"] button[aria-controls="tabs-bui3-tabpanel-2"] {
        background-color: #fff3e0;
        color: #e65100;
    }
    
    /* Tab 4 - Light Purple */
    .stTabs [data-baseweb="tab-list"] button[aria-controls="tabs-bui3-tabpanel-3"] {
        background-color: #f3e5f5;
        color: #6a1b9a;
    }
    
    /* Tab 5 - Light Pink */
    .stTabs [data-baseweb="tab-list"] button[aria-controls="tabs-bui3-tabpanel-4"] {
        background-color: #fce4ec;
        color: #c2185b;
    }
    
    /* Tab 6 - Light Teal */
    .stTabs [data-baseweb="tab-list"] button[aria-controls="tabs-bui3-tabpanel-5"] {
        background-color: #e0f2f1;
        color: #00695c;
    }
    
    /* Tab 7 - Light Gray */
    .stTabs [data-baseweb="tab-list"] button[aria-controls="tabs-bui3-tabpanel-6"] {
        background-color: #f5f5f5;
        color: #424242;
    }
    
    /* Active tab styling - make it slightly darker */
    .stTabs [aria-selected="true"] {
        opacity: 0.85;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        transform: translateY(-1px);
    }
    
    /* Remove the default bottom border indicator */
    .stTabs [data-baseweb="tab-highlight"] {
        background-color: transparent;
    }
    
    /* Hide all tab icons/emojis */
    .stTabs [data-baseweb="tab"] p {
        font-size: 14px;
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

# Create tabs WITHOUT icons
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Bulk Review",
    "Approved Queue", 
    "Rejected Issues",
    "Strategic Intelligence",
    "CreatorIQ Export",
    "Export",
    "File History"
])

with tab1:
    st.header("Bulk Review")
    st.write("This tab has a light blue background color.")
    
with tab2:
    st.header("Approved Queue")
    st.write("This tab has a light green background color.")
    
with tab3:
    st.header("Rejected Issues")
    st.write("This tab has a light orange background color.")
    
with tab4:
    st.header("Strategic Intelligence")
    st.write("This tab has a light purple background color.")
    
with tab5:
    st.header("CreatorIQ Export")
    st.write("This tab has a light pink background color.")
    
with tab6:
    st.header("Export")
    st.write("This tab has a light teal background color.")
    
with tab7:
    st.header("File History") 
    st.write("This tab has a light gray background color.")

st.divider()

st.subheader("Alternative Approach: Custom Tab-like Buttons")

# Create custom colored buttons that look like tabs
col1, col2, col3, col4, col5, col6, col7 = st.columns(7)

# Session state to track selected tab
if 'selected_tab' not in st.session_state:
    st.session_state.selected_tab = 0

# Custom CSS for button tabs
st.markdown("""
<style>
    /* Custom button styling to look like tabs */
    .tab-button {
        width: 100%;
        padding: 12px 8px;
        border: none;
        border-radius: 8px 8px 0 0;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        margin-bottom: -1px;
    }
    
    .tab-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
    }
    
    /* Individual button colors */
    .tab-blue { background-color: #e3f2fd; color: #1565c0; }
    .tab-green { background-color: #e8f5e9; color: #2e7d32; }
    .tab-orange { background-color: #fff3e0; color: #e65100; }
    .tab-purple { background-color: #f3e5f5; color: #6a1b9a; }
    .tab-pink { background-color: #fce4ec; color: #c2185b; }
    .tab-teal { background-color: #e0f2f1; color: #00695c; }
    .tab-gray { background-color: #f5f5f5; color: #424242; }
    
    /* Active state */
    .tab-active {
        box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.15);
        transform: translateY(-1px);
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# Button tabs
with col1:
    if st.button("Bulk Review", key="btn1", use_container_width=True):
        st.session_state.selected_tab = 0
        
with col2:
    if st.button("Approved", key="btn2", use_container_width=True):
        st.session_state.selected_tab = 1
        
with col3:
    if st.button("Rejected", key="btn3", use_container_width=True):
        st.session_state.selected_tab = 2
        
with col4:
    if st.button("Strategic", key="btn4", use_container_width=True):
        st.session_state.selected_tab = 3
        
with col5:
    if st.button("CreatorIQ", key="btn5", use_container_width=True):
        st.session_state.selected_tab = 4
        
with col6:
    if st.button("Export", key="btn6", use_container_width=True):
        st.session_state.selected_tab = 5
        
with col7:
    if st.button("History", key="btn7", use_container_width=True):
        st.session_state.selected_tab = 6

# Content area with border
st.markdown("""
<div style="border: 1px solid #e0e0e0; border-radius: 0 0 8px 8px; padding: 20px; min-height: 200px;">
""", unsafe_allow_html=True)

# Display content based on selected tab
tab_contents = [
    ("Bulk Review Content", "Light blue themed content area"),
    ("Approved Queue Content", "Light green themed content area"),
    ("Rejected Issues Content", "Light orange themed content area"),
    ("Strategic Intelligence Content", "Light purple themed content area"),
    ("CreatorIQ Export Content", "Light pink themed content area"),
    ("Export Content", "Light teal themed content area"),
    ("File History Content", "Light gray themed content area")
]

st.subheader(tab_contents[st.session_state.selected_tab][0])
st.write(tab_contents[st.session_state.selected_tab][1])

st.markdown("</div>", unsafe_allow_html=True)