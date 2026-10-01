import re

with open("streamlit_app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Remove icons from st.page_link
content = re.sub(r'st\.page_link\("([^"]+)", label="([^"]+)", icon="[^"]+"\)', r'st.page_link("\1", label="\2")', content)

with open("streamlit_app.py", "w", encoding="utf-8") as f:
    f.write(content)
