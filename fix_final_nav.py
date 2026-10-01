import re

with open("streamlit_app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject aggressive CSS specifically for the page links right above the nav container
nav_css = """
st.markdown('''
<style>
    /* Aggressive styling for page links to make them solid green */
    [data-testid="stPageLink"] {
        background-color: #22E06B !important;
        border-radius: 6px !important;
        padding: 5px !important;
    }
    [data-testid="stPageLink"] a {
        justify-content: center !important;
        text-decoration: none !important;
    }
    [data-testid="stPageLink"] p {
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        margin: 0 !important;
    }
</style>
''', unsafe_allow_html=True)

# Custom Guaranteed Horizontal Navigation Bar
"""
content = content.replace("# Custom Guaranteed Horizontal Navigation Bar\n", nav_css)


# 2. Remove Status and Backend from the strip
status_strip_old = """
    col_proj, col_stat, col_back, _ = st.columns([2, 2, 3, 5])
    
    with col_proj:
        with st.popover("📁 Project"):
            st.markdown("### Projects")
            project_id = ss("project_id")
            
            try:
                all_projects = client._get("/projects")
                if all_projects:
                    proj_options = {p['id']: f"#{p['id']} - {p['name']}" for p in all_projects}
                    idx = 0
                    if project_id and project_id in proj_options:
                        idx = list(proj_options.keys()).index(project_id)
                        
                    selected_id = st.selectbox("Select Project", options=list(proj_options.keys()), format_func=lambda x: proj_options[x], index=idx, label_visibility="collapsed")
                    
                    if selected_id != project_id:
                        set_ss("project_id", selected_id)
                        set_ss("pipeline_stage", "input")
                        st.rerun()
                else:
                    st.markdown("*No projects exist yet.*")
            except Exception as e:
                st.error("Failed to load projects.")

            if st.button("➕ New Project", key="strip_new_proj", use_container_width=True):
                try:
                    name = f"Project-{int(time.time())}"
                    proj = client.create_project(name=name)
                    set_ss("project_id", proj["id"])
                    set_ss("pipeline_stage", "input")
                    set_ss("issues", [])
                    set_ss("artifacts", [])
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
                    
    with col_stat:
        st.markdown(f"**Status:** {status_text}")
        
    with col_back:
        st.markdown(f"**Backend:** {provider_text}")
"""

status_strip_new = """
    col_proj, _ = st.columns([2, 10])
    
    with col_proj:
        with st.popover("📁 Project"):
            st.markdown("### Projects")
            project_id = ss("project_id")
            
            try:
                all_projects = client._get("/projects")
                if all_projects:
                    proj_options = {p['id']: f"#{p['id']} - {p['name']}" for p in all_projects}
                    idx = 0
                    if project_id and project_id in proj_options:
                        idx = list(proj_options.keys()).index(project_id)
                        
                    selected_id = st.selectbox("Select Project", options=list(proj_options.keys()), format_func=lambda x: proj_options[x], index=idx, label_visibility="collapsed")
                    
                    if selected_id != project_id:
                        set_ss("project_id", selected_id)
                        set_ss("pipeline_stage", "input")
                        st.rerun()
                else:
                    st.markdown("*No projects exist yet.*")
            except Exception as e:
                st.error("Failed to load projects.")

            if st.button("➕ New Project", key="strip_new_proj", use_container_width=True):
                try:
                    name = f"Project-{int(time.time())}"
                    proj = client.create_project(name=name)
                    set_ss("project_id", proj["id"])
                    set_ss("pipeline_stage", "input")
                    set_ss("issues", [])
                    set_ss("artifacts", [])
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
"""

content = content.replace(status_strip_old.strip(), status_strip_new.strip())

with open("streamlit_app.py", "w", encoding="utf-8") as f:
    f.write(content)
