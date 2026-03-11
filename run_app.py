"""
run_app.py — Top-level launcher for Log Intelligence Assistant
--------------------------------------------------------------
Run from the project4 folder:

    streamlit run run_app.py

This is the ONLY correct way to launch the app.
It ensures:
  1. Project root is on sys.path  (fixes all 'from app.xxx' imports)
  2. .env file is loaded early     (fixes LLM / API key issues)
"""

print("run_app started")

import sys
import os
from pathlib import Path

# ── 1. Add project root to sys.path ──────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── 2. Load .env BEFORE any app module is imported ───────────────────────────
_ENV_FILE = _ROOT / ".env"
try:
    from dotenv import load_dotenv
    if _ENV_FILE.exists():
        load_dotenv(dotenv_path=str(_ENV_FILE), override=True)
        print(f"[run_app] ✅ .env loaded from {_ENV_FILE}", file=sys.stderr)
    else:
        print(f"[run_app] ⚠️  No .env found at {_ENV_FILE}", file=sys.stderr)
        print(f"[run_app]    Copy .env.example → .env and fill in your API keys", file=sys.stderr)
except ImportError:
    print("[run_app] ⚠️  python-dotenv not installed — run: pip install python-dotenv", file=sys.stderr)

# ── 3. Launch app ─────────────────────────────────────────────────────────────
from app.main import main
main()
