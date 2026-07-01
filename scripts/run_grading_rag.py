"""Run the RAG grading dataset (data/grading_questions.json) and score it.

For each question:
  1. retrieve top-1 doc from the knowledge base (OpenAI embeddings + cosine),
  2. generate a grounded answer with the LLM using ONLY that doc,
  3. grade: must_contain_any / must_not_contain / top-1 doc == expect_top1_doc_id.

Writes outputs/grading_results.json and prints a summary table.
Makes real LLM calls (embeddings + one answer per question).
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from langgraph_agent_lab.llm import get_llm  # noqa: E402
from langgraph_agent_lab.retrieval import KBRetriever  # noqa: E402

DATASET = "data/grading_questions.json"
OUT_PATH = Path("outputs/grading_results.json")

RAG_SYSTEM = (
    "Bạn là trợ lý hỗ trợ nội bộ. CHỈ trả lời dựa trên tài liệu được cung cấp bên dưới. "
    "Nếu tài liệu không chứa thông tin, hãy nói 'Không có trong tài liệu'. "
    "Trả lời ngắn gọn bằng tiếng Việt, giữ nguyên các con số/đơn vị đúng như tài liệu."
)


def grounded_answer(llm, query: str, context_doc: str) -> str:
    human = f"Tài liệu:\n{context_doc}\n\nCâu hỏi: {query}\n\nTrả lời:"
    resp = llm.invoke([("system", RAG_SYSTEM), ("human", human)])
    return resp.content if hasattr(resp, "content") else str(resp)


def main() -> None:
    questions = json.loads(Path(DATASET).read_text(encoding="utf-8"))
    retriever = KBRetriever()
    llm = get_llm()

    results = []
    for q in questions:
        hits = retriever.retrieve(q["question"], k=3)
        top1 = hits[0]
        answer = grounded_answer(llm, q["question"], top1.text)
        low = answer.lower()

        must_any = q.get("must_contain_any") or []
        must_not = q.get("must_not_contain") or []
        contains_ok = (not must_any) or any(s.lower() in low for s in must_any)
        not_contains_ok = all(s.lower() not in low for s in must_not)
        retrieval_ok = top1.doc_id == q["expect_top1_doc_id"]
        passed = contains_ok and not_contains_ok and retrieval_ok

        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "expect_top1_doc_id": q["expect_top1_doc_id"],
                "actual_top1_doc_id": top1.doc_id,
                "retrieval_ok": retrieval_ok,
                "contains_ok": contains_ok,
                "not_contains_ok": not_contains_ok,
                "passed": passed,
                "answer": answer.strip(),
                "top3": [{"doc_id": h.doc_id, "score": round(h.score, 4)} for h in hits],
            }
        )
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {q['id']}: top1={top1.doc_id} (expect {q['expect_top1_doc_id']}) "
              f"contains={contains_ok} not_contains={not_contains_ok}")

    total = len(results)
    summary = {
        "total": total,
        "retrieval_accuracy": round(sum(r["retrieval_ok"] for r in results) / total, 4),
        "answer_pass_rate": round(
            sum(r["contains_ok"] and r["not_contains_ok"] for r in results) / total, 4
        ),
        "overall_pass_rate": round(sum(r["passed"] for r in results) / total, 4),
        "results": results,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n===== SUMMARY =====")
    print(f"total              = {summary['total']}")
    print(f"retrieval_accuracy = {summary['retrieval_accuracy']:.0%}")
    print(f"answer_pass_rate   = {summary['answer_pass_rate']:.0%}")
    print(f"overall_pass_rate  = {summary['overall_pass_rate']:.0%}")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
