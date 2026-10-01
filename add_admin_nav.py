import re

with open("streamlit_app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add admin page to st.navigation list
nav_addition = """st.Page("frontend/views/evaluation.py", title="Evaluation", icon=":material/assessment:"),
        st.Page("frontend/views/admin.py", title="Admin", icon=":material/lock:"),"""
content = content.replace('st.Page("frontend/views/evaluation.py", title="Evaluation", icon=":material/assessment:"),', nav_addition)

# Add admin column to Custom Guaranteed Horizontal Navigation Bar
# Find this exact line: col_logo, col1, col2, col3, col4, col5, col6, _ = st.columns([2, 2, 2, 2, 2, 2, 2, 1])
# Replace with: col_logo, col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5])
# And add col7 block

new_cols_code = """    col_logo, col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5])
    with col_logo:
        st.markdown("**⚡ Synapse Eng**")
    with col1:
        st.page_link("frontend/views/home.py", label="Home")
    with col2:
        st.page_link("frontend/views/requirements.py", label="Requirements")
    with col3:
        st.page_link("frontend/views/issues.py", label="Issues")
    with col4:
        st.page_link("frontend/views/specs.py", label="Specs")
    with col5:
        st.page_link("frontend/views/traceability.py", label="Traceability")
    with col6:
        st.page_link("frontend/views/evaluation.py", label="Evaluation")
    with col7:
        st.page_link("frontend/views/admin.py", label="Admin")"""

# Need to replace the whole col block
pattern = r"col_logo, col1, col2, col3, col4, col5, col6, _ = st\.columns.+?with col6:\n\s+st\.page_link\(\"frontend/views/evaluation\.py\", label=\"Evaluation\"\)"
content = re.sub(pattern, new_cols_code.strip(), content, flags=re.DOTALL)

with open("streamlit_app.py", "w", encoding="utf-8") as f:
    f.write(content)
