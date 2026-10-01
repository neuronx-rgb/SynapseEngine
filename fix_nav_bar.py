import re

with open("streamlit_app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace st.navigation with explicit page links
nav_code = """
# Manual Top Navigation
nav1, nav2, nav3, nav4, nav5, nav6 = st.columns(6)
with nav1: st.page_link("frontend/views/home.py", label="Home", icon="🏠")
with nav2: st.page_link("frontend/views/requirements.py", label="Requirements", icon="📋")
with nav3: st.page_link("frontend/views/issues.py", label="Issues", icon="⚠️")
with nav4: st.page_link("frontend/views/specs.py", label="Specs", icon="💻")
with nav5: st.page_link("frontend/views/traceability.py", label="Traceability", icon="🔗")
with nav6: st.page_link("frontend/views/evaluation.py", label="Evaluation", icon="📊")

st.markdown("<hr style='margin-top: 0; margin-bottom: 2rem; opacity: 0.2;'>", unsafe_allow_html=True)

# Run the selected page natively
# Streamlit >= 1.31 uses st.navigation, but since we are doing manual routing with page_link
# we actually just need to use st.navigation with a hidden sidebar if we want native routing,
# OR we can just define the pages and hide the sidebar.
pg = st.navigation(
    [
        st.Page("frontend/views/home.py", title="Home", icon=":material/home:"),
        st.Page("frontend/views/requirements.py", title="Requirements", icon=":material/list:"),
        st.Page("frontend/views/issues.py", title="Issues", icon=":material/report:"),
        st.Page("frontend/views/specs.py", title="Specs", icon=":material/code:"),
        st.Page("frontend/views/traceability.py", title="Traceability", icon=":material/account_tree:"),
        st.Page("frontend/views/evaluation.py", title="Evaluation", icon=":material/assessment:"),
    ],
    position="sidebar"
)
pg.run()
"""

# Find pg = st.navigation... pg.run() and replace it
# Wait, if I use position="sidebar" and hide the sidebar with CSS, the user relies purely on st.page_link!
# That is foolproof.

# Let's replace the existing st.navigation block
content = re.sub(r'pg = st\.navigation\([^)]+\)\n\npg\.run\(\)', nav_code.strip(), content, flags=re.DOTALL)

with open("streamlit_app.py", "w", encoding="utf-8") as f:
    f.write(content)
