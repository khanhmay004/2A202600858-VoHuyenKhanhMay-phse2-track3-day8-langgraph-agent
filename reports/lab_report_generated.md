# Báo cáo Lab Day 08 — LangGraph Agentic Orchestration (TỰ SINH)

- **Sinh viên:** Vo Huyen Khanh May
- **Commit:** (điền git commit hash)
- **Ngày:** 2026-06-29

## 1. Tổng quan metrics

- Tổng scenario: **7**
- Success rate: **100%**
- Trung bình node/scenario: **6.43**
- Tổng retries: **3**
- Tổng interrupts (HITL): **2**
- Crash-resume thành công: **True**

## 2. Kết quả từng scenario

| Scenario | Expected | Actual | Success | Retries | Interrupts | Approval | Nodes |
|---|---|---|:--:|--:|--:|:--:|--:|
| S01_simple | simple | simple | ✅ | 0 | 0 | no | 4 |
| S02_tool | tool | tool | ✅ | 0 | 0 | no | 6 |
| S03_missing | missing_info | missing_info | ✅ | 0 | 0 | no | 4 |
| S04_risky | risky | risky | ✅ | 0 | 1 | yes | 8 |
| S05_error | error | error | ✅ | 2 | 0 | no | 10 |
| S06_delete | risky | risky | ✅ | 0 | 1 | yes | 8 |
| S07_dead_letter | error | error | ✅ | 1 | 0 | no | 5 |

## 3. Kiến trúc graph

Graph gồm 11 node: intake -> classify -> (route) -> ... -> finalize -> END. `classify_node` dùng LLM + structured output để chọn 1 trong 5 route (ưu tiên risky > tool > missing_info > error > simple). Vòng lặp retry `tool -> evaluate -> retry -> tool` bị giới hạn bởi `route_after_retry` (attempt < max_attempts); vượt giới hạn thì đi `dead_letter`. Route `risky` đi qua `risky_action -> approval` (HITL) trước khi thực thi. Mọi nhánh hội tụ tại `finalize -> END`.

## 4. State schema & reducers

| Field | Reducer | Lý do |
|---|---|---|
| route / risk_level / attempt / final_answer | overwrite | giữ trạng thái hiện tại |
| evaluation_result / pending_question / proposed_action / approval | overwrite | giá trị mới nhất |
| messages / tool_results / errors / events | append (add) | nhật ký audit |

## 5. Phân tích lỗi (failure modes)

1. **Tool fail tạm thời -> retry có giới hạn:** `tool_node` trả `ERROR` khi `route=='error'` và `attempt<2`; `evaluate_node` phát hiện và lặp lại tối đa `max_attempts` lần. Không lặp vô hạn nhờ `route_after_retry`.
2. **Hết retry -> dead_letter:** vượt `max_attempts` (vd S07 đặt `max_attempts=1`) thì escalate, vẫn trả `final_answer` rõ ràng cho khách.
3. **Hành động rủi ro thiếu duyệt:** route `risky` bắt buộc qua `approval`; nếu bị từ chối thì sang `clarify` thay vì thực thi mù quáng.

## 6. Persistence / recovery

Checkpointer được gắn khi compile; mỗi run dùng `thread_id` riêng (`thread-<scenario_id>`). Bản SQLite (`scripts/demo_resume.py`) chứng minh graph dừng tại `interrupt()`, sống sót qua 'crash' và `resume` đúng từ checkpoint trên đĩa; `get_state_history()` cho phép time-travel.

## 7. Kế hoạch cải tiến

- Thay heuristic ở `evaluate_node` bằng LLM-as-judge có rubric.
- Thêm fan-out song song (`Send`) khi cần gọi nhiều tool.
- Idempotency key cho hành động rủi ro để tránh refund/delete trùng.
- Circuit breaker + cảnh báo khi tỷ lệ vào dead_letter tăng.
