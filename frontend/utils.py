import streamlit as st
from frontend.api_client import get_client

def ss(key: str, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

def set_ss(key: str, value):
    st.session_state[key] = value

def _safe_read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

SAMPLE_TEXTS = {
    "-- Select a sample --": "",
    "(a) Order System": _safe_read("samples/order_system.txt"),
    "(b) Account Email Conflict": _safe_read("samples/account_email.txt"),
    "(c) Salon Booking (Vague)": _safe_read("samples/salon_booking.txt"),
}

STAGES = ["Parse", "Analyze", "Clarify", "Generate", "Verify"]

def render_progress(stage: str):
    stage_map = {"input": -1, "parse": 0, "analyze": 1, "clarify": 2, "generate": 3, "verify": 4}
    current = stage_map.get(stage, -1)

    html = '<div class="step-bar" style="display: flex; gap: 8px; align-items: center; margin-bottom: 20px;">'
    for i, s in enumerate(STAGES):
        cls_color = "#166534" if i < current else ("#2563eb" if i == current else "#1e3a5f")
        text_color = "#86efac" if i < current else ("white" if i == current else "#93c5fd")
        check = "✓ " if i < current else ""
        html += f'<div style="padding: 4px 14px; border-radius: 20px; background: {cls_color}; color: {text_color}; font-size: 0.82em; font-weight: 600;">{check}{s}</div>'
        if i < len(STAGES) - 1:
            html += '<span style="color:#334155">→</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
