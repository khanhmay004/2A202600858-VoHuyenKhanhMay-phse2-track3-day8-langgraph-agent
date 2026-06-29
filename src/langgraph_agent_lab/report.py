"""Report generation helper.

render_report() turns a MetricsReport into a Vietnamese markdown report
(metrics tables + architecture + failure analysis + improvement plan).
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport

# >>> Edit these 3 values to match your submission <<<
STUDENT_NAME = "Vo Huyen Khanh May"
REPO_COMMIT = "(điền git commit hash)"
REPORT_DATE = "2026-06-29"


def render_report(metrics: MetricsReport) -> str:
    """Render a complete Vietnamese lab report from metrics data."""
    m = metrics
    lines: list[str] = []

    lines.append("# Báo cáo Lab Day 08 — LangGraph Agentic Orchestration (TỰ SINH)\n")
    lines.append(f"- **Sinh viên:** {STUDENT_NAME}")
    lines.append(f"- **Commit:** {REPO_COMMIT}")
    lines.append(f"- **Ngày:** {REPORT_DATE}\n")

    lines.append("## 1. Tổng quan metrics\n")
    lines.append(f"- Tổng scenario: **{m.total_scenarios}**")
    lines.append(f"- Success rate: **{m.success_rate:.0%}**")
    lines.append(f"- Trung bình node/scenario: **{m.avg_nodes_visited:.2f}**")
    lines.append(f"- Tổng retries: **{m.total_retries}**")
    lines.append(f"- Tổng interrupts (HITL): **{m.total_interrupts}**")
    lines.append(f"- Crash-resume thành công: **{m.resume_success}**\n")

    lines.append("## 2. Kết quả từng scenario\n")
    lines.append(
        "| Scenario | Expected | Actual | Success "
        "| Retries | Interrupts | Approval | Nodes |"
    )
    lines.append("|---|---|---|:--:|--:|--:|:--:|--:|")
    for s in m.scenario_metrics:
        ok = "✅" if s.success else "❌"
        appr = "yes" if s.approval_observed else "no"
        lines.append(
            f"| {s.scenario_id} | {s.expected_route} | {s.actual_route} | {ok} "
            f"| {s.retry_count} | {s.interrupt_count} | {appr} | {s.nodes_visited} |"
        )
    lines.append("")

    lines.append("## 3. Kiến trúc graph\n")
    lines.append(
        "Graph gồm 11 node: intake -> classify -> (route) -> ... -> finalize -> END. "
        "`classify_node` dùng LLM + structured output để chọn 1 trong 5 route "
        "(ưu tiên risky > tool > missing_info > error > simple). Vòng lặp retry "
        "`tool -> evaluate -> retry -> tool` bị giới hạn bởi `route_after_retry` "
        "(attempt < max_attempts); vượt giới hạn thì đi `dead_letter`. Route `risky` "
        "đi qua `risky_action -> approval` (HITL) trước khi thực thi. "
        "Mọi nhánh hội tụ tại `finalize -> END`.\n"
    )

    lines.append("## 4. State schema & reducers\n")
    lines.append("| Field | Reducer | Lý do |")
    lines.append("|---|---|---|")
    lines.append(
        "| route / risk_level / attempt / final_answer "
        "| overwrite | giữ trạng thái hiện tại |"
    )
    lines.append(
        "| evaluation_result / pending_question / proposed_action / approval "
        "| overwrite | giá trị mới nhất |"
    )
    lines.append("| messages / tool_results / errors / events | append (add) | nhật ký audit |")
    lines.append("")

    lines.append("## 5. Phân tích lỗi (failure modes)\n")
    lines.append(
        "1. **Tool fail tạm thời -> retry có giới hạn:** `tool_node` trả `ERROR` khi "
        "`route=='error'` và `attempt<2`; `evaluate_node` phát hiện và lặp lại tối đa "
        "`max_attempts` lần. Không lặp vô hạn nhờ `route_after_retry`."
    )
    lines.append(
        "2. **Hết retry -> dead_letter:** vượt `max_attempts` (vd S07 đặt `max_attempts=1`) "
        "thì escalate, vẫn trả `final_answer` rõ ràng cho khách."
    )
    lines.append(
        "3. **Hành động rủi ro thiếu duyệt:** route `risky` bắt buộc qua `approval`; "
        "nếu bị từ chối thì sang `clarify` thay vì thực thi mù quáng.\n"
    )

    lines.append("## 6. Persistence / recovery\n")
    lines.append(
        "Checkpointer được gắn khi compile; mỗi run dùng `thread_id` riêng "
        "(`thread-<scenario_id>`). Bản SQLite (`scripts/demo_resume.py`) chứng minh graph "
        "dừng tại `interrupt()`, sống sót qua 'crash' và `resume` đúng từ checkpoint trên "
        "đĩa; `get_state_history()` cho phép time-travel.\n"
    )

    lines.append("## 7. Kế hoạch cải tiến\n")
    lines.append("- Thay heuristic ở `evaluate_node` bằng LLM-as-judge có rubric.")
    lines.append("- Thêm fan-out song song (`Send`) khi cần gọi nhiều tool.")
    lines.append("- Idempotency key cho hành động rủi ro để tránh refund/delete trùng.")
    lines.append("- Circuit breaker + cảnh báo khi tỷ lệ vào dead_letter tăng.\n")

    return "\n".join(lines)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
