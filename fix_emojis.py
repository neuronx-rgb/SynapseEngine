import re

files = [
    "frontend/views/requirements.py",
    "frontend/views/issues.py",
    "frontend/views/specs.py",
    "frontend/views/traceability.py",
    "frontend/views/evaluation.py",
]

for file in files:
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace common unicode corruption patterns the agent introduced
        content = content.replace('dY"<', '📋')
        content = content.replace('dY`^', '⚠️')
        content = content.replace('dYs?', '🚀')
        content = content.replace('o.', '✅')
        content = content.replace('s,?', '⚠️')
        content = content.replace('dY"O', '📌')
        
        with open(file, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass
