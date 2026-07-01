"""Persistence demo: interrupt -> simulated 'crash' -> resume from SQLite + state history.

Run: python scripts/demo_resume.py
Makes real LLM calls (the risky scenario eventually reaches answer_node).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()
os.environ["LANGGRAPH_INTERRUPT"] = "true"  # enable real HITL interrupt for this demo

from langgraph.types import Command  # noqa: E402

from langgraph_agent_lab.graph import build_graph  # noqa: E402
from langgraph_agent_lab.persistence import build_checkpointer  # noqa: E402
from langgraph_agent_lab.state import Route, Scenario, initial_state  # noqa: E402

THREAD = "thread-resume-demo"
CONFIG = {"configurable": {"thread_id": THREAD}}


def run() -> None:
    # 1) First run: the graph pauses at `approval` (interrupt) and PERSISTS to SQLite.
    g1 = build_graph(checkpointer=build_checkpointer("sqlite"))
    scn = Scenario(
        id="resume-demo",
        query="Refund this customer and send email",
        expected_route=Route.RISKY,
        requires_approval=True,
    )
    out1 = g1.invoke(initial_state(scn), config=CONFIG)
    print("== Run 1: graph interrupted ==")
    print("interrupt payload:", out1.get("__interrupt__"))

    # 2) Simulate a CRASH: drop g1, build a FRESH graph over the same SQLite file + thread.
    del g1
    g2 = build_graph(checkpointer=build_checkpointer("sqlite"))

    # 3) RESUME from the on-disk checkpoint.
    out2 = g2.invoke(Command(resume={"approved": True}), config=CONFIG)
    print("\n== Run 2 (new process object): RESUMED ==")
    print("final_answer:", out2.get("final_answer"))

    # 4) State history (time-travel).
    print("\n== State history (newest -> oldest) ==")
    for snap in g2.get_state_history(CONFIG):
        print(
            f"  next={snap.next} | route={snap.values.get('route')} "
            f"| attempt={snap.values.get('attempt')}"
        )


if __name__ == "__main__":
    run()
