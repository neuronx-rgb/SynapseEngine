import streamlit as st
import sqlite3
import pandas as pd
import io
import zipfile
from frontend.utils import ss, set_ss

def render():
    st.markdown("""
        <style>
            /* Ensure the page matches the green and black theme */
            .admin-header {
                color: #22E06B;
                font-weight: 700;
                margin-bottom: 2rem;
            }
            .stat-box {
                background-color: #05080A;
                border: 1px solid #22E06B;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                margin-bottom: 2rem;
            }
            .stat-box h3 {
                color: white;
                margin: 0;
            }
            .stat-box h1 {
                color: #22E06B;
                margin: 0;
                font-size: 3rem;
            }
        </style>
    """, unsafe_allow_html=True)

    if not ss("is_admin", False):
        st.markdown("<h2 class='admin-header'>Admin Login</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password", placeholder="Enter admin password")
        
        if st.button("Login", type="primary"):
            if pwd == "SynapseAdmin":
                set_ss("is_admin", True)
                st.rerun()
            else:
                st.error("Invalid password. Please try again.")
        st.stop()

    # Logged in Dashboard
    colA, colB = st.columns([8, 2])
    with colA:
        st.markdown("<h2 class='admin-header'>Admin Dashboard</h2>", unsafe_allow_html=True)
    with colB:
        if st.button("Logout", use_container_width=True):
            set_ss("is_admin", False)
            st.rerun()

    try:
        # Connect to local SQLite DB to fetch raw data
        conn = sqlite3.connect("synapse.db")
        projects = pd.read_sql("SELECT id, name, created_at, raw_text FROM projects ORDER BY id DESC", conn)
        artifacts = pd.read_sql("SELECT project_id, type, content FROM artifacts", conn)
        conn.close()
        
        # Stats
        st.markdown(f"""
            <div class="stat-box">
                <h3>Total Website Building Requests Till Date</h3>
                <h1>{len(projects)}</h1>
            </div>
        """, unsafe_allow_html=True)
        
        # List Requests
        st.markdown("### Customer Requests")
        if projects.empty:
            st.info("No requests received yet.")
        
        for _, p in projects.iterrows():
            with st.expander(f"Request #{p['id']} - {p['name']} (Date: {p['created_at']})"):
                
                st.markdown("#### 📄 Raw Input from Customer")
                st.info(p['raw_text'] if p['raw_text'] else "No raw input provided.")
                
                proj_arts = artifacts[artifacts['project_id'] == p['id']]
                if not proj_arts.empty:
                    st.markdown("#### 📦 Final JSON / ZIP Files")
                    
                    # Create ZIP file in memory
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for _, art in proj_arts.iterrows():
                            # Determine extension
                            ext = "json" if "json" in art['content'][:20].lower() else "txt"
                            if art['type'] == 'openapi': ext = "yaml"
                            if art['type'] == 'sql_ddl': ext = "sql"
                            
                            zip_file.writestr(f"{art['type']}.{ext}", art['content'])
                    
                    st.download_button(
                        label=f"Download ZIP for Request #{p['id']}",
                        data=zip_buffer.getvalue(),
                        file_name=f"Customer_Request_{p['id']}_Files.zip",
                        mime="application/zip",
                        key=f"zip_{p['id']}",
                        type="primary"
                    )
                else:
                    st.warning("No artifacts generated yet for this request.")
                    
    except Exception as e:
        st.error(f"Failed to load dashboard data: {e}")

render()
