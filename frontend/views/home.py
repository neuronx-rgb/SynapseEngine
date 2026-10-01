import streamlit as st
import time
from frontend.utils import ss, set_ss, get_client
from frontend.components.hero import render_hero

def render():
    col1, col2 = st.columns([5, 7], gap="large")

    with col1:
        st.markdown("<p style='font-size: 0.85em; font-weight: 600; letter-spacing: 1px; color: var(--primary-color);'>LLM SPECIFICATION COMPILER</p>", unsafe_allow_html=True)
        st.markdown("<h1 style='line-height: 1.1; margin-bottom: 20px;'>Compile requirements, not regrets.</h1>", unsafe_allow_html=True)
        st.markdown(
            "<p style='opacity: 0.8; margin-bottom: 30px; font-size: 1.1em; line-height: 1.5;'>Synapse Engine transforms plain English requirements into rigorous technical specifications, exposing hidden assumptions before you build.</p>", 
            unsafe_allow_html=True
        )
        
        c_btn1, c_btn2 = st.columns([1, 1])
        with c_btn1:
            if st.button("Start compiling", type="primary", use_container_width=True):
                client = get_client()
                name = f"Project-{int(time.time())}"
                proj = client.create_project(name=name)
                set_ss("project_id", proj["id"])
                set_ss("pipeline_stage", "input")
                st.switch_page("frontend/views/requirements.py")
        with c_btn2:
            st.button("See how it works", use_container_width=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("✔️ **Z3-proven conflicts**<br>✔️ **Zero silent assumptions**<br>✔️ **Traceable end to end**", unsafe_allow_html=True)

    with col2:
        render_hero()

    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("### How it works")
    
    st.markdown("""
    <div style='display: flex; justify-content: space-between; border: 1px solid rgba(255,255,255,0.08); padding: 15px; border-radius: 12px; background: rgba(255,255,255,0.02);'>
        <div><strong>1. Parse</strong><br><span style='opacity:0.6; font-size:0.8em;'>Extract entities & actions</span></div>
        <div><strong>2. Analyze</strong><br><span style='opacity:0.6; font-size:0.8em;'>Detect logical conflicts</span></div>
        <div><strong>3. Clarify</strong><br><span style='opacity:0.6; font-size:0.8em;'>Resolve ambiguities</span></div>
        <div><strong>4. Generate</strong><br><span style='opacity:0.6; font-size:0.8em;'>Build OpenAPI & SQL</span></div>
        <div><strong>5. Verify</strong><br><span style='opacity:0.6; font-size:0.8em;'>Traceability & Tests</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    c_det1, c_det2, c_det3 = st.columns(3)
    with c_det1:
        st.markdown("<div style='border: 1px solid rgba(255,255,255,0.08); padding: 20px; border-radius: 14px;'><h4>Ambiguity</h4><p style='opacity:0.7; font-size:0.9em;'>Identifies vague pronouns and 'as needed' clauses.</p><p style='color:var(--primary-color); font-size:0.8em; margin-bottom:0;'>OUTPUT: Clarifying questions</p></div>", unsafe_allow_html=True)
    with c_det2:
        st.markdown("<div style='border: 1px solid rgba(255,255,255,0.08); padding: 20px; border-radius: 14px;'><h4>Conflict</h4><p style='opacity:0.7; font-size:0.9em;'>Uses Z3 theorem proving to catch mutually exclusive rules.</p><p style='color:var(--primary-color); font-size:0.8em; margin-bottom:0;'>OUTPUT: Blocking exceptions</p></div>", unsafe_allow_html=True)
    with c_det3:
        st.markdown("<div style='border: 1px solid rgba(255,255,255,0.08); padding: 20px; border-radius: 14px;'><h4>Completeness</h4><p style='opacity:0.7; font-size:0.9em;'>Flags missing edge cases and unhandled error states.</p><p style='color:var(--primary-color); font-size:0.8em; margin-bottom:0;'>OUTPUT: Completeness warnings</p></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.error("Compiler error demo: E0412 Mutually Exclusive Constraints\n\nREQ-001 [UNIQUE email] vs REQ-084 [SHARED email]\n\nBUILD HALTED", icon=":material/gpp_bad:")

render()
