import streamlit as st
import pandas as pd
from app.observability.metrics import get_metrics


def render_observability():
    st.header("📊 Observability Dashboard")
    st.markdown(
        "Live KPI monitoring: ingestion stats, anomaly detection accuracy, "
        "LLM quality metrics, and query execution traces."
    )

    metrics = get_metrics()
    summary = metrics.summary()
    traces = metrics.recent_traces(30)

    if not summary and not traces:
        st.info("No metrics recorded yet. Run ingestion, anomaly detection, or RCA first.")
        return

    # KPI cards
    st.subheader("KPI Summary")
    kpi_keys = [
        ("log_ingestion_latency_ms", "Ingestion Latency"),
        ("anomaly_detection_latency_ms", "Detection Latency"),
        ("rca_agent_latency_ms", "RCA Latency"),
        ("rag_query_latency_ms", "RAG Query Latency"),
        ("anomalies_detected", "Anomalies Detected"),
        ("chunks_indexed", "Chunks Indexed"),
        ("rag_hallucination_score", "RAG Grounding Score"),
        ("rca_steps_taken", "RCA Steps (avg)"),
    ]

    cols = st.columns(4)
    shown = 0
    for key, label in kpi_keys:
        if key in summary:
            col = cols[shown % 4]
            val = summary[key]
            display = f"{val['mean']:.0f}" if val['mean'] > 10 else f"{val['mean']:.2f}"
            col.metric(label, display, help=f"min={val['min']} max={val['max']} n={val['count']}")
            shown += 1

    if summary:
        st.subheader("All Metrics")
        df = pd.DataFrame([
            {"Metric": k, "Count": v["count"], "Mean": v["mean"], "Min": v["min"], "Max": v["max"], "StdDev": v["stdev"]}
            for k, v in summary.items()
        ])
        st.dataframe(df, use_container_width=True)

    # Latency chart
    latency_keys = [k for k in summary if "latency" in k]
    if latency_keys:
        st.subheader("Latency Overview (ms)")
        latency_df = pd.DataFrame({
            k.replace("_latency_ms", ""): [summary[k]["mean"]]
            for k in latency_keys
        })
        st.bar_chart(latency_df.T.rename(columns={0: "Mean Latency (ms)"}))

    # Traces table
    if traces:
        st.subheader(f"Recent Traces (last {len(traces)})")
        df = pd.DataFrame(traces)
        st.dataframe(df, use_container_width=True)

    # Guardrail events
    events = metrics.all_events()
    rai_events = [e for e in events if "rai" in e.get("name", "").lower() or "hallucination" in e.get("name", "").lower()]
    if rai_events:
        st.subheader("🛡️ RAI Guardrail Events")
        st.dataframe(pd.DataFrame(rai_events), use_container_width=True)

    # st.divider()
    # col1, col2 = st.columns(2)
    # col1.info("💡 Connect Azure App Insights via `APPINSIGHTS_CONNECTION_STRING` in `.env` for cloud monitoring.")
    # col2.info("📡 OpenTelemetry format supported — enable with `USE_OTEL_FORMAT=true`.")
