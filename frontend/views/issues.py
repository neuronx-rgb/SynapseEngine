import streamlit as st
from frontend.utils import ss, set_ss, get_client, render_progress

st.markdown("## 🔍 Issues & Clarification")

project_id = ss("project_id")
if not project_id:
    st.warning("Create a project first.")
    st.stop()

render_progress(ss("pipeline_stage", "clarify"))

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
    st.stop()

def _issue_badge(severity: str, issue_type: str) -> str:
    # We will use inline styles instead of classes for simpler CSS injection, or keep classes if we inject theme CSS globally.
    # We kept the global CSS in theme.py or similar, but wait, the global css has classes like card, badge-blocking. Let's just use the classes since we'll include them.
    sev_cls = f"badge-{severity.lower()}"
    type_cls = f"badge-{issue_type.lower()}"
    return (
        f'<span class="badge {sev_cls}">{severity.upper()}</span>'
        f'<span class="badge {type_cls}">{issue_type.upper()}</span>'
    )

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
                    st.switch_page("frontend/views/specs.py")
                except Exception as e:
                    st.error(f"Generation error: {e}")
