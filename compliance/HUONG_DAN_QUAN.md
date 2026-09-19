# Hướng dẫn khởi động phần việc của Quân
### (Business Analyst / Kiểm soát tuân thủ dạng mã – Compliance-as-Code)

> **Kết luận trước:** Quân **bắt đầu ngay tuần 1, không đợi ai.** Việc của Quân
> nằm ở *đầu* chuỗi phụ thuộc (thiết kế SoT) và phần lớn có thể làm song song
> nhờ **dữ liệu mẫu (golden config)**. Bộ khung trong thư mục này đã **chạy được**.

---

## 1. Vì sao không phải đợi Chung/Tùng

Cả nhóm nối với nhau qua **hợp đồng dữ liệu** chứ không qua code hoàn thiện:

| Hợp đồng dữ liệu | Ai chủ trì | Ai tiêu thụ |
|---|---|---|
| **SoT** – lược đồ thiết bị (`sot/devices.yaml`) | **Quân** | Chung (render Jinja2), Tùng |
| **Policy** – luật CIS (`policy/cis_rules.yaml`) | **Quân** | Tùng (đối chiếu hardening) |
| **Định dạng báo cáo** (`reports/compliance.json`) | **Quân** | Cả nhóm (đánh giá) |

Quân **chốt 3 giao diện này sớm** → Chung và Tùng cứ thế làm, còn Quân phát triển
công cụ trên **golden config** (cấu hình mẫu tự dựng) mà không cần chờ output thật.

### Bản đồ phụ thuộc
```
Tuần:   1─────2─────3(M1)──4─────5─────6─────7(M2)──8─────9─────10
Quân:  SoT + Policy + Tool chấm điểm (test bằng golden config)  ─┐
                                                                ├─► tích hợp
Chung:      (cần SoT) → Jinja2 → role → config THẬT ────────────┤   + đo
Tùng:            (cần policy) → hardening → tấn công đối chứng ──┘
        └── LÀM SONG SONG, gặp nhau ở điểm tích hợp tuần 5 và 8 ──┘
```
Điểm **phải chờ** (chỉ 2 mốc): config thật của Chung (≈tuần 5) và kết quả
hardening của Tùng (≈tuần 8) để chấm điểm đối chứng trước/sau.

---

## 2. Chạy thử bộ khung ngay bây giờ (5 phút)

```bash
cd "D:\ĐATN\Ansible Python\quan-compliance"

python -m venv .venv
.venv\Scripts\activate            # Windows;  Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

python tools\score.py             # chấm điểm trên configs/golden
```
Kết quả in ra bảng, đồng thời sinh 2 file trong `reports/`:
- `compliance.json` – dữ liệu thô (để tích hợp/đo lường).
- `compliance.html` – **dashboard trực quan** (mở bằng trình duyệt).

Kết quả mẫu: `leaf1` (chưa hardening) = **46.2%**, `core1` (đã hardening) = **100%**,
toàn hệ thống **75.4%**. Đây chính là *minh chứng công cụ phát hiện vi phạm*.

---

## 3. Cấu trúc thư mục & vai trò từng file

```
quan-compliance/
├─ sot/devices.yaml          # Nguồn dữ liệu tin cậy (hợp đồng #1)
├─ policy/cis_rules.yaml     # Bộ luật CIS dạng mã (hợp đồng #2)
├─ configs/
│  ├─ golden/*.cfg           # cấu hình MẪU để test khi chưa có đồ thật
│  └─ live/*.cfg             # cấu hình THẬT do Chung sinh (đặt vào đây sau)
├─ tools/score.py            # công cụ chấm điểm + sinh báo cáo
├─ reports/                  # kết quả (json + html dashboard)
└─ requirements.txt
```

**Cách công cụ hoạt động** (đọc `tools/score.py`):
1. Đọc `devices.yaml` → danh sách thiết bị + `os`.
2. Đọc `cis_rules.yaml` → mỗi luật có `check.type` (`must_contain` /
   `must_not_contain`) và `pattern` (regex).
3. Với mỗi thiết bị, đọc `configs/<nguồn>/<tên>.cfg`, **bỏ dòng chú thích**,
   rồi kiểm tra từng luật áp dụng (`applies_to`).
4. Tính **điểm có trọng số** theo mức nghiêm trọng (high=5, medium=3, low=1):
   `điểm = tổng trọng số luật ĐẠT / tổng trọng số luật áp dụng × 100`.
5. Xuất JSON + HTML.

---

## 4. Kế hoạch 10 tuần – việc cụ thể từng tuần

| Tuần | Việc của Quân | Cần ai? |
|---|---|---|
| **1** | Dựng repo Git, chốt cấu trúc thư mục; viết `devices.yaml` đầu tiên (2 thiết bị) | Độc lập |
| **2** | Hoàn thiện lược đồ SoT + **chốt 3 hợp đồng dữ liệu** với cả nhóm; viết golden config | Họp nhóm chốt |
| **3 (M1)** | Mã hóa thêm luật CIS (mục tiêu ~15–20 luật); báo cáo mốc M1 | Độc lập |
| **4** | Định nghĩa **định dạng báo cáo tuân thủ** (chốt JSON schema với Chung, Tùng) | Chốt với nhóm |
| **5** | Mở rộng `score.py`: thu thập cấu hình thật; bắt đầu nhận `configs/live` từ Chung | Cần config Chung |
| **6 (chuẩn bị M2)** | Hoàn thiện chấm điểm + danh sách vi phạm (KB-11); diễn tập trên lab | Độc lập |
| **7 (M2)** | Dashboard tuân thủ theo thiết bị & theo thời gian; báo cáo giữa kỳ | Độc lập |
| **8** | Khung đo lường + tích hợp **Batfish** kiểm chứng tiền triển khai (mở rộng) | Độc lập |
| **9** | Chấm điểm **đối chứng trước/sau** hardening; tổng hợp số liệu cả nhóm | Cần đồ Tùng |
| **10** | Chủ biên thuyết minh chung; tích hợp; chuẩn bị slide & demo bảo vệ | Cả nhóm |

---

## 5. Cách mở rộng (làm gì tiếp theo)

### 5.1. Thêm luật CIS mới
Mở `policy/cis_rules.yaml`, thêm một khối:
```yaml
  - id: CIS-7.1
    title: "Tắt HTTP server (chỉ dùng HTTPS)"
    severity: medium
    applies_to: all
    check:
      type: must_not_contain
      pattern: '(?im)^\s*ip http server'
    remediation: "Tắt HTTP, bật HTTPS cho giao diện quản trị."
    clo: [CLO2]
```
Chạy lại `score.py` là có ngay. **Không phải sửa code** — đây là điểm mạnh của
compliance-as-code: luật là *dữ liệu*, không phải *lệnh*.

### 5.2. Thêm thiết bị
Thêm khối vào `sot/devices.yaml` và đặt file `configs/golden/<tên>.cfg`.

### 5.3. Khi Chung có config thật
Chung xuất cấu hình đã triển khai vào `configs/live/<tên>.cfg`, rồi:
```bash
python tools\score.py --configs configs\live
```
So sánh điểm `golden` (trước) với `live` (sau hardening) → ra **số liệu đối chứng**
cho phần đánh giá.

### 5.4. Nâng cấp cách kiểm tra (giai đoạn sau)
Hiện tại kiểm bằng **regex trên text** — đủ để bắt đầu và demo. Khi vững, có thể
nâng lên: (a) parse cấu hình có cấu trúc (JSON từ NAPALM/`gnmic`), (b) tích hợp
**Batfish** để kiểm chứng *hành vi* mạng trước khi triển khai (KB-15).

---

## 6. 4 việc làm ngay trong tuần này (checklist)

- [ ] Tạo repo Git nhóm, đẩy thư mục `quan-compliance/` lên.
- [ ] Chỉnh `sot/devices.yaml` cho khớp lab thật (IP, tên thiết bị) và gửi Chung duyệt.
- [ ] Viết thêm 5–10 luật CIS vào `policy/cis_rules.yaml`.
- [ ] Gửi `reports/compliance.json` cho cả nhóm làm chuẩn "định dạng báo cáo".

> Khi Chung ra playbook chạy thật, Quân đã có sẵn công cụ chấm điểm để cắm vào —
> **không mất tuần nào để chờ.**
