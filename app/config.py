"""
Central configuration for Log Intelligence Assistant
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ── Load .env file ────────────────────────────────────────────────────────────
def _load_dotenv():
    try:
        from dotenv import load_dotenv, find_dotenv

        # Walk up from this file to find .env in project root
        _here = Path(__file__).resolve().parent   # .../project4/app
        _root = _here.parent                       # .../project4

        _env_file = _root / ".env"
        if _env_file.exists():
            load_dotenv(dotenv_path=str(_env_file), override=True)
            print(f"[config] ✅ .env loaded from: {_env_file}", file=sys.stderr)
            return

        # Fallback: search upward from cwd
        found = find_dotenv(usecwd=True)
        if found:
            load_dotenv(dotenv_path=found, override=True)
            print(f"[config] ✅ .env loaded from: {found}", file=sys.stderr)
        else:
            print("[config] ⚠️  No .env file found — using system environment only.", file=sys.stderr)

    except ImportError:
        print("[config] ⚠️  python-dotenv not installed. Run: pip install python-dotenv", file=sys.stderr)


_load_dotenv()
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AppConfig:
    # Azure / LLM
    azure_openai_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    azure_openai_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_KEY", ""))
    azure_openai_deployment: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"))
    azure_openai_api_version: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"))

    # OpenAI (fallback)
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # Vector DB
    vector_db_type: str = field(default_factory=lambda: os.getenv("VECTOR_DB_TYPE", "chroma"))
    chroma_persist_dir: str = field(default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", "./data/chroma"))
    azure_search_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_SEARCH_ENDPOINT", ""))
    azure_search_key: str = field(default_factory=lambda: os.getenv("AZURE_SEARCH_KEY", ""))
    azure_search_index: str = field(default_factory=lambda: os.getenv("AZURE_SEARCH_INDEX", "log-index"))

    # Embedding model
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"))

    # Log ingestion
    max_log_file_size_mb: int = field(default_factory=lambda: int(os.getenv("MAX_LOG_FILE_SIZE_MB", "50")))
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "512")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "64")))

    # Observability
    appinsights_connection_string: str = field(default_factory=lambda: os.getenv("APPINSIGHTS_CONNECTION_STRING", ""))

    # RAI / Safety
    enable_pii_masking: bool = field(default_factory=lambda: os.getenv("ENABLE_PII_MASKING", "true").lower() == "true")
    enable_profanity_filter: bool = field(default_factory=lambda: os.getenv("ENABLE_PROFANITY_FILTER", "true").lower() == "true")
    credential_patterns: list = field(default_factory=lambda: [
        r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+",
        r"(?i)(api_key|apikey|secret|token)\s*[:=]\s*\S+",
        r"[A-Za-z0-9+/]{40,}={0,2}",
    ])


CONFIG = AppConfig()


def debug_config():
    """Print config status for troubleshooting — call from sidebar or main."""
    key = CONFIG.azure_openai_key
    oai = CONFIG.openai_api_key
    print(f"[config] AZURE_OPENAI_ENDPOINT : {'SET' if CONFIG.azure_openai_endpoint else 'MISSING'}", file=sys.stderr)
    print(f"[config] AZURE_OPENAI_KEY      : {'SET (' + key[:6] + '...)' if key else 'MISSING'}", file=sys.stderr)
    print(f"[config] AZURE_OPENAI_DEPLOY   : {CONFIG.azure_openai_deployment}", file=sys.stderr)
    print(f"[config] OPENAI_API_KEY        : {'SET (' + oai[:6] + '...)' if oai else 'MISSING'}", file=sys.stderr)
