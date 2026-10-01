import streamlit as st
import json
from frontend.api_client import get_client

st.markdown("## 📊 Evaluation")
st.markdown("Run the evaluation suite on all sample inputs with planted flaws.")

client = get_client()

def _render_eval_report(report: dict):
    import plotly.graph_objects as go

    per_type = report.get("per_type", {})
    overall = report.get("overall", {})

    c1, c2, c3 = st.columns(3)
    c1.metric("OpenAPI Valid Rate", f"{overall.get('openapi_valid_rate', 0)*100:.1f}%")
    c2.metric("SQL Exec Rate", f"{overall.get('sql_exec_rate', 0)*100:.1f}%")
    c3.metric("Test Coverage", f"{overall.get('test_coverage_pct', 0):.1f}%")

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

    with st.expander("📄 Raw Report JSON"):
        st.json(report)

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
