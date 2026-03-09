"""
Vector Store Abstraction
Supports ChromaDB (local, default) and Azure AI Search (cloud)
"""

import logging
from typing import List, Dict, Any, Optional
from app.config import CONFIG

logger = logging.getLogger(__name__)


class VectorStore:
    """Abstract base — swap ChromaDB ↔ Azure AI Search via config."""

    def __init__(self):
        self._backend = self._init_backend()

    def _init_backend(self):
        if CONFIG.vector_db_type == "azure_search":
            return AzureSearchBackend()
        return ChromaBackend()

    def upsert(self, chunks: List[Dict[str, Any]], collection: str = "logs") -> int:
        return self._backend.upsert(chunks, collection)

    def query(self, query_text: str, collection: str = "logs", top_k: int = 5) -> List[Dict[str, Any]]:
        return self._backend.query(query_text, collection, top_k)

    def collections(self) -> List[str]:
        return self._backend.collections()


# ---------------------------------------------------------------------------
# ChromaDB backend
# ---------------------------------------------------------------------------

class ChromaBackend:
    def __init__(self):
        try:
            import chromadb
            from chromadb.config import Settings
            self.client = chromadb.PersistentClient(
                path=CONFIG.chroma_persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            logger.info("ChromaDB initialised at %s", CONFIG.chroma_persist_dir)
        except ImportError:
            logger.warning("chromadb not installed — vector search disabled")
            self.client = None

    def _get_or_create(self, name: str):
        if self.client is None:
            return None
        return self.client.get_or_create_collection(name)

    def upsert(self, chunks: List[Dict[str, Any]], collection: str = "logs") -> int:
        col = self._get_or_create(collection)
        if col is None:
            return 0
        ids = [f"chunk-{i}-{hash(c['text'])}" for i, c in enumerate(chunks)]
        docs = [c["text"] for c in chunks]
        metas = [c.get("metadata", {}) for c in chunks]
        # Stringify metadata values (Chroma requires primitives)
        metas = [{k: str(v) for k, v in m.items()} for m in metas]
        col.upsert(ids=ids, documents=docs, metadatas=metas)
        return len(ids)

    def query(self, query_text: str, collection: str = "logs", top_k: int = 5) -> List[Dict[str, Any]]:
        col = self._get_or_create(collection)
        if col is None:
            return []
        results = col.query(query_texts=[query_text], n_results=top_k)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        return [
            {"text": d, "metadata": m, "score": 1 - dist}
            for d, m, dist in zip(docs, metas, dists)
        ]

    def collections(self) -> List[str]:
        if self.client is None:
            return []
        return [c.name for c in self.client.list_collections()]


# ---------------------------------------------------------------------------
# Azure AI Search backend
# ---------------------------------------------------------------------------

class AzureSearchBackend:
    def __init__(self):
        try:
            from azure.search.documents import SearchClient
            from azure.search.documents.indexes import SearchIndexClient
            from azure.core.credentials import AzureKeyCredential
            self._cred = AzureKeyCredential(CONFIG.azure_search_key)
            self._endpoint = CONFIG.azure_search_endpoint
            self._index = CONFIG.azure_search_index
            self._index_client = SearchIndexClient(self._endpoint, self._cred)
            logger.info("Azure AI Search backend initialised")
        except ImportError:
            logger.warning("azure-search-documents not installed")
            self._cred = None

    def upsert(self, chunks: List[Dict[str, Any]], collection: str = "logs") -> int:
        if not self._cred:
            return 0
        from azure.search.documents import SearchClient
        client = SearchClient(self._endpoint, collection, self._cred)
        docs = [
            {"id": f"chunk-{i}", "content": c["text"], **c.get("metadata", {})}
            for i, c in enumerate(chunks)
        ]
        result = client.upload_documents(docs)
        return len([r for r in result if r.succeeded])

    def query(self, query_text: str, collection: str = "logs", top_k: int = 5) -> List[Dict[str, Any]]:
        if not self._cred:
            return []
        from azure.search.documents import SearchClient
        client = SearchClient(self._endpoint, collection, self._cred)
        results = client.search(query_text, top=top_k)
        return [{"text": r["content"], "metadata": r, "score": r.get("@search.score", 0)} for r in results]

    def collections(self) -> List[str]:
        if not self._cred:
            return []
        return [idx.name for idx in self._index_client.list_indexes()]


# Singleton
_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
