import re

with open("streamlit_app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Extract the st.set_page_config block
page_config_match = re.search(r'st\.set_page_config\([^)]+\)\n', content, flags=re.DOTALL)
if page_config_match:
    page_config_str = page_config_match.group(0)
    # Remove it from the current location
    content = content.replace(page_config_str, '')
    
    # Insert it right after `import streamlit as st`
    insert_target = 'import streamlit as st\n'
    content = content.replace(insert_target, insert_target + '\n' + page_config_str)

with open("streamlit_app.py", "w", encoding="utf-8") as f:
    f.write(content)
