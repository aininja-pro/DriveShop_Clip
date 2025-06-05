# example.py
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode

st.set_page_config(layout="wide")

st.title("📊 Clickable Links in AgGrid Column")

# 1) Build a tiny DataFrame that has one real URL in it
df = pd.DataFrame({
    "WO #": ["1201562"],
    "Model": ["Jetta"],
    "Contact": ["Anthony Fongaro"],
    "Publication": ["The Gentleman Racer"],
    "Score": ["10/10"],
    "Sentiment": ["😊 Pos"],
    # This column holds the raw URL (we will hide it)
    "Clip URL": ["https://thegentlemanracer.com/2025/05/jetta-gli/"],
    # Copy it again into a "View" column so we can run a cellRenderer
    "📄 View":   ["https://thegentlemanracer.com/2025/05/jetta-gli/"],
    "✅ Approve": [False],
    "❌ Reject":  [False]
})

# 2) Start a GridOptionsBuilder from that DataFrame
gb = GridOptionsBuilder.from_dataframe(df)

# 3) Hide the raw "Clip URL" column
gb.configure_column("Clip URL", hide=True)

# 4) Enable Excel‐style filters/sorting/resizing on every other column
gb.configure_default_column(filter=True, sortable=True, resizable=True, width=120)

# 5) Lock in widths to roughly match your real layout
gb.configure_column("WO #",        width= 80)
gb.configure_column("Model",       width=120)
gb.configure_column("Contact",     width=150)
gb.configure_column("Publication", width=180)
gb.configure_column("Score",       width= 80)
gb.configure_column("Sentiment",   width=100)
gb.configure_column("📄 View",     width=100)
gb.configure_column("✅ Approve",  width=100)
gb.configure_column("❌ Reject",   width=100)

# 6) Add a JavaScript cellRenderer that returns a clickable <a>…</a>
link_renderer = JsCode("""
    function(params) {
        if (!params.value) {
            return ""; 
        }
        return `<a href="${params.value}" target="_blank"
                   style="text-decoration:none;color:#1976d2;font-weight:bold;">
                   📄 View</a>`;
    }
""")
gb.configure_column("📄 View", cellRenderer=link_renderer, filter=False)

# 7) Build the gridOptions, then inject suppressHtmlEscaping at the root
grid_options = gb.build()

# ———————————————— MANDATORY: force this into the root of gridOptions ————————————————
grid_options["suppressHtmlEscaping"] = True
# (If this line is missing, Ag-Grid will escape your <a> as plain text.)

# 8) Finally render the AgGrid with allow_unsafe_jscode=True
AgGrid(
    df,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    allow_unsafe_jscode=True,
    enable_enterprise_modules=False,
    height=500,
    fit_columns_on_grid_load=True,
    theme="alpine"  # Use "alpine" theme instead of "light" to honor suppressHtmlEscaping
) 