import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, JsCode
from st_aggrid.grid_options_builder import GridOptionsBuilder

st.set_page_config(layout="wide")
st.title("🔗 Simple Clickable Links Test (Perplexity Method)")

# Sample data with real URL
data = {
    "WO #": ["1201562"],
    "Model": ["Jetta"],
    "Contact": ["Anthony Fongaro"],
    "Publication": ["The Gentleman Racer"],
    "Score": ["10/10"],
    "Sentiment": ["😊 Pos"],
    "Clip URL": ["https://thegentlemanracer.com/2025/05/jetta-gli/"]
}
df = pd.DataFrame(data)

st.write("**Testing the exact Perplexity approach:**")

# Build grid options
gb = GridOptionsBuilder.from_dataframe(df)

# Configure clickable link column using Perplexity's exact approach
cell_renderer = JsCode("""
function(params) {
    return `<a href="${params.value}" target="_blank">📄 View</a>`
}
""")

gb.configure_column("Clip URL", headerName="📄 View", cellRenderer=cell_renderer)

# Render table using Perplexity's simple approach
st.write("**Method 1: Perplexity's Basic Approach**")
AgGrid(df, gridOptions=gb.build(), allow_unsafe_jscode=True)

st.write("---")

# Let's also try with our current complex approach for comparison
st.write("**Method 2: Our Current Complex Approach**")
gb2 = GridOptionsBuilder.from_dataframe(df)
gb2.configure_column("Clip URL", hide=True)
gb2.configure_column("Clip URL", headerName="📄 View", cellRenderer=cell_renderer)

grid_options = gb2.build()
grid_options["suppressHtmlEscaping"] = True

AgGrid(df, gridOptions=grid_options, allow_unsafe_jscode=True, theme="alpine") 