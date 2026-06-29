"""Graph construction.

This module keeps the heavy LangGraph import inside build_graph() so the rest of the
package stays import-light. A module-level ``graph`` is exposed at the bottom for the
LangGraph CLI / Studio (`langgraph dev`).
"""

from __future__ import annotations

from typing import Any

from .state import AgentState


def build_graph(checkpointer: Any | None = None) -> Any:
    """Build and compile the support-ticket StateGraph.

    START -> intake -> classify -> [route_after_classify]
      simple        -> answer -> finalize -> END
      tool          -> tool -> evaluate -> [route_after_evaluate]
                                  success     -> answer -> finalize -> END
                                  needs_retry -> retry -> [route_after_retry]
                                                            attempt<max -> tool (loop)
                                                            attempt>=max -> dead_letter -> finalize
      missing_info  -> clarify -> finalize -> END
      risky         -> risky_action -> approval -> [route_after_approval]
                                          approved -> tool -> evaluate -> ...
                                          rejected -> clarify -> finalize -> END
      error         -> retry -> [route_after_retry] -> tool / dead_letter ...
    """
    from langgraph.graph import END, START, StateGraph

    from . import nodes
    from .routing import (
        route_after_approval,
        route_after_classify,
        route_after_evaluate,
        route_after_retry,
    )

    builder = StateGraph(AgentState)

    # 1) Register all 11 nodes (names MUST match routing return values).
    builder.add_node("intake", nodes.intake_node)
    builder.add_node("classify", nodes.classify_node)
    builder.add_node("tool", nodes.tool_node)
    builder.add_node("evaluate", nodes.evaluate_node)
    builder.add_node("answer", nodes.answer_node)
    builder.add_node("clarify", nodes.ask_clarification_node)
    builder.add_node("risky_action", nodes.risky_action_node)
    builder.add_node("approval", nodes.approval_node)
    builder.add_node("retry", nodes.retry_or_fallback_node)
    builder.add_node("dead_letter", nodes.dead_letter_node)
    builder.add_node("finalize", nodes.finalize_node)

    # 2) Fixed edges.
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "classify")
    builder.add_edge("tool", "evaluate")
    builder.add_edge("risky_action", "approval")
    builder.add_edge("answer", "finalize")
    builder.add_edge("clarify", "finalize")
    builder.add_edge("dead_letter", "finalize")
    builder.add_edge("finalize", END)

    # 3) Conditional edges (explicit path maps so Studio renders them correctly).
    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "answer": "answer",
            "tool": "tool",
            "clarify": "clarify",
            "risky_action": "risky_action",
            "retry": "retry",
        },
    )
    builder.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {"retry": "retry", "answer": "answer"},
    )
    builder.add_conditional_edges(
        "retry",
        route_after_retry,
        {"tool": "tool", "dead_letter": "dead_letter"},
    )
    builder.add_conditional_edges(
        "approval",
        route_after_approval,
        {"tool": "tool", "clarify": "clarify"},
    )

    # 4) Compile (checkpointer optional — injected by the dev server when None).
    return builder.compile(checkpointer=checkpointer)


# Module-level compiled graph for `langgraph dev` / LangGraph Studio.
# No baked-in checkpointer here — the dev server provides its own persistence.
graph = build_graph()
