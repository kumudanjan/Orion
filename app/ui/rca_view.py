import streamlit as st
from app.rca.agent import RCAAgent, AgentStep
from app.observability.metrics import get_metrics, Timer


def render_rca_view():
    st.header("🧠 RCA Agent — Root Cause Analysis")
    st.markdown(
        "The agent performs **step-by-step reasoning** (ReAct loop): "
        "it thinks, calls tools (search logs, lookup SOPs, count errors), "
        "observes results, and iterates until it reaches a root-cause conclusion."
    )

    entries = st.session_state.get("log_entries")
    if not entries:
        st.warning("No logs loaded. Please go to **Log Ingestion** first.")
        return

    anomalies = st.session_state.get("anomalies", [])

    # Quick-fill from anomaly
    st.subheader("Describe the Issue")
    if anomalies:
        preset = st.selectbox(
            "Pre-fill from detected anomaly (optional)",
            options=["-- manual entry --"] + [f"[{a.severity.upper()}] {a.title}" for a in anomalies],
        )
        if preset != "-- manual entry --":
            idx = [f"[{a.severity.upper()}] {a.title}" for a in anomalies].index(preset)
            default_q = f"Investigate this anomaly: {anomalies[idx].title}. {anomalies[idx].description}"
        else:
            default_q = ""
    else:
        default_q = ""

    query = st.text_area(
        "Describe the issue or paste an error message:",
        value=default_q,
        placeholder="e.g. 'Critical spike in 500 errors after 14:00 UTC — investigate root cause'",
        height=100,
    )

    max_steps = st.slider("Max reasoning steps", 3, 10, 6)

    if st.button("🚀 Run RCA Agent", type="primary", disabled=not query.strip()):
        agent = RCAAgent(entries=entries, max_steps=max_steps)

        st.subheader("🔄 Agent Reasoning Trace")
        steps_container = st.container()
        final_container = st.empty()

        step_list = []
        with Timer("rca_agent", query=query[:50]):
            for step in agent.run(query):
                step_list.append(step)
                with steps_container:
                    _render_step(step)

        get_metrics().record("rca_steps_taken", len(step_list))

        # Final answer
        final_steps = [s for s in step_list if s.is_final]
        if final_steps:
            with final_container:
                st.subheader("✅ Root Cause Analysis")
                st.success(final_steps[-1].final_answer)
                st.session_state["last_rca"] = final_steps[-1].final_answer

    # Show previous RCA
    if "last_rca" in st.session_state and not st.button("Clear RCA", key="clear_rca"):
        st.subheader("📋 Previous RCA Result")
        st.info(st.session_state["last_rca"])


def _render_step(step: AgentStep):
    if step.is_final:
        return

    with st.expander(f"Step {step.step_no}: {step.action or 'Thinking...'}", expanded=False):
        if step.thought:
            st.markdown(f"**💭 Thought:** {step.thought}")
        if step.action and step.action != "FINISH":
            st.markdown(f"**🔧 Action:** `{step.action}({step.action_input[:100]})`")
        if step.observation:
            st.markdown(f"**👁️ Observation:**")
            st.code(step.observation[:500], language="text")
