import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

st.set_page_config(layout="wide")
st.title("🔗 Claude's Class-Based Cell Renderer Test")

# Test data with your actual Jetta URL
df = pd.DataFrame({
    'WO #': ['1201562'],
    'Model': ['Jetta'],
    'Contact': ['Anthony Fongaro'],
    'Publication': ['The Gentleman Racer'],
    'Score': ['10/10'],
    'Sentiment': ['😊 Pos'],
    'URL': ['https://thegentlemanracer.com/2025/05/jetta-gli/'],
    'Link_Text': ['📄 View']
})

st.write("**Testing Claude's class-based cell renderer approach:**")

# Configure grid options
gb = GridOptionsBuilder.from_dataframe(df)

# Claude's class-based cell renderer
cell_renderer = JsCode("""
    class UrlCellRenderer {
        init(params) {
            this.eGui = document.createElement('a');
            this.eGui.innerText = '📄 View';
            this.eGui.setAttribute('href', params.data.URL);
            this.eGui.setAttribute('style', "text-decoration:none; color: #0066cc; font-weight: bold;");
            this.eGui.setAttribute('target', "_blank");
        }
        getGui() {
            return this.eGui;
        }
    }
""")

# Apply the cell renderer to the URL column
gb.configure_column("URL", cellRenderer=cell_renderer)
gb.configure_column("Link_Text", hide=True)  # Hide redundant column

gb.configure_grid_options(domLayout='normal')
gridOptions = gb.build()

# Display the grid
st.write("**If this works, you should see a clickable '📄 View' link in the URL column:**")
AgGrid(df, gridOptions=gridOptions, height=200, allow_unsafe_jscode=True)

st.write("---")
st.write("**For comparison, here's the old approach that showed raw HTML:**")

# Old approach for comparison
gb2 = GridOptionsBuilder.from_dataframe(df)
old_cell_renderer = JsCode("""
function(params) {
    return `<a href="${params.data.URL}" target="_blank">📄 View</a>`
}
""")

gb2.configure_column("URL", cellRenderer=old_cell_renderer)
gb2.configure_column("Link_Text", hide=True)

grid_options2 = gb2.build()
grid_options2["suppressHtmlEscaping"] = True

AgGrid(df, gridOptions=grid_options2, height=200, allow_unsafe_jscode=True, theme="alpine") 