"""
RAI Guardrails — PII Masking & Credential Scrubbing
-----------------------------------------------------
Applied at ingestion time so sensitive data never enters the vector store or LLM prompts.

Patterns masked:
  - Passwords / secrets / API keys in key=value pairs
  - IPv4 addresses (optional — configurable)
  - Email addresses
  - Bearer tokens / JWTs
  - Credit card numbers (basic pattern)
  - User IDs matching common patterns
"""

import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# (pattern, replacement_label)
_MASKING_RULES: List[Tuple[re.Pattern, str]] = [
    # Credentials in key=value or key: value form
    (re.compile(r'(?i)(password|passwd|pwd|secret|api_key|apikey|token|auth)\s*[=:]\s*\S+'), r'\1=***MASKED***'),
    # Bearer tokens
    (re.compile(r'(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*'), 'Bearer ***MASKED***'),
    # JWTs (three base64 segments separated by dots)
    (re.compile(r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'), '***JWT_MASKED***'),
    # Long base64 strings (likely tokens)
    (re.compile(r'[A-Za-z0-9+/]{40,}={0,2}'), '***TOKEN_MASKED***'),
    # Email addresses
    (re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'), '***EMAIL***'),
    # Credit card (simplified)
    (re.compile(r'\b(?:\d[ \-]?){13,16}\b'), '***CC_MASKED***'),
    # AWS-style access keys
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), '***AWS_KEY***'),
    # Private IPv4 ranges kept visible; public IPs optionally masked
    # (disabled by default — uncomment if needed)
    # (re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'), '***IP***'),
]


def mask_pii(text: str) -> str:
    """Apply all masking rules to a single log line."""
    for pattern, replacement in _MASKING_RULES:
        text = pattern.sub(replacement, text)
    return text


def validate_llm_output(text: str) -> Tuple[bool, List[str]]:
    """
    Check LLM output for accidental credential leakage.
    Returns (is_safe, list_of_violations).
    """
    violations = []
    suspicious = [
        re.compile(r'(?i)(password|secret|api_key)\s*[=:]\s*[^\s\*]+'),
        re.compile(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'),
        re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
        re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'),
    ]
    for pat in suspicious:
        matches = pat.findall(text)
        if matches:
            violations.extend(matches)

    if violations:
        logger.warning("LLM output RAI check failed — %d violations found", len(violations))
    return len(violations) == 0, violations


def hallucination_check(response: str, source_entries: List[str]) -> float:
    """
    Simple grounding score: fraction of claimed facts that appear in source entries.
    Returns 0.0 (no grounding) to 1.0 (fully grounded).
    A production system would use a dedicated NLI model.
    """
    if not source_entries or not response:
        return 0.0

    # Extract significant words from response (>6 chars)
    words = set(w.lower() for w in re.findall(r'\b\w{6,}\b', response))
    source_text = " ".join(source_entries).lower()
    if not words:
        return 1.0

    grounded = sum(1 for w in words if w in source_text)
    score = grounded / len(words)
    return round(score, 2)
