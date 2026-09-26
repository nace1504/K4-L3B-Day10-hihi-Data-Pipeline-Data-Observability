# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4 (K4-L3B-Day10) |
| Tên nhóm | hihi |
| Repository | https://github.com/nace1504/K4-L3B-Day10-hihi-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| ---: | --- | --- | --- | --- |
| 1 | Doãn Hữu Nguyên | 2A202602671 | Trưởng nhóm — A: Data & Ingestion | `crossref.py`, `cleaning.py`, raw/clean data contract |
| 2 | Vũ Đình Thư | 2A202602652 | B: Observability & Evaluation | `quality.py`, `testset.py`, `reporting.py` |
| 3 | Lê Quang Ngọc | 2A202602664 | C: Pipeline & Corruption | `phase1.py`, `corruption.py`, `corruption_flow.py` |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành pipeline RAG data end-to-end từ snapshot Crossref đến cleaning, embedding MiniLM, ChromaDB, evaluation, observability, synthetic corruption và repair. Ingestion tạo 24 `PaperRecord`; cleaning giữ 24 dòng hợp lệ, duy nhất theo DOI, có `age_days` và `text_for_embedding` năm phần. Baseline dùng 10 câu hỏi thuộc bốn loại và đạt retrieval hit rate `1.0000`, Mean Token F1 `0.8816`; quality và freshness đều pass.

Corruption suite tiêm đủ sáu lỗi: drop năm records mới nhất, ba summary rỗng, ba summary nhiễu, ba title bị cắt, sáu records bị làm stale và ba duplicate rows. Quality gate phát hiện duplicate/summary lỗi; stale ratio tăng từ `4.17%` lên `45.45%`, khiến freshness fail. Drop latest ảnh hưởng rõ nhất vì các ground-truth documents của test set không còn trong corrupted index: hit rate giảm xuống `0.0000`, Token F1 còn `0.5537`. Repair không sửa chắp vá trên dữ liệu bẩn mà tái dựng từ raw snapshot, re-index và dùng lại đúng test set; toàn bộ quality, freshness và bốn metrics trở về baseline.

Giới hạn chính là lần đo cuối dùng `LLM_PROVIDER=mock`, nên judge sử dụng heuristic fallback và Ragas không bật. MiniLM vẫn là embedding thật. Ngoài ra, test set nhỏ và chọn deterministic từ đầu dataframe nên mức suy giảm nhạy với kịch bản drop latest.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref API / local snapshot
    -> parse PaperRecord + raw artifacts
    -> cleaning + data model
    -> MiniLM embeddings + ChromaDB baseline index
    -> shared evaluation set + baseline metrics
    -> GX quality gate + freshness SLA
    -> six deterministic corruptions
    -> corrupted index + metrics + observability
    -> rebuild from immutable raw records
    -> repaired index + metrics + comparison report
```

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref `/works` hoặc local snapshot | Retry 3 lần với backoff 1s/2s, fallback snapshot; parse DOI, text, metadata và ngày | `crossref_response.json`, `crossref_records.json` | Doãn Hữu Nguyên |
| Cleaning | `list[PaperRecord]`, UTC run date | Normalize, bỏ record lỗi, dedupe DOI, tính `age_days`, tạo embedding text | `papers_clean.csv/json` | Doãn Hữu Nguyên |
| Embedding/index | Clean dataframe | MiniLM normalized embeddings, ba Chroma collections riêng | `data/chroma/`, embedding manifests | Lê Quang Ngọc (tích hợp) |
| Evaluation | Clean dataframe/index | 10 câu hỏi, retrieval hit, Token F1, judge | Test set, answers và metrics JSON | Vũ Đình Thư |
| Observability | Dataframe và settings | GX 1.x expectations, stale ratio và Markdown reports | `data/quality/`, `data/reports/` | Vũ Đình Thư |
| Corruption/repair | Baseline dataframe và immutable raw records | Tiêm sáu lỗi, rebuild embedding text; repair từ raw rồi re-index | Corrupted/repaired data, log và metrics | Lê Quang Ngọc |
| Orchestration | Contracts của A/B/C | Điều phối baseline và three-state flow, kiểm tra test-set lineage | Toàn bộ artifacts CP3–CP5 | Lê Quang Ngọc |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng ở lần đo cuối |
| --- | --- |
| `LLM_PROVIDER` | `mock` |
| `LLM_MODEL` | Không dùng trong lần đo mock; cấu hình mặc định là `gemini-2.5-flash` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày; fail khi stale ratio > 25% |
| Corruption selection | Deterministic, không dùng random seed |

### Cài đặt và chạy

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:LLM_PROVIDER='mock'
python script/run_phase1.py
python script/run_corruption_flow.py
```

Nếu MiniLM đã được tải cache và môi trường demo không có mạng:

```powershell
$env:HF_HUB_OFFLINE='1'
```

| Lệnh | Trạng thái | Lần chạy xác minh | Bằng chứng |
| --- | --- | --- | --- |
| `python script/run_phase1.py` | Thành công, exit code 0 | 2026-09-26 | `baseline_metrics.json`, `phase1_report.md` |
| `python script/run_corruption_flow.py` | Thành công, exit code 0 | 2026-09-26 | `corruption_log.json`, three-state metrics, `corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API `/works`; lần chạy dùng local snapshot để tái lập |
| Query | `agentic retrieval augmented generation large language model` |
| Filter | `from-pub-date:<run_date - 180 days>,has-abstract:true` |
| Thời điểm snapshot | Không được ghi trong metadata nguồn; pipeline chạy ngày 2026-09-26 |
| Số records | 24 raw items → 24 raw records → 24 clean rows |
| Retry/backoff | Tối đa 3 lần; chờ 1s và 2s cho 429/503/lỗi mạng; fallback snapshot |

### Raw và clean schema

| Trường | Kiểu | Bắt buộc | Ý nghĩa | Xử lý thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | string | Có | DOI, document identity ổn định | Loại record; dedupe ở cleaning |
| `title` | string | Có | Tiêu đề paper | Normalize; loại record rỗng |
| `summary` | string | Có | Abstract đã bỏ JATS | Normalize; loại record rỗng |
| `authors_joined` | string | Không | Danh sách tác giả đã ghép | Chuẩn hóa, cho phép rỗng |
| `categories_joined` | string | Có cho category test | Subjects đã ghép | Fallback `Uncategorized` |
| `published` | ISO date string | Có cho freshness | Ngày công bố | Parse `date-parts`; fallback created |
| `age_days` | integer | Có | Tuổi record tại run date | Ngày lỗi thành missing và bị freshness tính stale |
| `text_for_embedding` | string | Có | Nội dung index | Build lại từ năm phần nguồn |

### Quy tắc cleaning

| Quy tắc | Dimension | Records bị tác động trong snapshot | Xác minh |
| --- | --- | ---: | --- |
| Bỏ tag JATS, normalize whitespace | Validity | 24 summaries được chuẩn hóa | Không còn markup `<...>` |
| Loại thiếu DOI/title/summary | Completeness | 0 | 24 items → 24 records |
| Dedupe `paper_id` | Uniqueness | 0 trong snapshot | 24/24 IDs unique |
| Tính `age_days` | Freshness | 24 | 1 record > 180 ngày ở lần chạy cuối |
| Build embedding text | Consistency | 24 | Đủ Title/Authors/Categories/Published/Summary |

`paper_id` dùng trực tiếp DOI để giữ identity xuyên suốt raw, clean, test set và index. `text_for_embedding` gồm năm dòng có nhãn rõ ràng. `age_days = run_date - published`, sử dụng UTC.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 |
| `question_type` | 3 summary, 3 authors, 2 date, 2 categories |
| Ground-truth IDs | DOI lấy từ `paper_id`; pipeline kiểm tra mọi ID thuộc clean snapshot |
| Embedding | `all-MiniLM-L6-v2`, normalized vectors |
| Vector store | ChromaDB; `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval | `top_k=4`, cosine space |
| Judge | `mock`/heuristic fallback ở lần đo cuối |
| Shared test set | `data/eval/test_set.json` |

Cùng một test set được dùng cho cả ba trạng thái. Nếu đổi câu hỏi hoặc ground truth giữa các lần chạy, chênh lệch metric có thể đến từ benchmark thay vì corruption. Baseline còn kiểm tra lineage và tự build lại test set nếu ground-truth IDs không thuộc snapshot hiện hành.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | 24 records |
| Clean dataset | `data/clean/papers_clean.{csv,json}` | Có | 24 rows |
| Embedding/index | `data/embeddings/`, `data/chroma/` | Có | Baseline/corrupted/repaired |
| Evaluation set | `data/eval/test_set.json` | Có | 10 câu, cùng lineage |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | 10 samples |
| Quality/freshness | `data/quality/` | Có | Ba trạng thái |
| Reports | `data/reports/` | Có | Phase 1 và comparison |

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | Cả 10 câu retrieve được ground-truth doc trong top 4 |
| `mean_token_f1` | 0.8816 | Mức trùng token trung bình cao với đáp án chuẩn |
| `judge_accuracy` | 1.0000 | Heuristic judge đánh dấu đúng 10/10 |
| `mean_judge_score` | 4.4000 | Điểm trung bình trên thang 1–5 |
| Ragas | N/A | Không bật `RUN_RAGAS`; tránh ghi số liệu chưa chạy |

## 8. Data quality và freshness

| Check | Dimension | Ngưỡng | Baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| Row count | Completeness | 1–24 | Pass: 24 | `baseline_quality_report.json` |
| `paper_id` not null | Completeness | 100% | Pass: 0 unexpected | Cùng artifact |
| `paper_id` unique | Uniqueness | 100% | Pass: 0 duplicate | Cùng artifact |
| `title` not null | Completeness | 100% | Pass | Cùng artifact |
| Summary length | Validity | 20–10,000 | Pass: 0 unexpected | Cùng artifact |

| Freshness property | Baseline value |
| --- | --- |
| Dataset | Clean dataframe trước embedding |
| Latest/oldest published | 2026-07-22 / 2026-03-28 |
| Threshold | `age_days > 180`; fail nếu stale ratio > 25% |
| Result | Fresh: 1/24 stale (`4.17%`) |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Records | Signal/tác động thực tế | Repair |
| --- | --- | ---: | --- | --- |
| Drop latest | Xóa 20% records mới nhất | 5 | Ground-truth docs biến mất; hit rate về 0 | Rebuild từ raw |
| Blank summary | Gán chuỗi rỗng | 3 | Summary-length expectation fail | Rebuild từ raw |
| Inject noise | Thêm garbage tokens lặp lại | 3 | Nhiễu content/vector | Rebuild từ raw |
| Truncate title | Đổi title thành `BAD` | 3 | Làm mất exact-title lookup | Rebuild từ raw |
| Stale date | Đặt ngày `2000-01-01`, tính lại age | 6 | Cùng stale duplicates tạo 10/22 stale; freshness fail | Rebuild từ raw |
| Duplicate rows | Append rows giữ nguyên DOI | 3 | 6 unexpected rows trong uniqueness check | Dedupe qua clean rebuild |

`data/results/corruption_log.json` có đủ sáu loại, count, affected `paper_id`, mô tả và input/output row count. Repair đọc lại `crossref_records.json`, gọi cùng cleaning function của baseline rồi build collection mới. Vì không sử dụng corrupted dataframe làm nguồn, records đã drop và metadata bị ghi đè đều được phục hồi; chạy lặp lại cho cùng raw snapshot tạo cùng clean corpus.

## 10. So sánh ba trạng thái

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi corruption | Phục hồi | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.0000 | 1.0000 | -1.0000 | 100% | Ground-truth docs bị drop, rồi phục hồi |
| `mean_token_f1` | 0.8816 | 0.5537 | 0.8816 | -0.3279 | 100% | Answer quality giảm rồi về baseline |
| `judge_accuracy` | 1.0000 | 0.6000 | 1.0000 | -0.4000 | 100% | 4/10 câu bị ảnh hưởng |
| `mean_judge_score` | 4.4000 | 3.2000 | 4.4000 | -1.2000 | 100% | Phục hồi đúng baseline |
| Quality | Pass | Fail | Pass | Duplicate và summary lỗi | Hoàn toàn | `True → False → True` |
| Freshness | Pass | Fail | Pass | 4.17% → 45.45% stale | Hoàn toàn | `True → False → True` |

Hai quan hệ nhân quả có bằng chứng:

1. Drop latest làm các ground-truth DOI biến mất, đồng thời blank summary/duplicate/stale date làm quality và freshness fail → hit rate giảm `1.0 → 0.0`, Token F1 giảm `0.8816 → 0.5537`.
2. Rebuild từ immutable raw records khôi phục 24 clean unique rows và stale ratio `4.17%` → quality/freshness pass và cả bốn metrics trở lại chính xác baseline.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** baseline chạy được nhưng retrieval hit rate bằng `0.0000`.
- **Nguyên nhân:** `test_set.json` được merge từ một snapshot Crossref khác; ba ground-truth IDs không giao với 24 clean IDs hiện tại.
- **Cách xử lý:** thêm kiểm tra lineage trong `phase1.py`; mọi ground-truth ID phải thuộc dataset hiện hành, nếu không test set được build lại.
- **Cách xác minh:** sau sửa, overlap hợp lệ và baseline hit rate đạt `1.0000`; cùng test set sau đó được tái sử dụng cho corrupted/repaired.

Blocker môi trường khi tải model là lỗi SSL certificate trên máy Windows. Nhóm xác minh HTTPS bằng Windows certificate store, tải model một lần, sau đó dùng `HF_HUB_OFFLINE=1` cho lần chạy tái lập. Cảnh báo cleanup thư mục tạm Windows không làm pipeline fail; cả hai entrypoint kết thúc exit code 0.

## 12. Giới hạn và hướng cải thiện

| Giới hạn | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Test set chỉ có 10 câu và tái dùng một số papers | Metric nhạy với việc drop nhóm records đầu | Sampling phân tầng theo thời gian/category; chạy nhiều seeds và báo mean/std |
| Judge cuối dùng heuristic mock | Không phản ánh đầy đủ đánh giá ngữ nghĩa của LLM | Chạy lại với provider thật, lưu model/version và so sánh với heuristic |
| Ragas chưa chạy | Thiếu faithfulness/context metrics | Bật `RUN_RAGAS=1`, lưu artifact và thời gian chạy |
| Snapshot chưa có ingest timestamp | Khó audit tuổi của chính snapshot | Thêm lineage manifest gồm fetched_at, source mode và record counts |
| Title corruption chưa có expectation độ dài riêng | Được phản ánh qua retrieval nhưng không có signal GX độc lập | Thêm title-length expectation và test corrupted value `<8` |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và báo cáo cá nhân.
- [x] Hai entrypoint đã được chạy lại trên phiên bản hiện tại.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp các file trong `data/results/`.
- [x] Kết luận quality/freshness khớp `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact tồn tại.
- [x] Ba thành viên có báo cáo cá nhân riêng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
