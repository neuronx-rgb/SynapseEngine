"""
streamlit_app.py
Root entry point for Synapse Engine.
"""
from __future__ import annotations

import os
import sys
import time
import threading
import logging
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Synapse Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def _load_st_secrets():
    try:
        for key, val in st.secrets.items():
            if key not in os.environ:
                os.environ[key] = str(val)
    except Exception:
        pass

_load_st_secrets()

logger = logging.getLogger(__name__)
BACKEND_MODE = os.getenv("BACKEND_MODE", "embedded").lower()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

@st.cache_resource
def start_backend():
    if BACKEND_MODE != "embedded":
        logger.info(f"Remote backend mode: {BACKEND_URL}")
        return True

    def run():
        try:
            import uvicorn
            from backend.main import app
            uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
        except Exception as e:
            print(f"!!! Uvicorn crash: {e}")
            logger.error(f"Backend failed to start: {e}")

    t = threading.Thread(target=run, name="synapse-backend", daemon=True)
    t.start()
    logger.info("Backend thread started, waiting for /health...")

    import httpx
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            r = httpx.get("http://127.0.0.1:8000/health", timeout=2)
            if r.status_code == 200:
                logger.info("Backend is ready.")
                return True
        except Exception:
            pass
        time.sleep(0.5)

    logger.warning("Backend did not respond within 15s — continuing anyway.")
    return True

start_backend()

from frontend.theme import inject_theme
from frontend.api_client import get_client
from frontend.utils import ss, set_ss

inject_theme()

st.logo("static/logo.svg")

# Status strip under the navbar
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

    col1, col2, col3, _ = st.columns([2, 2, 2, 6])
    
    with col1:
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
                    
    with col2:
        st.markdown(f"**Status:** {status_text}")
        
    with col3:
        st.markdown(f"**Backend:** {provider_text}")

    st.markdown("<hr style='margin-top: 0.5rem; margin-bottom: 1.5rem; opacity: 0.2;'>", unsafe_allow_html=True)

render_status_strip()

pg = st.navigation(
    [
        st.Page("frontend/views/home.py", title="Home", icon=":material/home:"),
        st.Page("frontend/views/requirements.py", title="Requirements", icon=":material/list:"),
        st.Page("frontend/views/issues.py", title="Issues", icon=":material/report:"),
        st.Page("frontend/views/specs.py", title="Specs", icon=":material/code:"),
        st.Page("frontend/views/traceability.py", title="Traceability", icon=":material/account_tree:"),
        st.Page("frontend/views/evaluation.py", title="Evaluation", icon=":material/assessment:"),
    ],
    position="top",
)

pg.run()

st.markdown('''
    <div style="text-align: center; color: var(--text-color); font-size: 0.85em; opacity: 0.7; padding: 20px 0;">
        <p>Synapse Engine • Data is ephemeral on cloud • Free-tier LLMs may use submitted data.</p>
        <p>Uses Cornelius FR NFR Curated Dataset</p>
    </div>
''', unsafe_allow_html=True)
