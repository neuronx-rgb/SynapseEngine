"""
streamlit_app.py
Root entry point for Synapse Engine.

BACKEND_MODE=embedded (default): starts FastAPI in a background daemon thread.
BACKEND_MODE=remote: reads BACKEND_URL.
"""
from __future__ import annotations

import os
import sys
import time
import threading
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load env from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try to load from Streamlit secrets (Community Cloud)
def _load_st_secrets():
    try:
        import streamlit as st
        for key, val in st.secrets.items():
            if key not in os.environ:
                os.environ[key] = str(val)
    except Exception:
        pass

_load_st_secrets()

logger = logging.getLogger(__name__)
BACKEND_MODE = os.getenv("BACKEND_MODE", "embedded").lower()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


# ---------------------------------------------------------------------------
# Embedded backend (FastAPI + uvicorn in background thread)
# ---------------------------------------------------------------------------

import streamlit as st

@st.cache_resource
def start_backend():
    """Start FastAPI/uvicorn in a daemon thread. Called once per process."""
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

    # Wait up to 15s for the backend to be ready
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


# Start (cached — only runs once)
start_backend()

# Now run the Streamlit UI
from frontend.app import main
main()
