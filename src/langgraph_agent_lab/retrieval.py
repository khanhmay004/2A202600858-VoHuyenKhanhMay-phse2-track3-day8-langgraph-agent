"""Tiny embeddings retriever over a local knowledge base (RAG extension).

Loads markdown docs from data/knowledge_base/, embeds them once with OpenAI
embeddings, and returns the top-k docs by cosine similarity. Used by the grading
harness (scripts/run_grading_rag.py) to answer policy questions with grounded
retrieval and to check top-1 retrieval accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_KB_DIR = "data/knowledge_base"
DEFAULT_EMBED_MODEL = "text-embedding-3-small"


@dataclass
class Doc:
    doc_id: str
    text: str


@dataclass
class Hit:
    doc_id: str
    text: str
    score: float


def load_kb(kb_dir: str = DEFAULT_KB_DIR) -> list[Doc]:
    """Load every *.md file in kb_dir; doc_id is the filename stem."""
    docs: list[Doc] = []
    for path in sorted(Path(kb_dir).glob("*.md")):
        docs.append(Doc(doc_id=path.stem, text=path.read_text(encoding="utf-8")))
    if not docs:
        raise FileNotFoundError(f"No .md documents found in {kb_dir}")
    return docs


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors (pure Python, no numpy dependency)."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


class KBRetriever:
    """Embeds the KB once, then retrieves top-k docs per query by cosine similarity."""

    def __init__(self, kb_dir: str = DEFAULT_KB_DIR, model: str = DEFAULT_EMBED_MODEL) -> None:
        from langchain_openai import OpenAIEmbeddings

        self.docs = load_kb(kb_dir)
        self.embeddings = OpenAIEmbeddings(model=model)
        self.doc_vectors = self.embeddings.embed_documents([d.text for d in self.docs])

    def retrieve(self, query: str, k: int = 1) -> list[Hit]:
        query_vec = self.embeddings.embed_query(query)
        hits = [
            Hit(doc.doc_id, doc.text, cosine(query_vec, vec))
            for doc, vec in zip(self.docs, self.doc_vectors, strict=True)
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]
