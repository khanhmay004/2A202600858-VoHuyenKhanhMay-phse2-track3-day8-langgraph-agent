"""Dump the per-scenario audit-event trace to outputs/traces/<id>.json.

Note: this RUNS the graph, so it makes real LLM calls (classify + answer).
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from langgraph_agent_lab.graph import build_graph  # noqa: E402
from langgraph_agent_lab.persistence import build_checkpointer  # noqa: E402
from langgraph_agent_lab.scenarios import load_scenarios  # noqa: E402
from langgraph_agent_lab.state import initial_state  # noqa: E402

OUT = Path("outputs/traces")
OUT.mkdir(parents=True, exist_ok=True)

graph = build_graph(checkpointer=build_checkpointer("memory"))
for scn in load_scenarios("data/sample/scenarios.jsonl"):
    st = initial_state(scn)
    final = graph.invoke(st, config={"configurable": {"thread_id": st["thread_id"]}})
    trace = {
        "scenario_id": scn.id,
        "expected_route": scn.expected_route.value,
        "actual_route": final.get("route"),
        "final_answer": final.get("final_answer"),
        "events": final.get("events", []),
    }
    (OUT / f"{scn.id}.json").write_text(
        json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {scn.id}: {len(trace['events'])} events")
