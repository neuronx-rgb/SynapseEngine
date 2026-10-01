import re

with open('streamlit_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_nav = '''
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
'''

content = re.sub(r'pg = st\.navigation\(.*?\n\)', new_nav.strip(), content, flags=re.DOTALL)

with open('streamlit_app.py', 'w', encoding='utf-8') as f:
    f.write(content)
