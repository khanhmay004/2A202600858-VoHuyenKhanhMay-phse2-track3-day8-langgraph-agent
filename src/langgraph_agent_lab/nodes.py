"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

import os
import time
from typing import Literal

from pydantic import BaseModel, Field

from .llm import get_llm
from .state import AgentState, ApprovalDecision, make_event


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── classify: LLM + structured output ───────────────────────────────
class IntentClassification(BaseModel):
    """Structured output schema for intent classification."""

    route: Literal["simple", "tool", "missing_info", "risky", "error"] = Field(
        description="The single best route for this support ticket."
    )
    reasoning: str = Field(default="", description="One short sentence explaining the choice.")


CLASSIFY_SYSTEM = """You are an intent classifier for a customer-support agent.
Classify the user's support ticket into EXACTLY ONE route:
- risky: actions with side effects, e.g. refund, delete or cancel an account,
  send an email, charge a card, or reset another user's data.
- tool: information lookups (order status, tracking, search, account info) with no side effects.
- missing_info: a vague or incomplete request lacking actionable detail
  (e.g. "fix it", "help", "it's broken").
- error: the ticket describes a SYSTEM failure or outage
  (timeout, crash, cannot recover, service unavailable).
- simple: a general how-to question answerable without tools or actions.

If several could apply, use this PRIORITY: risky > tool > missing_info > error > simple.
Return only the structured classification."""


def classify_node(state: AgentState) -> dict:
    """LLM-based intent classification using structured output."""
    t0 = time.perf_counter()
    llm = get_llm().with_structured_output(IntentClassification)
    result: IntentClassification = llm.invoke(
        [("system", CLASSIFY_SYSTEM), ("human", state.get("query", ""))]
    )
    route = result.route
    risk_level = "high" if route == "risky" else "low"
    latency = int((time.perf_counter() - t0) * 1000)
    return {
        "route": route,
        "risk_level": risk_level,
        "messages": [f"classify:{route}"],
        "events": [
            make_event(
                "classify",
                "completed",
                f"route={route}",
                route=route,
                reasoning=result.reasoning,
                latency_ms=latency,
            )
        ],
    }


# ─── tool: mock tool with error simulation for the error route ───────
def tool_node(state: AgentState) -> dict:
    """Mock tool. Simulate a transient failure for the 'error' route while attempt < 2."""
    route = state.get("route", "")
    attempt = state.get("attempt", 0)
    if route == "error" and attempt < 2:
        result = f"ERROR: transient tool failure (attempt={attempt})"
        event = make_event("tool", "error", result, attempt=attempt)
    else:
        result = f"TOOL_OK: retrieved data for query '{state.get('query', '')[:40]}'"
        event = make_event("tool", "completed", result, attempt=attempt)
    return {
        "tool_results": [result],
        "messages": [f"tool:{result[:30]}"],
        "events": [event],
    }


# ─── evaluate: retry-loop gate (heuristic; LLM-judge = bonus) ────────
def evaluate_node(state: AgentState) -> dict:
    """Evaluate the latest tool result -> 'success' | 'needs_retry'."""
    results = state.get("tool_results", [])
    latest = results[-1] if results else ""
    needs_retry = "ERROR" in latest.upper()
    evaluation = "needs_retry" if needs_retry else "success"
    return {
        "evaluation_result": evaluation,
        "events": [make_event("evaluate", "completed", f"eval={evaluation}")],
    }


# ─── answer: LLM-grounded final response ─────────────────────────────
ANSWER_SYSTEM = """You are a helpful, concise customer-support agent.
Write a friendly final reply to the customer.
Ground your answer ONLY in the provided context (tool results / approval decision / the query).
Do not invent order numbers, prices, or facts that are not present in the context."""


def answer_node(state: AgentState) -> dict:
    """LLM-generated answer grounded in tool_results / approval / the original query."""
    t0 = time.perf_counter()
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")

    context_parts: list[str] = []
    if tool_results:
        context_parts.append("Tool results:\n" + "\n".join(tool_results))
    if approval:
        context_parts.append(f"Approval decision: {approval}")
    context = "\n\n".join(context_parts) or "(no tool data available)"

    human = f"Customer query: {query}\n\nContext:\n{context}\n\nWrite the final reply:"
    llm = get_llm()
    resp = llm.invoke([("system", ANSWER_SYSTEM), ("human", human)])
    answer = resp.content if hasattr(resp, "content") else str(resp)
    latency = int((time.perf_counter() - t0) * 1000)
    return {
        "final_answer": answer,
        "messages": ["answer:done"],
        "events": [
            make_event("answer", "completed", "generated grounded answer", latency_ms=latency)
        ],
    }


# ─── clarify: ask for missing information ─────────────────────────────
def ask_clarification_node(state: AgentState) -> dict:
    """Ask a specific clarification question instead of hallucinating an answer."""
    query = state.get("query", "")
    question = (
        f'Could you share more details? Your request "{query}" is missing specifics - '
        "please tell me which order, account, or item is involved and the outcome you expect."
    )
    return {
        "pending_question": question,
        "final_answer": question,  # satisfy success gate (final_answer or pending_question)
        "messages": ["clarify:asked"],
        "events": [make_event("clarify", "completed", "asked clarification question")],
    }


# ─── risky_action: prepare a risky action for approval ───────────────
def risky_action_node(state: AgentState) -> dict:
    """Describe the proposed risky action that requires human approval."""
    query = state.get("query", "")
    action = f"PROPOSED ACTION (needs human approval): {query}"
    return {
        "proposed_action": action,
        "messages": [f"risky:{query[:30]}"],
        "events": [make_event("risky_action", "completed", "prepared risky action for approval")],
    }


# ─── approval: human-in-the-loop step ────────────────────────────────
def approval_node(state: AgentState) -> dict:
    """Mock approval by default (approved=True) so CI/tests run offline.

    Extension: if env LANGGRAPH_INTERRUPT=true, pause with interrupt() for real HITL.
    """
    proposed = state.get("proposed_action", "(unspecified action)")
    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        decision = interrupt(
            {
                "proposed_action": proposed,
                "question": "Approve this action? reply approved=true/false",
            }
        )
        if isinstance(decision, dict):
            approval = ApprovalDecision(**decision).model_dump()
        else:
            approval = ApprovalDecision(approved=bool(decision)).model_dump()
    else:
        approval = ApprovalDecision(
            approved=True, reviewer="mock-reviewer", comment="auto-approved (mock)"
        ).model_dump()

    state_msg = "approved" if approval["approved"] else "rejected"
    return {
        "approval": approval,
        "messages": [f"approval:{state_msg}"],
        "events": [
            make_event(
                "approval", "interrupt", "human approval step", approved=approval["approved"]
            )
        ],
    }


# ─── retry: record a bounded retry attempt ───────────────────────────
def retry_or_fallback_node(state: AgentState) -> dict:
    """Increment the attempt counter and log the transient failure."""
    attempt = state.get("attempt", 0) + 1
    return {
        "attempt": attempt,
        "errors": [f"retry attempt {attempt}: transient failure, retrying"],
        "messages": [f"retry:{attempt}"],
        "events": [make_event("retry", "retry", f"attempt {attempt}", attempt=attempt)],
    }


# ─── dead_letter: handle unresolvable failures ───────────────────────
def dead_letter_node(state: AgentState) -> dict:
    """Escalate after max retries are exhausted (third layer: retry -> fallback -> dead letter)."""
    attempt = state.get("attempt", 0)
    msg = (
        f"We could not complete your request after {attempt} attempt(s). "
        "It has been escalated to a human engineer (dead-letter queue)."
    )
    return {
        "final_answer": msg,
        "errors": ["dead_letter: max retries exhausted"],
        "messages": ["dead_letter"],
        "events": [
            make_event(
                "dead_letter", "completed", "escalated to dead-letter queue", attempt=attempt
            )
        ],
    }


# ─── finalize: final audit event before END ──────────────────────────
def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END."""
    return {
        "messages": ["finalize"],
        "events": [
            make_event("finalize", "completed", "workflow finished", route=state.get("route", ""))
        ],
    }
