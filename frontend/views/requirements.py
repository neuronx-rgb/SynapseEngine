import streamlit as st
from frontend.utils import ss, set_ss, SAMPLE_TEXTS, get_client, render_progress

st.markdown("## 📋 Requirements Input")

project_id = ss("project_id")
if not project_id:
    st.warning("👈 Create a new project first.")
    st.stop()

render_progress(ss("pipeline_stage", "input"))

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
            st.stop()
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
                st.stop()

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

req_ids = ss("req_ids", [])
if req_ids:
    with st.expander(f"📌 {len(req_ids)} Parsed Requirements", expanded=False):
        for rid in req_ids:
            st.markdown(f"- `{rid}`")
