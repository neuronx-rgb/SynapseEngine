"""
frontend/app.py
Synapse Engine — Streamlit UI
Dark navy + light blue theme. Five tabs:
1) Requirements  2) Issues & Clarification  3) Specs  4) Traceability  5) Evaluation
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional

import streamlit as st

from frontend.api_client import get_client

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Synapse Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark navy custom CSS
st.markdown("""
<style>
  /* Dark navy background */
  .stApp { background-color: #0d1b2a; color: #e0e8f0; }
  section[data-testid="stSidebar"] { background-color: #0a1520; }

  /* Cards */
  .card {
    background: #152236;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
    border-left: 4px solid #3b82f6;
  }
  .card.blocking { border-left-color: #ef4444; }
  .card.warning  { border-left-color: #f59e0b; }
  .card.answered { border-left-color: #22c55e; }
  .card.assumed  { border-left-color: #a855f7; }

  /* Badges */
  .badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.78em;
    font-weight: 600;
    margin-right: 6px;
  }
  .badge-blocking  { background: #7f1d1d; color: #fca5a5; }
  .badge-warning   { background: #78350f; color: #fcd34d; }
  .badge-conflict  { background: #1e3a5f; color: #93c5fd; }
  .badge-ambiguity { background: #2d1b69; color: #c4b5fd; }
  .badge-incomplete{ background: #064e3b; color: #6ee7b7; }
  .badge-ok        { background: #14532d; color: #86efac; }
  .badge-error     { background: #7f1d1d; color: #fca5a5; }

  /* Progress steps */
  .step-bar {
    display: flex; gap: 8px; align-items: center;
    margin-bottom: 20px;
  }
  .step { 
    padding: 4px 14px; border-radius: 20px;
    background: #1e3a5f; color: #93c5fd;
    font-size: 0.82em; font-weight: 600;
  }
  .step.active { background: #2563eb; color: white; }
  .step.done   { background: #166534; color: #86efac; }

  /* Tab styling */
  .stTabs [data-baseweb="tab"] { color: #94a3b8; }
  .stTabs [aria-selected="true"] { color: #60a5fa; border-bottom-color: #60a5fa; }

  /* Input boxes */
  .stTextArea textarea { background: #152236; color: #e0e8f0; border-color: #1e3a5f; }
  .stTextInput input   { background: #152236; color: #e0e8f0; border-color: #1e3a5f; }

  /* Buttons */
  .stButton > button { background: #2563eb; color: white; border: none; border-radius: 6px; }
  .stButton > button:hover { background: #1d4ed8; }

  h1, h2, h3, h4 { color: #60a5fa; }
  code { background: #1e3a5f; color: #93c5fd; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

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


def _load_dataset_projects() -> dict[str, list[dict]]:
    """Load dataset_real.json and return {project_name: [req_dicts]}."""
    import json
    from pathlib import Path
    path = Path("eval/dataset_real.json")
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            docs = json.load(f)
        result = {}
        for doc in docs:
            project = doc.get("project", "Unknown")
            result[project] = doc.get("requirements", [])
        return result
    except Exception:
        return {}


def _dataset_reqs_to_text(reqs: list[dict], n: int) -> str:
    """Convert sampled dataset requirements to plain-text input format."""
    lines = []
    for i, r in enumerate(reqs[:n], start=1):
        req_id = r.get("req_id", f"REQ-{i:03d}")
        text = r.get("text", "")
        lines.append(f"{req_id}: {text}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Sidebar — status
# ---------------------------------------------------------------------------

def render_sidebar():
    with st.sidebar:
        st.markdown("## ⚡ Synapse Engine")
        st.markdown("*LLM Specification Compiler*")
        st.divider()

        client = get_client()
        try:
            health = client.health()
            provider = health.get("active_provider", "unknown")
            model = health.get("model", "unknown")
            mock = health.get("mock_mode", True)

            st.markdown(f"**Status:** 🟢 Online")
            if mock:
                st.markdown("**Mode:** 🎭 `MOCK_MODE`")
                st.info("Running with mock data. Set GEMINI_API_KEY or GROQ_API_KEY for real LLM.", icon="ℹ️")
            else:
                st.markdown(f"**Provider:** `{provider}`")
                st.markdown(f"**Model:** `{model}`")
        except Exception as e:
            st.markdown("**Status:** 🔴 Backend offline")
            st.error(f"Cannot connect: {e}")

        st.divider()

        # Project selector
        st.markdown("### 📁 Project")
        project_id = ss("project_id")
        if project_id:
            st.markdown(f"**Active project:** `#{project_id}`")
        else:
            st.markdown("*No project selected*")

        if st.button("➕ New Project"):
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

        st.divider()
        st.caption("⚠️ Free-tier LLM providers may use submitted data. Do not submit confidential information.")
        st.caption("💾 Data is ephemeral on cloud — resets on restart.")


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------

STAGES = ["Parse", "Analyze", "Clarify", "Generate", "Verify"]

def render_progress(stage: str):
    stage_map = {"input": -1, "parse": 0, "analyze": 1, "clarify": 2, "generate": 3, "verify": 4}
    current = stage_map.get(stage, -1)

    html = '<div class="step-bar">'
    for i, s in enumerate(STAGES):
        cls = "done" if i < current else ("active" if i == current else "step")
        html += f'<div class="step {cls}">{("✓ " if i < current else "") + s}</div>'
        if i < len(STAGES) - 1:
            html += '<span style="color:#334155">→</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab 1: Requirements
# ---------------------------------------------------------------------------

def tab_requirements():
    st.markdown("## 📋 Requirements Input")

    project_id = ss("project_id")
    if not project_id:
        st.warning("👈 Create a new project from the sidebar first.")
        return

    render_progress(ss("pipeline_stage", "input"))

    # Sample loader
    sample_choice = st.selectbox("Load a sample:", list(SAMPLE_TEXTS.keys()))
    if sample_choice != "-- Select a sample --" and SAMPLE_TEXTS[sample_choice]:
        if st.button("Load Sample"):
            set_ss("req_text", SAMPLE_TEXTS[sample_choice])

    req_text = st.text_area(
        "Paste your product requirements here:",
        value=ss("req_text", ""),
        height=300,
        max_chars=8000,
        placeholder="Enter requirements in plain English...",
        key="req_text_input",
    )
    char_count = len(req_text)
    st.caption(f"{char_count}/8000 characters")

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🚀 Parse & Analyze"):
            if not req_text.strip():
                st.error("Please enter requirements first.")
                return
            set_ss("req_text", req_text)

            client = get_client()
            with st.spinner("Parsing requirements..."):
                try:
                    parse_result = client.submit_requirements(project_id, req_text)
                    st.success(f"✅ Parsed {parse_result['requirement_count']} requirements")
                    set_ss("req_ids", parse_result["req_ids"])
                    set_ss("pipeline_stage", "analyze")
                except Exception as e:
                    st.error(f"Parse error: {e}")
                    return

            with st.spinner("Analyzing for issues..."):
                try:
                    analyze_result = client.analyze(project_id)
                    issues = analyze_result.get("issues", [])
                    set_ss("issues", issues)
                    blocking = analyze_result.get("blocking_count", 0)
                    llm_warn = analyze_result.get("llm_warning")
                    if llm_warn:
                        st.warning(f"⚠️ {llm_warn}")
                    if blocking > 0:
                        st.warning(f"⚠️ Found {len(issues)} issue(s), {blocking} blocking — resolve in Issues tab.")
                        set_ss("pipeline_stage", "clarify")
                    else:
                        st.success(f"✅ Analysis done — {len(issues)} warnings only.")
                        set_ss("pipeline_stage", "generate")
                    st.rerun()
                except Exception as e:
                    st.error(f"Analysis error: {e}")

    # Show parsed requirements
    req_ids = ss("req_ids", [])
    if req_ids:
        with st.expander(f"📌 {len(req_ids)} Parsed Requirements", expanded=False):
            for rid in req_ids:
                st.markdown(f"- `{rid}`")


# ---------------------------------------------------------------------------
# Tab 2: Issues & Clarification
# ---------------------------------------------------------------------------

def _issue_badge(severity: str, issue_type: str) -> str:
    sev_cls = f"badge-{severity.lower()}"
    type_cls = f"badge-{issue_type.lower()}"
    return (
        f'<span class="badge {sev_cls}">{severity.upper()}</span>'
        f'<span class="badge {type_cls}">{issue_type.upper()}</span>'
    )


def tab_issues():
    st.markdown("## 🔍 Issues & Clarification")

    project_id = ss("project_id")
    if not project_id:
        st.warning("Create a project first.")
        return

    # Refresh issues
    client = get_client()
    try:
        issues = client.get_issues(project_id)
        set_ss("issues", issues)
    except Exception as e:
        st.error(f"Could not load issues: {e}")
        issues = ss("issues", [])

    if not issues:
        if ss("pipeline_stage") in ("clarify", "generate"):
            st.success("✅ No issues detected. Your requirements passed the current analysis checks.")
        else:
            st.info("No analysis results yet. Parse and analyze requirements first.")
        return

    # Summary counts
    blocking = [i for i in issues if i["severity"] == "blocking" and i["status"] == "open"]
    warnings = [i for i in issues if i["severity"] == "warning" and i["status"] == "open"]
    resolved = [i for i in issues if i["status"] in ("answered", "assumed")]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Blocking (open)", len(blocking))
    c2.metric("🟡 Warnings (open)", len(warnings))
    c3.metric("✅ Resolved", len(resolved))
    c4.metric("📊 Total", len(issues))

    if blocking:
        st.error(f"🚫 {len(blocking)} blocking issue(s) must be resolved before generating specs.")
    elif not any(i["status"] == "open" for i in issues):
        st.success("✅ All issues resolved! You can now generate artifacts.")

    st.divider()

    # Filter
    show_filter = st.selectbox("Show:", ["All", "Blocking", "Warnings", "Resolved"])

    def show_issue(i: dict) -> bool:
        if show_filter == "All": return True
        if show_filter == "Blocking": return i["severity"] == "blocking"
        if show_filter == "Warnings": return i["severity"] == "warning"
        if show_filter == "Resolved": return i["status"] in ("answered", "assumed")
        return True

    for iss in issues:
        if not show_issue(iss):
            continue

        status = iss.get("status", "open")
        severity = iss.get("severity", "warning")
        issue_type = iss.get("issue_type", "ambiguity")
        card_cls = status if status != "open" else severity

        badge_html = _issue_badge(severity, issue_type)
        status_icon = {"open": "🔓", "answered": "✅", "assumed": "💭"}.get(status, "")

        with st.container():
            st.markdown(f"""
            <div class="card {card_cls}">
              <strong>{status_icon} {iss['issue_id']}</strong> &nbsp; {badge_html}
              <p style="margin:8px 0 4px 0; color:#cbd5e1">{iss['description']}</p>
              <p style="margin:0; color:#94a3b8; font-size:0.85em">
                <em>Involves: {', '.join(iss.get('involved_req_ids', []))}</em>
              </p>
            </div>
            """, unsafe_allow_html=True)

            if status == "open":
                st.markdown(f"**Question:** *{iss['suggested_question']}*")
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    ans = st.text_input(
                        "Your answer:",
                        key=f"ans_{iss['issue_id']}",
                        placeholder="Type your answer here...",
                        label_visibility="collapsed",
                    )
                with col_b:
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("Submit", key=f"submit_{iss['issue_id']}"):
                            if ans.strip():
                                try:
                                    client.answer_issue(project_id, iss["issue_id"], ans)
                                    st.success("Answered!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(str(e))
                            else:
                                st.warning("Enter an answer first.")
                    with b2:
                        if st.button("Assume default", key=f"assume_{iss['issue_id']}"):
                            try:
                                client.assume_issue(project_id, iss["issue_id"])
                                st.info("Default assumed.")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
            elif status == "answered":
                st.markdown(f"✅ **Answer:** {iss.get('answer', '')}")
            elif status == "assumed":
                st.markdown(f"💭 **Assumption:** {iss.get('assumption', 'default behavior assumed')}")

    st.divider()

    # Re-analyze button
    if any(i["status"] != "open" for i in issues):
        col1, _ = st.columns([1, 3])
        with col1:
            if st.button("🔄 Re-analyze after answers"):
                with st.spinner("Re-analyzing..."):
                    try:
                        result = client.analyze(project_id)
                        set_ss("issues", result.get("issues", []))
                        st.success(f"Re-analysis complete: {result.get('blocking_count', 0)} blocking issues remaining.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    # Generate button (when no blocking)
    open_blocking = [i for i in issues if i["severity"] == "blocking" and i["status"] == "open"]
    if not open_blocking:
        col1, _ = st.columns([1, 3])
        with col1:
            if st.button("⚙️ Generate Specifications →"):
                with st.spinner("Generating OpenAPI, SQL, and Test Plan..."):
                    try:
                        result = client.generate(project_id)
                        set_ss("artifacts", result.get("artifacts", []))
                        set_ss("pipeline_stage", "verify")
                        st.success(f"✅ Generated {result.get('artifacts_generated', 0)} artifacts!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Generation error: {e}")


# ---------------------------------------------------------------------------
# Tab 3: Specs
# ---------------------------------------------------------------------------

def tab_specs():
    st.markdown("## 📄 Generated Specifications")

    project_id = ss("project_id")
    if not project_id:
        st.warning("Create a project first.")
        return

    client = get_client()
    try:
        artifacts = client.get_artifacts(project_id)
    except Exception as e:
        st.error(f"Cannot load artifacts: {e}")
        artifacts = []

    if not artifacts:
        st.info("No artifacts yet. Complete the Issues tab and generate specs.")
        return

    render_progress("verify")

    for art in artifacts:
        art_type = art.get("artifact_type", "")
        is_valid = art.get("is_valid", False)
        errors = art.get("validation_errors", [])
        content = art.get("content", "")

        icons = {"openapi": "🔌", "sql_ddl": "🗄️", "test_plan": "🧪"}
        titles = {"openapi": "OpenAPI 3 Specification", "sql_ddl": "SQL DDL Schema", "test_plan": "Test Plan"}

        st.markdown(f"### {icons.get(art_type, '📄')} {titles.get(art_type, art_type)}")

        # Validation badge
        if is_valid:
            st.markdown('<span class="badge badge-ok">✓ VALID</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge badge-error">✗ INVALID</span>', unsafe_allow_html=True)
            for err in errors:
                st.error(f"Validation error: {err}")

        # Content display
        lang = {"openapi": "yaml", "sql_ddl": "sql", "test_plan": "json"}.get(art_type, "text")
        st.code(content, language=lang)

        # Download button
        ext = {"openapi": "yaml", "sql_ddl": "sql", "test_plan": "json"}.get(art_type, "txt")
        fname = {"openapi": "openapi.yaml", "sql_ddl": "schema.sql", "test_plan": "test_plan.json"}.get(art_type, "artifact.txt")
        st.download_button(
            f"⬇️ Download {fname}",
            data=content,
            file_name=fname,
            mime="text/plain",
        )
        st.divider()

    # Download all
    export_url = client.export_url(project_id)
    st.markdown(f"📦 [Download all as ZIP]({export_url})")


# ---------------------------------------------------------------------------
# Tab 4: Traceability
# ---------------------------------------------------------------------------

def tab_traceability():
    st.markdown("## 🔗 Traceability")

    project_id = ss("project_id")
    if not project_id:
        st.warning("Create a project first.")
        return

    client = get_client()
    try:
        trace = client.get_traceability(project_id)
    except Exception as e:
        st.error(f"Cannot load traceability: {e}")
        return

    links = trace.get("links", [])
    if not links:
        st.info("No traceability data yet. Generate specs first.")
        return

    # Coverage
    coverage = trace.get("coverage_pct", 0)
    uncovered = trace.get("uncovered_req_ids", [])

    col1, col2 = st.columns(2)
    col1.metric("📊 Test Coverage", f"{coverage:.1f}%")
    col2.metric("⚠️ Uncovered REQs", len(uncovered))

    if uncovered:
        st.warning(f"Uncovered requirements: {', '.join(uncovered)}")

    # Matrix
    st.markdown("### 📋 Traceability Matrix")
    import pandas as pd

    rows = []
    for link in links:
        rows.append({
            "Requirement": link["req_id"],
            "Artifact Type": link["artifact_type"],
            "Item": link["item_id"],
            "Label": link["item_label"],
        })
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

    # Interactive graph with pyvis
    st.markdown("### 🕸️ Dependency Graph")
    try:
        import networkx as nx
        from pyvis.network import Network
        import tempfile, os

        G = nx.DiGraph()
        colors = {"openapi": "#3b82f6", "sql_ddl": "#22c55e", "test_plan": "#f59e0b"}

        req_nodes = set()
        for link in links:
            req_node = link["req_id"]
            item_node = f"{link['artifact_type']}::{link['item_id']}"
            G.add_node(req_node, color="#ef4444", title=req_node, label=req_node)
            G.add_node(item_node, color=colors.get(link["artifact_type"], "#94a3b8"),
                       title=link["item_label"], label=link["item_id"][:30])
            G.add_edge(req_node, item_node)
            req_nodes.add(req_node)

        net = Network(height="450px", width="100%", bgcolor="#0d1b2a", font_color="#e0e8f0", directed=True)
        net.from_nx(G)
        net.set_options("""
        {
          "physics": {"solver": "repulsion", "repulsion": {"nodeDistance": 120}},
          "nodes": {"font": {"size": 13}},
          "edges": {"arrows": {"to": {"enabled": true}}}
        }
        """)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, dir="./data") as f:
            net.save_graph(f.name)
            html_content = open(f.name, encoding="utf-8").read()
            os.unlink(f.name)

        st.components.v1.html(html_content, height=470, scrolling=False)
    except ImportError:
        st.info("Install networkx and pyvis for interactive graph visualization.")
    except Exception as e:
        st.warning(f"Graph render error: {e}")

    # Decision Log
    decision_log = trace.get("decision_log", [])
    if decision_log:
        st.markdown("### 📝 Decision Log")
        for entry in decision_log:
            with st.expander(f"🗒️ {entry['issue_id']} — {entry['resolved_at'][:10]}"):
                st.markdown(f"**Question:** {entry['question']}")
                if entry.get("answer"):
                    st.markdown(f"**Answer:** {entry['answer']}")
                if entry.get("assumption"):
                    st.markdown(f"**Assumption:** {entry['assumption']}")


# ---------------------------------------------------------------------------
# Tab 5: Evaluation
# ---------------------------------------------------------------------------

def tab_evaluation():
    st.markdown("## 📊 Evaluation")
    st.markdown("Run the evaluation suite on all sample inputs with planted flaws.")

    client = get_client()

    # Try to load cached report
    try:
        with open("eval/eval_report.json", encoding="utf-8") as f:
            report = json.load(f)
        st.success("📋 Cached evaluation report loaded.")
        _render_eval_report(report)
    except FileNotFoundError:
        st.info("No evaluation report found. Run evaluation below.")
    except Exception as e:
        st.warning(f"Could not parse report: {e}")

    col1, _ = st.columns([1, 3])
    with col1:
        if st.button("▶️ Run Evaluation Now"):
            with st.spinner("Running evaluation (this may take a minute)..."):
                try:
                    report = client.evaluate()
                    if report.get("status") == "error":
                        st.error(f"Evaluation failed: {report.get('error')}")
                    else:
                        _render_eval_report(report)
                        st.success("Evaluation complete!")
                except Exception as e:
                    st.error(f"Error: {e}")


def _render_eval_report(report: dict):
    import plotly.graph_objects as go

    per_type = report.get("per_type", {})
    overall = report.get("overall", {})

    # Overall metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("OpenAPI Valid Rate", f"{overall.get('openapi_valid_rate', 0)*100:.1f}%")
    c2.metric("SQL Exec Rate", f"{overall.get('sql_exec_rate', 0)*100:.1f}%")
    c3.metric("Test Coverage", f"{overall.get('test_coverage_pct', 0):.1f}%")

    # Per-type metrics chart
    if per_type:
        types = list(per_type.keys())
        prec = [per_type[t].get("precision", 0) for t in types]
        rec = [per_type[t].get("recall", 0) for t in types]
        f1 = [per_type[t].get("f1", 0) for t in types]

        fig = go.Figure(data=[
            go.Bar(name="Precision", x=types, y=prec, marker_color="#3b82f6"),
            go.Bar(name="Recall", x=types, y=rec, marker_color="#22c55e"),
            go.Bar(name="F1", x=types, y=f1, marker_color="#f59e0b"),
        ])
        fig.update_layout(
            barmode="group",
            title="Detection Precision / Recall / F1 by Issue Type",
            paper_bgcolor="#0d1b2a",
            plot_bgcolor="#0d1b2a",
            font_color="#e0e8f0",
            legend=dict(bgcolor="#152236"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Raw report expander
    with st.expander("📄 Raw Report JSON"):
        st.json(report)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    render_sidebar()

    project_id = ss("project_id")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Requirements",
        "🔍 Issues",
        "📄 Specs",
        "🔗 Traceability",
        "📊 Evaluation",
    ])

    with tab1:
        tab_requirements()
    with tab2:
        tab_issues()
    with tab3:
        tab_specs()
    with tab4:
        tab_traceability()
    with tab5:
        tab_evaluation()

