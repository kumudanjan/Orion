"""
PROJECT 4 — Log Intelligence Assistant
Main Streamlit Application Entry Point
"""

import sys
import os

# ── Path fix ──────────────────────────────────────────────────────────────
# Ensure the project root (the folder containing 'app/') is on sys.path
# regardless of how / from where Streamlit is launched.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
# ─────────────────────────────────────────────────────────────────────────

import streamlit as st

st.set_page_config(
    page_title="Log Intelligence Assistant",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.ui.sidebar import render_sidebar
from app.ui.log_upload import render_log_upload
from app.ui.anomaly_view import render_anomaly_view
from app.ui.rca_view import render_rca_view
from app.ui.rag_view import render_rag_view
from app.ui.observability import render_observability

def main():
    st.title("🔍 Log Intelligence Assistant")
    st.markdown(
        "_GenAI-powered log analysis: ingest, detect anomalies, and get plain-language root-cause analysis._"
    )

    page = render_sidebar()

    if page == "Log Ingestion":
        render_log_upload()
    elif page == "Anomaly Detection":
        render_anomaly_view()
    elif page == "RCA Agent":
        render_rca_view()
    elif page == "RAG / Knowledge Base":
        render_rag_view()
    elif page == "Observability":
        render_observability()

if __name__ == "__main__":
    main()
