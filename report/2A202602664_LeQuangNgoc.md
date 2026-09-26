# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Lê Quang Ngọc |
| MSSV | 2A202602664 |
| Khóa/Lớp | K4 (K4-L3B-Day10) |
| Tên nhóm | hihi |
| Vai trò chính | C — Pipeline & Corruption |
| Repository | https://github.com/nace1504/K4-L3B-Day10-hihi-Data-Pipeline-Data-Observability.git |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Baseline orchestration | `src/pipelines/phase1.py::main` | Raw records và cấu hình project | Clean dataset, Chroma index, baseline metrics, quality/freshness và Phase 1 report | Hoàn thành |
| Synthetic corruption suite | `src/ingestion/corruption.py::corrupt_clean_dataframe` | Clean dataframe | Corrupted dataframe và `corruption_log.json` ghi đủ 6 kịch bản | Hoàn thành |
| Corruption, repair và comparison | `src/pipelines/corruption_flow.py::main` | Baseline artifacts, shared test set và raw records | Corrupted/repaired artifacts, metrics và comparison report | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Tích hợp module A/B | Ingestion, cleaning, evaluation và observability | Phát hiện test set cũ không cùng lineage với cleaned dataset; bổ sung kiểm tra document IDs và tự build lại test set |
| Xác minh báo cáo B | `observability/reporting.py` | Truyền quality/freshness baseline vào comparison report để không còn giá trị `N/A` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Nối pipeline baseline | `src/pipelines/phase1.py` | 24 documents, 10 evaluation samples và đầy đủ artifacts CP3 | `python script/run_phase1.py` |
| Tiêm lỗi có thể tái lập | `src/ingestion/corruption.py` | 6 loại lỗi, 24 input rows và 22 output rows | `data/results/corruption_log.json` |
| Repair từ immutable raw records | `src/pipelines/corruption_flow.py` | Repaired dataset trở lại 24 dòng và metric bằng baseline | `python script/run_corruption_flow.py` |
| So sánh ba trạng thái | `data/reports/corruption_report.md` | Bảng Baseline/Corrupted/Repaired gồm 4 metrics và quality/freshness | Đọc report và ba file metrics JSON |

Output nổi bật là `data/reports/corruption_report.md`: corrupted hit rate giảm từ `1.0000` xuống `0.0000`, sau repair trở lại `1.0000`; quality chuyển `True → False → True`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần C phải kết nối các module độc lập thành hai luồng chạy được: baseline và corruption/repair. Luồng thứ hai phải tạo lỗi dữ liệu có chủ đích, đo tác động trên cùng test set, rồi tái dựng dữ liệu từ raw records để chứng minh khả năng phục hồi thay vì sửa trực tiếp dữ liệu bẩn.

### Cách triển khai

Baseline tải raw records, clean và lưu CSV/JSON, build collection `papers-baseline`, xác minh evaluation set thuộc đúng snapshot, evaluate, chạy quality/freshness gate và sinh report. Kiểm tra lineage lấy hợp các `ground_truth_doc_ids` và yêu cầu chúng là tập con của `paper_id` hiện tại; test set sai lineage sẽ được build lại.

Corruption tạo bản sao dataframe để không sửa baseline, rồi tiêm tuần tự 6 lỗi deterministic:

1. Xóa 20% records mới nhất.
2. Làm rỗng summary.
3. Chèn noise vào summary.
4. Cắt title còn `BAD`.
5. Đưa published date về `2000-01-01` và tính lại `age_days`.
6. Nhân bản rows nhưng giữ nguyên `paper_id`.

Sau khi thay đổi các cột nguồn, pipeline build lại `text_for_embedding`, ghi audit log, tạo index riêng và evaluate. Repair luôn đọc lại `crossref_records.json`, chạy lại cleaning và build collection `papers-repaired`; thao tác này idempotent vì không dùng corrupted dataframe làm nguồn phục hồi.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `PaperRecord`, cleaned dataframe có `paper_id`, `title`, `summary`, metadata, `age_days`, `text_for_embedding`; shared test set gồm ground truth IDs |
| Output | Clean/corrupted/repaired CSV và JSON, ba Chroma collections, metrics, answers, quality/freshness JSON, corruption log và Markdown reports |
| Module phụ thuộc | `ingestion.crossref`, `ingestion.cleaning`, `evaluation.testset`, `evaluation.metrics`, `observability.quality`, `observability.reporting`, `retrieval.index` |
| Module sử dụng output | Entrypoints trong `script/`, báo cáo nhóm và live demo |
| Điều kiện lỗi cần xử lý | Raw/test set rỗng, thiếu cột bắt buộc, test set khác lineage, baseline artifacts chưa tồn tại, repair tạo dataframe rỗng |

### Cách xác minh

```powershell
$env:HF_HUB_OFFLINE='1'
$env:LLM_PROVIDER='openai'
$env:LLM_MODEL='gpt-4o-mini'
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** baseline đạt chất lượng cao; corruption làm quality/metrics giảm; repair khôi phục dữ liệu và metrics.
- **Kết quả thực tế:** cả hai lệnh exit code `0`; baseline và repaired có cùng bốn metrics, corrupted giảm ở cả bốn metrics.
- **Artifact/log:** `data/results/*.json`, `data/quality/*.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`.

Số liệu đo bằng LLM_PROVIDER=openai (gpt-4o-mini), không phải mock. Ragas được giữ ở trạng thái skipped vì `RUN_RAGAS` không được bật.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Repair có thể sửa từng lỗi trên corrupted dataframe hoặc tái dựng từ raw artifact.
- **Các phương án đã cân nhắc:** (1) đảo ngược từng mutation; (2) rebuild hoàn toàn từ raw records bất biến.
- **Phương án đã chọn:** rebuild từ `data/raw/crossref_records.json` bằng chính hàm cleaning của baseline.
- **Lý do:** đảo mutation dễ bỏ sót, phụ thuộc thứ tự lỗi và không phục hồi được records đã drop. Rebuild từ raw đơn giản hơn, giữ lineage rõ ràng và idempotent.
- **Bằng chứng quyết định phù hợp:** repaired có 24 records, quality `True`, stale ratio `4.17%`; toàn bộ bốn metrics khớp baseline chính xác.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** baseline chạy thành công nhưng `retrieval_hit_rate: 0.0000`.
- **Lệnh hoặc bước tái hiện:** chạy `python script/run_phase1.py` sau khi merge artifact `data/eval/test_set.json` từ nhánh khác.
- **Nguyên nhân gốc:** ba ground-truth document IDs trong test set có độ giao bằng 0 với 24 `paper_id` của cleaned snapshot. Pipeline trước đó chỉ kiểm tra file test set có tồn tại, không kiểm tra lineage.
- **Cách xử lý:** thêm `_test_set_matches_dataset()` trong `phase1.py`; nếu ID không phải tập con của dataset hiện hành thì tự build lại test set trước evaluation.
- **Cách xác minh sau khi sửa:** baseline hit rate tăng từ `0.0000` lên `1.0000`, Token F1 đạt `0.8816`.
- **Điều học được:** artifact tồn tại không đồng nghĩa artifact hợp lệ; pipeline cần kiểm tra quan hệ lineage giữa dữ liệu và evaluation set.

Một blocker môi trường khác là lỗi SSL khi tải MiniLM. Kết nối được xác minh bằng Windows certificate store qua `truststore`; sau khi model được cache, các lần đo cuối chạy với `HF_HUB_OFFLINE=1` để tái lập và không phụ thuộc mạng.

## 7. Hiểu biết về luồng end-to-end

1. Crossref payload được parse thành `PaperRecord`, lưu raw artifacts, làm sạch/khử trùng lặp, tạo `text_for_embedding`, rồi MiniLM sinh vector để nạp vào ChromaDB.
2. Mỗi câu hỏi có đáp án chuẩn và `ground_truth_doc_ids`. Retrieval hit khi danh sách docs trả về chứa ID chuẩn; câu trả lời được so bằng Token F1 và judge.
3. Quality checks kiểm tra cấu trúc/nội dung như row count, null, unique và độ dài summary. Freshness giám sát tuổi dữ liệu theo `age_days` và chỉ fail khi stale ratio vượt 25%.
4. Dùng cùng test set giúp sự thay đổi metric phản ánh trạng thái dữ liệu/index, không phải do đổi câu hỏi hay ground truth.
5. Repair thành công khi clean artifacts được tái tạo từ raw, quality trở lại pass, freshness trở lại mức baseline và metrics repaired khôi phục về baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.0000 | 1.0000 | Corruption loại khỏi index toàn bộ ground-truth docs được chọn; repair khôi phục hoàn toàn |
| `mean_token_f1` | 0.8816 | 0.5537 | 0.8816 | Câu trả lời corrupted vẫn có một phần token chung nhưng giảm 0.3279 |
| `judge_accuracy` | 0.7000 | 0.5000 | 0.7000 | LLM judge (gpt-4o-mini) chấm đúng 7/10 → 5/10 → 7/10 |
| `mean_judge_score` | 4.3000 | 3.3000 | 4.3000 | Giảm 1.0 điểm rồi khôi phục hoàn toàn |
| Quality checks | True | False | True | Duplicate IDs và 3 summary rỗng làm quality gate fail |
| Freshness status | True (1/24 stale, 4.17%) | False (10/22 stale, 45.45%) | True (1/24 stale, 4.17%) | Corruption vượt ngưỡng stale 25%; repair khôi phục SLA |

### Kết luận từ số liệu

1. Drop latest + các mutation nội dung/duplicate → quality `True → False`, freshness `True → False` với stale ratio `4.17% → 45.45%` → hit rate `1.0 → 0.0`, Token F1 `0.8816 → 0.5537`.
2. Rebuild từ raw records → quality `False → True`, stale ratio về `4.17%` → cả bốn agent metrics trở lại đúng baseline.

Corruption ảnh hưởng rõ nhất là **drop latest records**. Test set deterministic chọn các paper mới ở đầu cleaned dataframe; năm records mới nhất bị drop làm các ground-truth docs không còn trong corrupted index, trực tiếp khiến retrieval hit rate bằng 0.

Kết quả ban đầu khác kỳ vọng là freshness corrupted vẫn `True` vì chỉ có 5/22 rows stale (`22.73%`). Mình điều chỉnh kịch bản stale-date để ít nhất 30% số rows còn lại bị làm cũ; cùng các duplicated stale rows, artifact cuối ghi nhận 10/22 rows stale (`45.45%`). Freshness gate vì vậy fail đúng SLA `>25%`, đồng thời uniqueness và summary-length checks cũng fail độc lập.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Orchestration phải kiểm tra lineage và contract, không chỉ kiểm tra file có tồn tại.
2. Data quality gate và freshness là hai tín hiệu bổ sung: dữ liệu có thể fail quality trong khi vẫn pass freshness.
3. Một thay đổi upstream như drop documents có thể làm retrieval sụp đổ dù ứng dụng và model không báo lỗi kỹ thuật.

### Nếu có thêm thời gian

Mình sẽ tách evaluation documents đều hơn theo thời gian và thêm pytest cho invariants của corruption/repair. Cải thiện được đo bằng coverage trên sáu corruption scenarios, kiểm tra repair idempotency qua hai lần chạy liên tiếp, và so sánh độ nhạy metric trên nhiều test-set sampling seeds.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Lê Quang Ngọc  
**Ngày xác nhận:** 2026-09-26
