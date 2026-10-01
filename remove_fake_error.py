import re

with open("frontend/views/home.py", "r", encoding="utf-8") as f:
    content = f.read()

# Remove the fake compiler error
content = re.sub(r'st\.error\("Compiler error demo.*?"\)', '', content, flags=re.DOTALL)

with open("frontend/views/home.py", "w", encoding="utf-8") as f:
    f.write(content)
