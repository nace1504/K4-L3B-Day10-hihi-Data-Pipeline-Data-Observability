# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Vũ Đình Thư |
| MSSV | 2A202602652 |
| Khóa/Lớp | K4 (K4-L3-DAY10) |
| Tên nhóm | hihi |
| Vai trò chính | Member — Observability & Evaluation |
| Repository | https://github.com/nace1504/K4-L3B-Day10-hihi-Data-Pipeline-Data-Observability/tree/main |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data quality và freshness | `src/observability/quality.py`: `run_data_quality_checks`, `build_freshness_report` | Cleaned pandas DataFrame, `Settings` | Quality JSON và freshness JSON | Hoàn thành |
| Evaluation test set | `src/evaluation/testset.py`: `build_test_set` | Cleaned DataFrame gồm metadata bài báo | `data/eval/test_set.json` có 10 câu hỏi | Hoàn thành |
| Markdown reporting | `src/observability/reporting.py`: hai hàm generate report | Metrics, quality và freshness dictionaries | Phase 1/corruption Markdown report | Hoàn thành |

Các phần việc này phụ thuộc vào cleaned dataset từ ingestion/cleaning. Output quality và test set là đầu vào cho evaluation, reporting và các pipeline tổng thể ở các bước sau.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra artifact đầu vào | Ingestion/cleaning | Xác minh 24 raw records, 24 clean rows, `paper_id` không trùng và clean JSON đọc được. |
| Ghi nhận dữ liệu category thiếu | Test-set integration | Dùng nhãn `Uncategorized` ở cleaned data để không tạo ground truth category rỗng. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| GX quality gate | `src/observability/quality.py`; `data/quality/test_quality_report.json` | `success=True`; 5 checks pass | Chạy `run_data_quality_checks` trên clean JSON |
| Freshness SLA | `data/quality/freshness_report.json` | `is_fresh=True`, stale rows = 0/24 | Kiểm tra `age_days > 180` với ngưỡng 25% |
| Test set | `data/eval/test_set.json` | 10 câu: summary 3, authors 3, date 2, categories 2 | `len(test_set) == 10` |
| Report generator | `src/observability/reporting.py` | Sinh Markdown UTF-8, thiếu key hiển thị `N/A` | Tạo report thử với string path |

Output cụ thể: `data/quality/test_quality_report.json` xác nhận row count 24, `paper_id` not-null/unique, `title` not-null và summary length 20–10,000 đều pass. Freshness report cho thấy published mới nhất là 2026-09-15, cũ nhất là 2026-04-01, không có record stale.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần một quality gate trước embedding/evaluation để phát hiện dữ liệu thiếu, trùng hoặc summary không hợp lệ. Đồng thời, dữ liệu có thể vẫn đúng schema nhưng đã cũ; vì vậy freshness cần được đo riêng bằng `age_days`. Evaluation cũng cần bộ câu hỏi cố định, có ground-truth document ID, để các lần chạy có thể so sánh công bằng.

### Cách triển khai

Quality module dùng Great Expectations 1.x với ephemeral context và pandas dataframe. Năm expectation được chạy cho row count, `paper_id` not null, `paper_id` unique, `title` not null và độ dài `summary`. Kết quả GX được chuyển thành dictionary JSON-safe; lỗi thiếu cột hoặc dtype được ghi thành một check fail thay vì làm hỏng cả report.

Freshness chuyển `age_days` sang numeric, tính số record vượt 180 ngày và stale ratio. Dataset chỉ fresh khi stale ratio không vượt 25%. Test set tạo theo thứ tự xác định 3 summary, 3 authors, 2 date và 2 categories; mỗi câu chứa title trong dấu nháy đơn để khớp exact-title lookup của `answer_question()`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | DataFrame có `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `age_days` |
| Output | Quality/freshness report dictionary, JSON artifacts, test set list 10 items |
| Module phụ thuộc | `core.utils.write_json`, `core.utils.write_text`, Great Expectations 1.x, pandas |
| Module sử dụng output | Evaluation metrics, reporting, phase/corruption pipeline |
| Điều kiện lỗi cần xử lý | Thiếu required column, field đáp án rỗng, dataset không đủ câu hỏi, missing metric key, report path truyền dạng string |

### Cách xác minh

```powershell
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); r=run_data_quality_checks(pd.read_json(s.paths.clean_json), s, 'test'); print(r['success'])"
```

- **Kết quả mong đợi:** `True` khi cleaned dataset đạt tất cả checks và freshness SLA.
- **Kết quả thực tế:** `True`; stale rows = 0/24 và `is_fresh=True`.
- **Artifact/log:** `data/quality/test_quality_report.json`, `data/quality/freshness_report.json`, `data/eval/test_set.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Crossref `subject` có thể vắng mặt; categories rỗng sẽ làm câu hỏi category có ground truth rỗng.
- **Các phương án đã cân nhắc:** (1) bỏ toàn bộ câu hỏi category; (2) tạo câu trả lời/category suy đoán từ summary; (3) dùng nhãn explicit `Uncategorized` trong cleaned data.
- **Phương án đã chọn:** Dùng `Uncategorized` cho record thiếu category, sau đó test set lấy đúng giá trị từ `categories_joined`.
- **Lý do:** Không bịa nội dung chuyên môn, vẫn duy trì schema ổn định và đủ bốn loại câu hỏi cho evaluation.
- **Bằng chứng quyết định phù hợp:** 24 records có category fallback; `build_test_set` tạo đủ 10 câu và không có ground truth rỗng.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `ValueError: Cannot create the required 2 categories questions: only 0 eligible rows have non-empty 'categories_joined'.`
- **Lệnh hoặc bước tái hiện:** Chạy `build_test_set(pd.read_json(s.paths.clean_json), s.paths.eval_testset)` khi dữ liệu Crossref không có `subject`.
- **Nguyên nhân gốc:** API response hiện có không cung cấp category cho 24 records nên `categories_joined` rỗng sau cleaning.
- **Cách xử lý:** Chuẩn hóa category trống thành `Uncategorized` ở bước cleaning và tạo lại clean JSON/test set.
- **Cách xác minh sau khi sửa:** Lệnh tạo test set trả về `10`; file `data/eval/test_set.json` tồn tại.
- **Điều học được:** Cần kiểm tra completeness của từng metadata field trước khi thiết kế evaluation data; valid schema không đồng nghĩa dữ liệu đủ cho mọi loại câu hỏi.

## 7. Hiểu biết về luồng end-to-end

1. Crossref payload được parse thành `PaperRecord`, lưu raw response/records; cleaning chuẩn hóa text, tính `age_days` và tạo `text_for_embedding`. Bước tiếp theo (chưa có artifact) là embedding và Chroma index.
2. Test set liên kết mỗi question với `ground_truth` và list `ground_truth_doc_ids`. Evaluation kiểm tra retrieved IDs có chứa đúng document và so sánh answer với ground truth qua token F1/judge.
3. Quality checks kiểm tra tính đầy đủ, uniqueness và validity tại một thời điểm. Freshness monitoring đo độ mới theo tỷ lệ `age_days` vượt SLA; dữ liệu có thể pass quality nhưng vẫn stale.
4. Dùng cùng test set giúp khác biệt giữa baseline, corrupted và repaired đến từ dữ liệu/index, không phải do bộ câu hỏi thay đổi.
5. Repair chỉ được xem là thành công khi corrupted/repaired artifacts và metrics cho thấy quality/freshness được phục hồi, đồng thời retrieval/answer metrics cải thiện gần baseline. Hiện chưa có artifacts này nên chưa thể kết luận.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | N/A | N/A | N/A | Chưa có index và baseline metrics artifact. |
| `mean_token_f1` | N/A | N/A | N/A | Chưa chạy evaluation. |
| `judge_accuracy` | N/A | N/A | N/A | Chưa chạy evaluation. |
| `mean_judge_score` | N/A | N/A | N/A | Chưa chạy evaluation. |
| Quality checks | Pass | N/A | N/A | 5 GX checks pass trên baseline clean data. |
| Freshness status | Fresh | N/A | N/A | 0/24 stale, stale ratio 0.0. |

### Kết luận từ số liệu

1. Chưa có corruption artifact nên không có bằng chứng định lượng cho chuỗi corruption → quality/freshness → agent metric.
2. Chưa có repaired artifact nên không có bằng chứng định lượng cho chuỗi repair → recovery.

Corruption ảnh hưởng rõ nhất: chưa xác định được vì corruption flow chưa chạy.

Kết quả khác với kỳ vọng ban đầu: Crossref subjects rỗng ở toàn bộ 24 records, nên category evaluation phải dùng nhãn fallback minh bạch thay vì category học thuật thực tế.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Data lineage từ raw snapshot đến clean artifact giúp tái tạo và kiểm tra pipeline dễ hơn.
2. Quality checks và freshness SLA bổ sung cho nhau: một bên bảo vệ contract, bên còn lại bảo vệ độ mới của tri thức.
3. Chất lượng metadata quyết định trực tiếp khả năng xây dựng evaluation; thiếu category có thể làm test set không đủ coverage.

### Nếu có thêm thời gian

Bổ sung nguồn/enrichment category đáng tin cậy cho Crossref records, sau đó chạy embedding/index và cùng một test set trên baseline, corrupted, repaired để đo chính xác retrieval hit rate, token F1 và recovery.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Vũ Đình Thư
**Ngày xác nhận:** 2026-09-26
