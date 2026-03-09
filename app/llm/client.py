"""
LLM Client — Azure OpenAI (primary) + OpenAI (fallback)
"""

import logging
import sys
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self._client = None
        self._mode = None
        self._deployment = None
        self._error_reason = ""
        self._init()

    def _init(self):
        # Always re-read from config so .env changes are picked up
        from app.config import CONFIG

        # ── Try Azure OpenAI ─────────────────────────────────────────────
        if CONFIG.azure_openai_key and CONFIG.azure_openai_endpoint:
            try:
                from openai import AzureOpenAI
                self._client = AzureOpenAI(
                    api_key=CONFIG.azure_openai_key,
                    azure_endpoint=CONFIG.azure_openai_endpoint,
                    api_version=CONFIG.azure_openai_api_version,
                )
                self._mode = "azure"
                self._deployment = CONFIG.azure_openai_deployment
                logger.info("LLM: Azure OpenAI ready (%s)", self._deployment)
                print(f"[llm] ✅ Azure OpenAI connected — deployment={self._deployment}", file=sys.stderr)
                return
            except ImportError:
                self._error_reason = "openai package not installed. Run: pip install openai"
                logger.error(self._error_reason)
                return
            except Exception as e:
                self._error_reason = f"Azure OpenAI init error: {e}"
                logger.warning(self._error_reason)

        # ── Try OpenAI fallback ──────────────────────────────────────────
        if CONFIG.openai_api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=CONFIG.openai_api_key)
                self._mode = "openai"
                self._deployment = "gpt-4o"
                logger.info("LLM: OpenAI ready (gpt-4o)")
                print("[llm] ✅ OpenAI connected (gpt-4o)", file=sys.stderr)
                return
            except ImportError:
                self._error_reason = "openai package not installed. Run: pip install openai"
                logger.error(self._error_reason)
                return
            except Exception as e:
                self._error_reason = f"OpenAI init error: {e}"
                logger.warning(self._error_reason)

        # ── Neither configured ───────────────────────────────────────────
        from app.config import CONFIG as C
        missing = []
        if not C.azure_openai_key:
            missing.append("AZURE_OPENAI_KEY")
        if not C.azure_openai_endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not C.openai_api_key:
            missing.append("OPENAI_API_KEY (fallback)")

        self._error_reason = (
            f"LLM not configured. Missing env vars: {', '.join(missing)}. "
            f"Check your .env file is in the project4/ folder and has been saved."
        )
        print(f"[llm] ❌ {self._error_reason}", file=sys.stderr)

    def is_available(self) -> bool:
        return self._client is not None

    @property
    def error_reason(self) -> str:
        return self._error_reason

    def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        return self.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )

    def chat(self, messages: List[Dict], max_tokens: int = 1500) -> str:
        if not self._client:
            return '{"anomalies": []}'
        try:
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.0,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return f"LLM error: {e}"


_client: Optional[LLMClient] = None


def get_llm_client() -> Optional[LLMClient]:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client if _client.is_available() else None


def get_llm_error() -> str:
    """Return the reason LLM is unavailable — for display in the UI."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client.error_reason
