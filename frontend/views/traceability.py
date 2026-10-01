import streamlit as st
import pandas as pd
from frontend.utils import ss, get_client

st.markdown("## 🔗 Traceability")

project_id = ss("project_id")
if not project_id:
    st.warning("Create a project first.")
    st.stop()

client = get_client()
try:
    trace = client.get_traceability(project_id)
except Exception as e:
    st.error(f"Cannot load traceability: {e}")
    st.stop()

links = trace.get("links", [])
if not links:
    st.info("No traceability data yet. Generate specs first.")
    st.stop()

coverage = trace.get("coverage_pct", 0)
uncovered = trace.get("uncovered_req_ids", [])

col1, col2 = st.columns(2)
col1.metric("📊 Test Coverage", f"{coverage:.1f}%")
col2.metric("⚠️ Uncovered REQs", len(uncovered))

if uncovered:
    st.warning(f"Uncovered requirements: {', '.join(uncovered)}")

st.markdown("### 📋 Traceability Matrix")
rows = []
for link in links:
    rows.append({
        "Requirement": link["req_id"],
        "Artifact Type": link["artifact_type"],
        "Item": link["item_id"],
        "Label": link["item_label"],
    })
if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

st.markdown("### 🕸️ Dependency Graph")
try:
    import networkx as nx
    from pyvis.network import Network
    import tempfile, os

    G = nx.DiGraph()
    colors = {"openapi": "#3b82f6", "sql_ddl": "#22c55e", "test_plan": "#f59e0b"}

    req_nodes = set()
    for link in links:
        req_node = link["req_id"]
        item_node = f"{link['artifact_type']}::{link['item_id']}"
        G.add_node(req_node, color="#ef4444", title=req_node, label=req_node)
        G.add_node(item_node, color=colors.get(link["artifact_type"], "#94a3b8"),
                   title=link["item_label"], label=link["item_id"][:30])
        G.add_edge(req_node, item_node)
        req_nodes.add(req_node)

    net = Network(height="450px", width="100%", bgcolor="#0d1b2a", font_color="#e0e8f0", directed=True)
    net.from_nx(G)
    net.set_options("""
    {
      "physics": {"solver": "repulsion", "repulsion": {"nodeDistance": 120}},
      "nodes": {"font": {"size": 13}},
      "edges": {"arrows": {"to": {"enabled": true}}}
    }
    """)
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, dir="./data") as f:
        net.save_graph(f.name)
        html_content = open(f.name, encoding="utf-8").read()
        os.unlink(f.name)

    st.components.v1.html(html_content, height=470, scrolling=False)
except ImportError:
    st.info("Install networkx and pyvis for interactive graph visualization.")
except Exception as e:
    st.warning(f"Graph render error: {e}")

decision_log = trace.get("decision_log", [])
if decision_log:
    st.markdown("### 📝 Decision Log")
    for entry in decision_log:
        with st.expander(f"🗒️ {entry['issue_id']} — {entry['resolved_at'][:10]}"):
            st.markdown(f"**Question:** {entry['question']}")
            if entry.get("answer"):
                st.markdown(f"**Answer:** {entry['answer']}")
            if entry.get("assumption"):
                st.markdown(f"**Assumption:** {entry['assumption']}")
