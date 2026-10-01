import re

with open("frontend/theme.py", "r", encoding="utf-8") as f:
    content = f.read()

# Remove sidebar hiding CSS
content = re.sub(r'/\* Hide sidebar and toggle \*/\s*\[data-testid="stSidebar"\].*?display: none !important;\s*\}', '', content, flags=re.DOTALL)

with open("frontend/theme.py", "w", encoding="utf-8") as f:
    f.write(content)
