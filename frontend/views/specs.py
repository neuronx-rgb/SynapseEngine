import streamlit as st
from frontend.utils import ss, get_client, render_progress

st.markdown("## 📄 Generated Specifications")

project_id = ss("project_id")
if not project_id:
    st.warning("Create a project first.")
    st.stop()

client = get_client()
try:
    artifacts = client.get_artifacts(project_id)
except Exception as e:
    st.error(f"Cannot load artifacts: {e}")
    artifacts = []

if not artifacts:
    st.info("No artifacts yet. Complete the Issues tab and generate specs.")
    st.stop()

render_progress("verify")

for art in artifacts:
    art_type = art.get("artifact_type", "")
    is_valid = art.get("is_valid", False)
    errors = art.get("validation_errors", [])
    content = art.get("content", "")

    icons = {"openapi": "🔌", "sql_ddl": "🗄️", "test_plan": "🧪"}
    titles = {"openapi": "OpenAPI 3 Specification", "sql_ddl": "SQL DDL Schema", "test_plan": "Test Plan"}

    st.markdown(f"### {icons.get(art_type, '📄')} {titles.get(art_type, art_type)}")

    if is_valid:
        st.markdown('<span class="badge badge-ok">✓ VALID</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-error">✗ INVALID</span>', unsafe_allow_html=True)
        for err in errors:
            st.error(f"Validation error: {err}")

    lang = {"openapi": "yaml", "sql_ddl": "sql", "test_plan": "json"}.get(art_type, "text")
    st.code(content, language=lang)

    ext = {"openapi": "yaml", "sql_ddl": "sql", "test_plan": "json"}.get(art_type, "txt")
    fname = {"openapi": "openapi.yaml", "sql_ddl": "schema.sql", "test_plan": "test_plan.json"}.get(art_type, "artifact.txt")
    st.download_button(
        f"⬇️ Download {fname}",
        data=content,
        file_name=fname,
        mime="text/plain",
    )
    st.divider()

export_url = client.export_url(project_id)
st.markdown(f"📦 [Download all as ZIP]({export_url})")
