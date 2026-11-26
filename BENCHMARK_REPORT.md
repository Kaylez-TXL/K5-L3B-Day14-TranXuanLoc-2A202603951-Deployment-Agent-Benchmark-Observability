# Benchmark & Observability Report — Day 14

- **Họ tên** — Tran Xuan Loc
- **Ngày chạy** — 26/11/2026
- **Môi trường** — Windows, WSL2 và Docker Desktop. Load test và eval chạy qua loopback trong WSL2. Locust, agent và các dịch vụ observability chạy trong Docker Compose.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Ngưỡng mặc định của `load_test.py`, dùng để theo dõi nhóm request chậm. |
| Error rate `/ask` | ≤ 2% | Ngưỡng mặc định của `load_test.py`, theo dõi tỷ lệ request thất bại trong từng lần đo. |
| Accuracy trên golden dataset | ≥ 85% trong CI, 100% ở lần chấm cuối CP7 | CI chặn phiên bản chất lượng thấp. Lần kiểm tra cuối của bài lab yêu cầu đúng cả 23 câu và không có regression. |

Trong `/metrics`, lần gọi thử xuất hiện `http_requests_total` (Counter), `agent_in_flight_requests` (Gauge), `http_request_duration_seconds` và `agent_question_length_chars` (Histogram). Histogram độ dài có `_count=1` sau một câu hỏi. Label `route` lấy mẫu route, ví dụ `/ask`, và gom URL không khớp vào `unmatched` để số chuỗi thời gian tăng theo số route của app. [Mã đo metrics](06-lab-complete/benchmark-observability/develop/app.py)

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3,96 | 189,4 | 221,4 | 1706,2 | 1,67% | PASS |
| 10 | 33,47 | 190,2 | 1666,7 | 1705,5 | 0,33% | FAIL p95 |
| 50 | 111,21 | 191,8 | 227,9 | 329,3 | 1,33% | PASS |
| 100 | 80,95 | 293,6 | 2323,6 | 2471,8 | 0,67% | FAIL p95 |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Mỗi lượt gửi 300 request với `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`. RPS tăng từ 3,96 lên 111,21 khi tăng concurrency từ 1 lên 50. Ở concurrency 100, RPS giảm còn 80,95 và latency tăng. Kết quả cho thấy tăng concurrency không đem lại mức tăng RPS tuyến tính trong điều kiện đo này. Mẫu 300 request và độ trễ ngẫu nhiên của mock LLM có thể làm percentile giữa các lượt dao động. [c1](reports/load_v2_c1.json) · [c10](reports/load_v2_c10.json) · [c50](reports/load_v2_c50.json) · [c100](reports/load_v2_c100.json)

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 189,3 | 216,5 | 221,7 |
| 0.03 (mặc định) | 234,0 | 218,9 | 1712,4 |
| 0.1 | 333,4 | 1690,5 | 1714,0 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

Ở concurrency 20, khi tăng slow rate từ 0 lên 0,03, avg tăng 44,7 ms và p99 tăng từ 221,7 ms lên 1712,4 ms. Khi slow rate tăng tiếp lên 0,1, p95 lên 1690,5 ms. Avg gộp trải nghiệm của mọi request, nên nhóm nhỏ phải đợi lâu dễ bị che khuất. SLO p95 nêu rõ thời gian mà ít nhất 95% request phải đáp ứng, còn p99 quan sát nhóm chậm hơn. [Slow 0](reports/load_v2_slow_0.json) · [Slow 0.03](reports/load_v2_slow_0.03.json) · [Slow 0.1](reports/load_v2_slow_0.1.json)

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4,3% (1/23) | 91,3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 58,0 | 109,0 | 114,1 |
| Tổng cost (USD) | 0,000417 | 0,000760 | 0,000795 |
| Cost / câu đúng (USD) | 0,00041715 | 0,00003619 | 0,00003455 |
| Latency p95 (ms) | 1659,9 | 220,9 | 1536,8 |
| Quality gate | FAIL (ngưỡng 80%) | PASS (ngưỡng 80%) | PASS (ngưỡng 100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | token, hết hạn, chữ ký | Bổ sung tài liệu giải thích JWT có chữ ký số và thời hạn, rồi mô tả cách server kiểm tra cả hai. |
| `scaling-03` | cpu, memory, custom metrics | Bổ sung tài liệu về Kubernetes HPA và các chỉ số dùng để điều chỉnh số pod. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

V2 đưa thêm tài liệu vào prompt nên dùng nhiều token hơn mỗi câu. Đổi lại, số câu đúng tăng từ 1 lên 21, khiến chi phí trên mỗi câu đúng giảm. Sau khi bổ sung tài liệu, chi phí trên mỗi câu đúng giảm tiếp và hai câu còn thiếu đều đạt. Trong lượt eval cuối có hai request chậm xấp xỉ 1,7 giây. Bộ eval chỉ có 23 câu và vẫn dùng slow rate 0,03, nên mức chênh p95 giữa các lượt có thể chịu ảnh hưởng của mô phỏng độ trễ. Cả ba lượt dùng `MOCK_ERROR_RATE=0` để đo nội dung câu trả lời. [Eval v1](reports/eval_v1.json) · [Eval v2](reports/eval_v2.json) · [Eval v2 đã sửa](reports/eval_v2_fixed.json)

Trong CI, khởi động agent v2 và chạy `python eval/run_eval.py --min-accuracy 0.85 --baseline <report-của-bản-đã-duyệt>`. Script thoát với mã 1 nếu dưới ngưỡng hoặc có regression. Đặt job này là check bắt buộc trước khi merge để kết quả đó chặn pull request.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] [Dashboard Grafana khi Locust đang tạo tải](screenshots/grafana-dashboard.png)
- [x] [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png)
- [x] [Trace lỗi có event `exception` trong Jaeger](screenshots/jaeger-error-trace.png)
- [x] [Trang Alerts của Prometheus với hai alert cùng firing](screenshots/prometheus-alert-firing.png)

Trong khoảng tải ba agent, dashboard hiển thị **59,1 request/giây**, **0,69%** lỗi và **p95 294,18 ms** cho `/ask`. Truy vấn Prometheus tại mốc cuối của ảnh cho avg **234,44 ms**. Khoảng cách với p95 cho thấy nhóm request chậm cần chú ý dù trung bình thấp hơn. Ba instance nhận khoảng **19,74**, **19,80** và **19,59 request/giây**, tức phân tải khá đều trong mẫu quan sát. Input đạt khoảng **4.582 token/giây**, cao hơn output khoảng **2.413 token/giây** vì prompt v2 có thêm tài liệu truy xuất.

Nginx trả **404** với `GET /metrics`. Prometheus scrape trực tiếp endpoint nội bộ của ba agent nên vẫn có dữ liệu. Phép thử rule bằng `promtool test rules alert_rules_test.yml` báo `SUCCESS`.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 79 giây | Error rate, khoảng 18,4% khi lần đầu thấy firing. |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 140 giây | Latency p95, khoảng 1,90 giây khi lần đầu thấy firing. |

Hai thay đổi được áp dụng cùng lúc trên ba agent local và Locust tạo tải 30 users. Thời gian trong bảng tính từ lúc áp dụng cấu hình đến lần đầu thấy trạng thái `firing` qua API Prometheus, thăm dò mỗi 2,5 giây. Rule lỗi cần vượt 5% trong một phút. Rule độ trễ cần p95 vượt một giây trong hai phút. Thời gian quan sát còn gồm lúc tái tạo container, bắt đầu tạo tải và chờ chu kỳ đánh giá. [Alert rules](06-lab-complete/benchmark-observability/production/prometheus/alert_rules.yml) · [Ảnh hai alert cùng firing](screenshots/prometheus-alert-firing.png)

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Để phát hiện chất lượng giảm khi đổi sang v1, em sẽ chạy eval trên golden dataset ở mỗi lần phát hành và so accuracy với bản đã duyệt. Các rule hạ tầng dựa trên HTTP, thời gian xử lý, instance và chi phí. Chúng có thể vẫn nằm trong ngưỡng dù nhiều câu trả lời thiếu nội dung, như ở lượt eval v1.

### 4.3 Debug bằng trace

Trace chậm được chọn từ các log có `llm_ms` cao trong lúc Locust chạy:

- Trace ID `233b1f0f7c749051afd9c41d62d1962f`.
- Tổng thời gian **1.709,201 ms**.
- Trong các bước con của agent, `chat mock-llm-small` chậm nhất, **1.690,168 ms**, khoảng **98,9%** tổng thời gian.
- Dòng log `llm_call` có cùng trace ID.

```json
{"ts":"2026-11-26T14:38:25.780229+00:00","level":"INFO","service":"observable-agent","instance":"b49f0a7a12f1","event":"llm_call","trace_id":"233b1f0f7c749051afd9c41d62d1962f","span_id":"1a8bb1bcba4f83af","request_id":"b85ee2cef272","model":"mock-llm-small","agent_version":"v2","input_tokens":76,"output_tokens":39,"cost_usd":3.5e-05,"llm_ms":1689.9}
```

Trace lỗi `0aa7745f7a1a12740bc31a0ee9ef2c90` có event `exception` trong span `chat mock-llm-small`. Dòng log `llm_error` tương ứng xác nhận mock LLM trả lỗi upstream 503.

```json
{"ts":"2026-11-26T14:38:28.121973+00:00","level":"INFO","service":"observable-agent","instance":"b49f0a7a12f1","event":"llm_error","trace_id":"0aa7745f7a1a12740bc31a0ee9ef2c90","span_id":"ca3c08c51321e077","request_id":"ca45c48b2f77","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 59,68 | 190 | 250 | 1700 | 62/7870 (0,79%) |
| 3 | 62,15 | 190 | 220 | 1700 | 58/7923 (0,73%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Hai lượt cùng dùng 100 users, tốc độ tăng 10 users/giây và thời lượng 2 phút, với cấu hình độ trễ và lỗi mặc định. Bảng lấy dòng `Aggregated` từ CSV của Locust. Tăng từ một lên ba instance làm RPS tăng khoảng **4,1%** và p95 giảm từ 250 xuống 220 ms trong mẫu đo, còn p99 vẫn 1700 ms. Trace và panel LLM latency cho thấy các lượt mock LLM chạy chậm vẫn chi phối p99. Mỗi user Locust cũng có thời gian nghỉ giữa các lượt, nên kết quả phản ánh mức tải của kịch bản này. [CSV một instance](benchmark-results/scale_1_stats.csv) · [CSV ba instance](benchmark-results/scale_3_stats.csv)

---

## 6. Kết luận

1. Theo dõi cả p95 và p99 giúp nhận ra số ít request chậm bị che trong latency trung bình.
2. Đánh giá chất lượng và chi phí trên mỗi câu đúng giúp so sánh v1 và v2 ngay cả khi v2 dùng nhiều token hơn.
3. Grafana giúp khoanh vùng thời điểm có vấn đề. Jaeger cho biết bước nào chậm hoặc lỗi, rồi có thể dùng `trace_id` để tìm dòng log JSON tương ứng.

Khi triển khai thật, em sẽ bổ sung phép thử định kỳ từ bên ngoài qua cùng Nginx. Phép thử đo cả thời gian phản hồi và lỗi ở cổng vào, gồm những lỗi có thể chưa đi tới agent.
