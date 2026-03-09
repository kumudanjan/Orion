import streamlit as st
import pandas as pd
from app.anomaly.detector import run_anomaly_detection, AnomalyResult
from app.observability.metrics import get_metrics, Timer

SEVERITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
SEVERITY_COLOR = {"critical": "#FF4444", "high": "#FF8C00", "medium": "#FFD700", "low": "#32CD32"}


def render_anomaly_view():
    st.header("🚨 Anomaly Detection")
    st.markdown(
        "Two-layer detection: **statistical Z-score** on error-rate time series "
        "+ **LLM pattern matcher** for semantic anomalies."
    )

    entries = st.session_state.get("log_entries")
    if not entries:
        st.warning("No logs loaded. Please upload logs on the **Log Ingestion** page first.")
        return

    st.info(f"Working with **{len(entries):,}** log entries.")

    col1, col2 = st.columns(2)
    with col1:
        z_thresh = st.slider("Z-score threshold (statistical)", 1.5, 5.0, 2.5, 0.1)
    with col2:
        enable_llm = st.checkbox("Enable LLM pattern detection", value=True)

    if st.button("🔍 Run Anomaly Detection", type="primary"):
        with st.spinner("Analyzing logs..."):
            with Timer("anomaly_detection", entry_count=len(entries)):
                from app.anomaly.detector import statistical_anomaly_detection, llm_anomaly_detection
                results = statistical_anomaly_detection(entries, z_threshold=z_thresh)
                if enable_llm:
                    results += llm_anomaly_detection(entries)
                severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
                results.sort(key=lambda x: severity_order.get(x.severity, 99))

        st.session_state["anomalies"] = results
        get_metrics().record("anomalies_detected", len(results))
        st.success(f"Detection complete — **{len(results)}** anomalies found.")

    results: list[AnomalyResult] = st.session_state.get("anomalies", [])
    if not results:
        return

    # Summary metrics
    st.subheader("Summary")
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for r in results:
        counts[r.severity] = counts.get(r.severity, 0) + 1

    cols = st.columns(4)
    for col, (sev, cnt) in zip(cols, counts.items()):
        col.metric(f"{SEVERITY_ICON[sev]} {sev.title()}", cnt)

    # Anomaly cards
    st.subheader("Detected Anomalies")
    for r in results:
        icon = SEVERITY_ICON.get(r.severity, "⚪")
        with st.expander(f"{icon} [{r.severity.upper()}] {r.title} — {r.type}", expanded=r.severity in ("critical", "high")):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Description:** {r.description}")
                if r.timestamp:
                    st.markdown(f"**Timestamp:** `{r.timestamp}`")
                if r.affected_lines:
                    st.markdown(f"**Affected lines:** {r.affected_lines[:10]}")
            with col2:
                st.metric("Confidence", f"{r.confidence:.0%}")
                st.metric("Type", r.type.replace("_", " ").title())

            # Show sample affected entries
            if r.affected_entries:
                st.markdown("**Sample affected log entries:**")
                df = pd.DataFrame(r.affected_entries)[["line_no", "level", "message"]].head(5)
                st.dataframe(df, use_container_width=True)

    # Export
    if st.button("📥 Export Anomaly Report (CSV)"):
        df = pd.DataFrame([r.to_dict() for r in results])
        st.download_button(
            "Download CSV",
            data=df.to_csv(index=False),
            file_name="anomaly_report.csv",
            mime="text/csv",
        )
