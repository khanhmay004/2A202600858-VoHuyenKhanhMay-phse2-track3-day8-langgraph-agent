"""Entry point for `langgraph dev` / LangGraph Studio.

The LangGraph CLI loads this file by PATH (not as a package), so it must use
ABSOLUTE imports only. It re-exports the compiled graph from the installed
package; the relative imports *inside* the package resolve normally because the
package is imported through the normal import machinery (pip install -e .).
"""

from langgraph_agent_lab.graph import build_graph

# No baked-in checkpointer — the dev server injects its own persistence.
graph = build_graph()
