import streamlit as st
import os
from pathlib import Path


def render_sidebar() -> str:
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=60)
        st.title("Log Intelligence")
        st.caption("GenAI-Powered SRE Assistant")
        st.divider()

        page = st.radio(
            "Navigate",
            options=[
                "Log Ingestion",
                "Anomaly Detection",
                "RAG / Knowledge Base",
                "RCA Agent",
                "Observability",
            ],
            index=0,
        )

        st.divider()
        st.markdown("**Config Status**")

        from app.llm.client import get_llm_client, get_llm_error
        from app.ingestion.vector_store import get_vector_store
        from app.config import CONFIG

        client = get_llm_client()
        store = get_vector_store()

        if client:
            st.success("🤖 LLM: ✅ Connected")
        else:
            st.error("🤖 LLM: ❌ Not configured")

        st.markdown(f"🗄️ Vector DB: ✅ {store._backend.__class__.__name__}")
        st.markdown("🛡️ PII Masking: ✅ Active")

        # ── .env file location check ──────────────────────────────────
        st.divider()
        _root = Path(__file__).resolve().parent.parent.parent
        _env = _root / ".env"

        if not client:
            st.markdown("**🔧 Fix LLM Config**")

            # Show where .env should be
            st.info(f"📁 Expected `.env` location:\n`{_env}`")

            if _env.exists():
                st.warning("`.env` file found but key may be wrong or missing.")
                # Read and show which keys are present (not values)
                env_keys = []
                try:
                    for line in _env.read_text().splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k = line.split("=")[0].strip()
                            v = line.split("=", 1)[1].strip()
                            env_keys.append((k, bool(v)))
                except Exception:
                    pass

                if env_keys:
                    st.markdown("**Keys in your .env:**")
                    for k, has_value in env_keys:
                        icon = "✅" if has_value else "❌"
                        st.markdown(f"{icon} `{k}`")
            else:
                st.error("`.env` file NOT found at expected location!")
                st.markdown(f"**Create it at:** `{_env}`")

            # Show exact error
            err = get_llm_error()
            if err:
                with st.expander("Show error details"):
                    st.code(err)

            # Show what a correct .env looks like
            with st.expander("📋 .env template"):
                st.code("""# Azure OpenAI (recommended)
AZURE_OPENAI_ENDPOINT=https://YOUR_RESOURCE.openai.azure.com/
AZURE_OPENAI_KEY=your_key_here
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# OR OpenAI direct
OPENAI_API_KEY=sk-your_key_here""", language="bash")

            if st.button("🔄 Retry LLM Connection"):
                # Force re-init
                import app.llm.client as _llm_mod
                _llm_mod._client = None
                st.rerun()

        st.divider()
        st.caption("Genpact GenAI Capstone")

    return page
