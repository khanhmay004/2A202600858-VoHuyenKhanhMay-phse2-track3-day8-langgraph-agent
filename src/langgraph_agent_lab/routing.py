"""Routing functions for conditional edges.

Each function takes AgentState and returns a string — the name of the next node.
These strings MUST match node names registered in graph.py.
"""

from __future__ import annotations

from .state import AgentState

_CLASSIFY_MAP = {
    "simple": "answer",
    "tool": "tool",
    "missing_info": "clarify",
    "risky": "risky_action",
    "error": "retry",
}


def route_after_classify(state: AgentState) -> str:
    """Map the classified route string to the next graph node (default -> 'answer')."""
    return _CLASSIFY_MAP.get(state.get("route", ""), "answer")


def route_after_evaluate(state: AgentState) -> str:
    """Retry-loop gate: needs_retry -> 'retry', otherwise -> 'answer'."""
    return "retry" if state.get("evaluation_result") == "needs_retry" else "answer"


def route_after_retry(state: AgentState) -> str:
    """Bounded retry: attempt < max_attempts -> 'tool', else -> 'dead_letter'."""
    if state.get("attempt", 0) < state.get("max_attempts", 3):
        return "tool"
    return "dead_letter"


def route_after_approval(state: AgentState) -> str:
    """Approval routing: approved -> 'tool', rejected -> 'clarify'."""
    approval = state.get("approval") or {}
    return "tool" if approval.get("approved") else "clarify"
