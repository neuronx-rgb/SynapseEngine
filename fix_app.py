import os

with open("streamlit_app.py", "rb") as f:
    content = f.read()

idx = 4328
part1 = content[:idx].decode("utf-8")

footer = """
st.markdown('''
    <div style="text-align: center; color: var(--text-color); font-size: 0.85em; opacity: 0.7; padding: 20px 0;">
        <p>Synapse Engine • Data is ephemeral on cloud • Free-tier LLMs may use submitted data.</p>
        <p>Uses Cornelius FR NFR Curated Dataset</p>
    </div>
''', unsafe_allow_html=True)
"""

with open("streamlit_app.py", "w", encoding="utf-8") as f:
    f.write(part1 + footer)

print("Fixed streamlit_app.py encoding!")
