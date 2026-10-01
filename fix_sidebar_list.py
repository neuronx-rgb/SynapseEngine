import re

with open("streamlit_app.py", "r", encoding="utf-8") as f:
    content = f.read()

new_strip = """
# Status strip
def render_status_strip():
    client = get_client()
    try:
        health = client.health()
        provider = health.get("active_provider", "unknown")
        model = health.get("model", "unknown")
        mock = health.get("mock_mode", True)
        
        status_text = "🟢 Online"
        if mock:
            provider_text = "🛠️ MOCK_MODE"
        else:
            provider_text = f"{provider} / {model}"
    except Exception:
        status_text = "🔴 Backend offline"
        provider_text = "Unknown"

    st.sidebar.markdown(f"**Status:** {status_text}")
    st.sidebar.markdown(f"**Backend:** {provider_text}")
    st.sidebar.divider()

    st.sidebar.markdown("### Projects")
    project_id = ss("project_id")
    
    try:
        all_projects = client._get("/projects")
        if all_projects:
            proj_options = {p['id']: f"#{p['id']} - {p['name']}" for p in all_projects}
            
            # Find index of current project
            idx = 0
            if project_id and project_id in proj_options:
                idx = list(proj_options.keys()).index(project_id)
                
            selected_id = st.sidebar.selectbox("Select Project", options=list(proj_options.keys()), format_func=lambda x: proj_options[x], index=idx, label_visibility="collapsed")
            
            if selected_id != project_id:
                set_ss("project_id", selected_id)
                set_ss("pipeline_stage", "input")
                st.rerun()
        else:
            st.sidebar.markdown("*No projects exist yet.*")
    except Exception as e:
        st.sidebar.error("Failed to load projects.")

    if st.sidebar.button("➕ New Project", key="strip_new_proj", use_container_width=True):
        try:
            name = f"Project-{int(time.time())}"
            proj = client.create_project(name=name)
            set_ss("project_id", proj["id"])
            set_ss("pipeline_stage", "input")
            set_ss("issues", [])
            set_ss("artifacts", [])
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
"""

content = re.sub(r'# Status strip.*?render_status_strip\(\)', new_strip.strip() + "\n\nrender_status_strip()", content, flags=re.DOTALL)

with open("streamlit_app.py", "w", encoding="utf-8") as f:
    f.write(content)
