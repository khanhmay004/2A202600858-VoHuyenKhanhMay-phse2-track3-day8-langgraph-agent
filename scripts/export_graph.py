"""Export the graph diagram as Mermaid (+ PNG if rendering is available)."""

from __future__ import annotations

from pathlib import Path

from langgraph_agent_lab.graph import build_graph

Path("outputs").mkdir(exist_ok=True)
g = build_graph()
mermaid = g.get_graph().draw_mermaid()
Path("outputs/graph.mmd").write_text(mermaid, encoding="utf-8")
print(mermaid)

try:
    png = g.get_graph().draw_mermaid_png()
    Path("outputs/graph.png").write_bytes(png)
    print("Wrote outputs/graph.png")
except Exception as exc:  # PNG needs internet or graphviz; ignore on failure
    print(f"(Skipped PNG: {exc})")
