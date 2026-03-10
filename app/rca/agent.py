"""
RCA Agent — Root Cause Analysis
---------------------------------
Implements a ReAct-style agentic loop:
  Think → Act (tool call) → Observe → Repeat → Answer

Tools available to the agent:
  - search_logs(query)      : semantic vector search over ingested logs
  - get_error_context(line) : fetch surrounding lines for a given line number
  - lookup_sop(topic)       : retrieve SOP / runbook from knowledge base
  - count_errors(level)     : count log entries by severity level
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from app.llm.client import get_llm_client
from app.ingestion.vector_store import get_vector_store
from app.ingestion.parser import LogEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent step dataclass (for UI streaming)
# ---------------------------------------------------------------------------

@dataclass
class AgentStep:
    step_no: int
    thought: str = ""
    action: str = ""
    action_input: str = ""
    observation: str = ""
    is_final: bool = False
    final_answer: str = ""


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _tool_search_logs(query: str, entries: List[LogEntry] = None) -> str:
    store = get_vector_store()
    results = store.query(query, collection="logs", top_k=5)
    if not results:
        # Fallback: simple keyword search over in-memory entries
        if entries:
            hits = [e for e in entries if query.lower() in (e.message or e.raw).lower()][:5]
            if hits:
                return "\n".join(f"[Line {h.line_no}] {h.raw[:200]}" for h in hits)
        return "No results found."
    return "\n".join(f"Score={r['score']:.2f}: {r['text'][:300]}" for r in results)


def _tool_get_error_context(line_no_str: str, entries: List[LogEntry]) -> str:
    try:
        line_no = int(line_no_str)
    except ValueError:
        return "Invalid line number."
    window = [e for e in entries if abs(e.line_no - line_no) <= 10]
    if not window:
        return "No entries found around that line."
    return "\n".join(f"[{e.line_no}][{e.level}] {e.raw[:200]}" for e in window)


def _tool_lookup_sop(topic: str) -> str:
    store = get_vector_store()
    results = store.query(topic, collection="sops", top_k=3)
    if not results:
        return f"No SOP found for '{topic}'. General advice: check service health, review recent deployments, inspect upstream dependencies."
    return "\n".join(f"SOP [{i+1}]: {r['text'][:400]}" for i, r in enumerate(results))


def _tool_count_errors(level: str, entries: List[LogEntry]) -> str:
    level = level.upper()
    count = sum(1 for e in entries if e.level == level)
    total = len(entries)
    return f"{count} entries with level '{level}' out of {total} total ({100*count/total:.1f}% if total else 0)."


# ---------------------------------------------------------------------------
# RCA Agent
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an expert SRE Root-Cause Analysis agent. You have access to tools to investigate log files.

Available tools:
- search_logs(query: str) → Search logs semantically for relevant entries
- get_error_context(line_no: str) → Get surrounding lines for context
- lookup_sop(topic: str) → Retrieve runbooks or SOPs
- count_errors(level: str) → Count log entries by severity level

Respond in this exact JSON format for each step:
{
  "thought": "Your reasoning about what to do next",
  "action": "tool_name or FINISH",
  "action_input": "input string for the tool, or final answer if FINISH"
}

Always respond ONLY in the following JSON structure:

{
  "Root Cause of the Anomaly": string,
  "Recommended Fix": string
}

When you have enough information from search_logs and lookup_sop, set action to "FINISH" and write the root cause analysis in action_input.
Keep your Root Cause Analysis clear: state the root cause, evidence, and recommended fix in plain language.
IMPORTANT: Never include credentials, passwords, or API keys in your output."""


class RCAAgent:
    def __init__(self, entries: List[LogEntry], max_steps: int = 8):
        self.entries = entries
        self.max_steps = max_steps
        self.tools: Dict[str, Callable] = {
            "search_logs": lambda q: _tool_search_logs(q, entries),
            "get_error_context": lambda l: _tool_get_error_context(l, entries),
            "lookup_sop": _tool_lookup_sop,
            "count_errors": lambda lvl: _tool_count_errors(lvl, entries),
        }

    def run(self, user_query: str):
        """
        Generator that yields AgentStep objects for streaming in UI.
        """
        client = get_llm_client()
        if client is None:
            yield AgentStep(
                step_no=1, is_final=True,
                final_answer="LLM client not configured. Please set AZURE_OPENAI_KEY or OPENAI_API_KEY in .env."
            )
            return

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Perform root-cause analysis for the following issue:\n\n{user_query}\n\n"
                f"There are {len(self.entries)} log entries available. "
                f"Error count: {sum(1 for e in self.entries if e.level in ('ERROR','CRITICAL','FATAL'))}. "
                "Use tools to investigate step by step."
            )},
        ]

        for step_no in range(1, self.max_steps + 1):
            raw = client.chat(messages)
            try:
                # Strip markdown code fences if present
                clean = raw.strip().strip("```json").strip("```").strip()
                obj = json.loads(clean)
            except json.JSONDecodeError:
                obj = {"thought": raw, "action": "FINISH", "action_input": raw}

            thought = obj.get("thought", "")
            action = obj.get("action", "FINISH")
            action_input = obj.get("action_input", "")

            if action == "FINISH":
                step = AgentStep(
                    step_no=step_no,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    is_final=True,
                    final_answer=action_input,
                )
                yield step
                return

            # Call tool
            tool_fn = self.tools.get(action)
            if tool_fn is None:
                observation = f"Unknown tool '{action}'. Available: {list(self.tools.keys())}"
            else:
                try:
                    observation = tool_fn(action_input)
                except Exception as e:
                    observation = f"Tool error: {e}"

            step = AgentStep(
                step_no=step_no,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
            )
            yield step

            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        # Max steps reached
        yield AgentStep(
            step_no=self.max_steps,
            is_final=True,
            final_answer="Max reasoning steps reached. Summary: multiple errors detected in logs. Recommend reviewing recent deployments and checking upstream service health.",
        )
