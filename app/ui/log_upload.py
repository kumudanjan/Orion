import streamlit as st
import pandas as pd
from app.ingestion.parser import parse_uploaded_file, semantic_chunk
from app.ingestion.vector_store import get_vector_store
from app.observability.metrics import get_metrics, Timer


def render_log_upload():
    st.header("📥 Log Ingestion & Parsing")
    st.markdown(
        "Upload log files (plain text, JSON/NDJSON, Apache/Nginx, syslog, OpenTelemetry). "
        "Logs are auto-parsed, PII-scrubbed, chunked, and indexed into the vector store."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded = st.file_uploader(
            "Drop log file(s) here",
            type=["log", "txt", "json", "ndjson"],
            accept_multiple_files=True,
        )

    with col2:
        st.info(
            "**Supported formats**\n"
            "- Plain text / syslog\n"
            "- JSON / NDJSON\n"
            "- Apache Combined Log\n"
            "- OpenTelemetry JSON\n"
        )

    # Demo data option
    use_demo = st.checkbox("Use sample log data (demo mode)")
    if use_demo:
        from app.data.sample_logs import SAMPLE_LOG_BYTES
        uploaded_demo = [type("F", (), {"read": lambda s: SAMPLE_LOG_BYTES, "name": "sample_web_server.log"})()]
        uploaded = uploaded_demo  # type: ignore

    if not uploaded:
        st.info("Please upload a log file or enable demo mode.")
        return

    all_entries = []
    for f in uploaded:
        raw = f.read()
        if hasattr(raw, 'encode'):
            raw = raw.encode()
        with Timer("log_ingestion", source=f.name):
            entries = parse_uploaded_file(raw, f.name)
        all_entries.extend(entries)
        st.success(f"✅ Parsed **{len(entries)}** entries from `{f.name}`")

    if not all_entries:
        st.warning("No log entries parsed.")
        return

    # Store in session
    st.session_state["log_entries"] = all_entries

    # Show parsed entries table
    st.subheader(f"Parsed Entries — {len(all_entries):,} total")
    df = pd.DataFrame([e.to_dict() for e in all_entries[:500]])
    cols = ["line_no", "timestamp", "level", "service", "message"]
    display_cols = [c for c in cols if c in df.columns]

    level_colors = {"ERROR": "🔴", "CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🟢", "DEBUG": "⚪"}
    df["level_display"] = df["level"].map(lambda l: f"{level_colors.get(l, '⚪')} {l}")
    df.to_csv("parsed_log.csv")

    st.dataframe(
        df[display_cols].rename(columns={"level": "severity", "line_no": "line #"}),
        use_container_width=True,
        height=300,
    )

    # Level distribution
    st.subheader("Level Distribution")
    level_counts = df["level"].value_counts().reset_index()
    level_counts.columns = ["Level", "Count"]
    st.bar_chart(level_counts.set_index("Level"))

    # Ingest into vector store
    st.subheader("🗄️ Vector Store Indexing")
    if st.button("Index logs into Vector Store", type="primary"):
        with st.spinner("Chunking and embedding..."):
            with Timer("vector_indexing"):
                chunks = semantic_chunk(all_entries)
                store = get_vector_store()
                n = store.upsert(chunks, collection="logs")
                get_metrics().record("chunks_indexed", n)
        st.success(f"✅ Indexed **{n}** semantic chunks. Ready for RAG & anomaly detection.")
        st.session_state["indexed"] = True
