import streamlit as st
from app.rag.engine import rag_query, ingest_sop_document, extract_text_from_docx, extract_text_from_pdf_pypdf2
from app.observability.metrics import get_metrics, Timer


def render_rag_view():
    st.header("📚 RAG — Knowledge Base Q&A")
    st.markdown(
        "Ask questions over your **logs + SOPs** using Retrieval-Augmented Generation. "
        "Answers are grounded in retrieved context and checked for hallucinations."
    )

    tab1, tab2 = st.tabs(["🔎 Query Logs & SOPs", "📤 Upload SOP / Runbook"])

    with tab1:
        _render_query_tab()

    with tab2:
        _render_sop_upload_tab()


def _render_query_tab():
    query = st.text_input(
        "Ask a question about your logs or SOPs",
        placeholder="e.g. 'What caused the 502 errors?' or 'How do I restart the payment service?'",
    )

    col1, col2 = st.columns(2)
    with col1:
        use_logs = st.checkbox("Search logs", value=True)
    with col2:
        use_sops = st.checkbox("Search SOPs / Runbooks", value=True)
    top_k = st.slider("Top-K retrieved chunks", 2, 10, 5)

    if st.button("🔍 Ask", type="primary") and query.strip():
        collections = []
        if use_logs:
            collections.append("logs")
        if use_sops:
            collections.append("sops")

        with st.spinner("Retrieving and generating answer..."):
            with Timer("rag_query", query=query[:50]):
                result = rag_query(query, collections=collections, top_k=top_k)
            get_metrics().record("rag_hallucination_score", result["hallucination_score"])

        st.subheader("Answer")
        if result["is_safe"]:
            st.success(result["answer"])
        else:
            st.error("⚠️ Response blocked by RAI guardrail.")

        col1, col2 = st.columns(2)
        col1.metric("Grounding Score", f"{result['hallucination_score']:.0%}")
        col2.metric("Sources Retrieved", len(result["sources"]))

        with st.expander("📄 Retrieved Sources"):
            for i, src in enumerate(result["sources"], 1):
                st.markdown(f"**Source {i}** (collection: `{src.get('collection','?')}`, score: `{src.get('score',0):.2f}`)")
                st.code(src["text"][:400], language="text")


def _render_sop_upload_tab():
    st.markdown("Upload SOPs, runbooks, or knowledge base documents to enable RAG over them.")

    title = st.text_input("Document title", placeholder="e.g. Database Recovery Runbook")
    sop_text = st.text_area(
        "Paste SOP / Runbook content",
        placeholder="Paste the text of your standard operating procedure or runbook here...",
        height=300,
    )
    st.text_area("File content preview", value=sop_text[:500], height=150, disabled=True)
    sop_files_text = sop_text

    sop_files = st.file_uploader("Or upload SOP files", type=["txt","pdf","docx"],accept_multiple_files=True)
    


    for uploaded in sop_files:
        if uploaded:
            title = uploaded.name
            ext = uploaded.name.split('.')[-1]
            try:
                if ext == "txt":
                    sop_text = uploaded.read().decode("utf-8", errors="replace")

                elif ext == "docx":
                    uploaded.seek(0)
                    sop_text = extract_text_from_docx(uploaded)

                elif ext == "pdf":
                    # Try quick path first
                    uploaded.seek(0)
                    sop_text = extract_text_from_pdf_pypdf2(uploaded)

                    # # If nothing came out, consider higher-fidelity / OCR fallbacks
                    # if not sop_text.strip():
                    #     uploaded.seek(0)
                    #     # Better layout handling
                    #     try:
                    #         sop_text = extract_text_from_pdf_pdfminer(uploaded)
                    #     except Exception:
                    #         pass

                    # if not sop_text.strip():
                    #     # As a last resort use OCR (if configured)
                    #     uploaded.seek(0)
                    #     sop_text = extract_text_from_scanned_pdf_ocr(uploaded)

                if not sop_text.strip():
                    st.warning("No extractable text found. If it's a scanned PDF, enable OCR.")
                
                st.text_area("File content preview", value=sop_text[:500], height=150, disabled=True)
                sop_files_text = sop_text

            except Exception as e:
                st.error(f"Failed to decode file: {e}")


        # if sop_file:
            # sop_text = sop_file.read().decode("utf-8", errors="replace")
            

    if st.button("📤 Ingest into Knowledge Base", type="primary"):
        if not sop_text.strip():
            st.warning("Please provide SOP content.")
            return
        with st.spinner("Ingesting..."):
            n = ingest_sop_document(sop_files_text, title=title or "Unnamed SOP")
        st.success(f"✅ Ingested **{n}** chunks into the knowledge base.")
