import re

with open("frontend/components/hero.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('object-fit: cover;', 'object-fit: contain;')

with open("frontend/components/hero.py", "w", encoding="utf-8") as f:
    f.write(content)
