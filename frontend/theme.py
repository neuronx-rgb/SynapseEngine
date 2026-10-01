import streamlit as st

def inject_theme():
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Hide sidebar and toggle completely to force manual Top Navigation */
    [data-testid="stSidebar"] {
        display: none !important;
    }
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    
    /* Style page links to be green buttons with white text */
    div[data-testid="stPageLink-NavLink"] {
        background-color: #22E06B !important;
        border-radius: 8px !important;
        padding: 8px 0px !important;
        justify-content: center !important;
    }
    div[data-testid="stPageLink-NavLink"] p {
        color: white !important;
        font-weight: 600 !important;
    }
    div[data-testid="stPageLink-NavLink"]:hover {
        background-color: #1cbd5a !important;
    }
</style>
""", unsafe_allow_html=True)
