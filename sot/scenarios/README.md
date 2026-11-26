# Kịch bản quy mô cho công cụ chấm điểm

Ba tệp SoT ở thư mục này dùng để **chạy thử `score.py` ở các quy mô 3, 9 và 12 thiết bị** mà không cần dựng thêm thiết bị trong lab.

Ansible, `run.sh` và dashboard mặc định **vẫn dùng `sot/devices.yaml`** (6 thiết bị). Các tệp ở đây được dùng theo hai cách: chấm điểm trên cấu hình giả lập qua tham số `--sot` của `score.py`, hoặc **deploy thật trên lab** bằng `./run.sh scale-lab` (xem cuối tệp).

## Thành phần

| Tệp / thư mục | Nội dung |
|---|---|
| `devices_3.yaml` | edge1 → spine1 → leaf1 (1 edge, 1 spine, 1 leaf) |
| `devices_9.yaml` | 6 thiết bị của lab (Pod A) + edge2 → spine3 → leaf4 |
| `devices_12.yaml` | Pod A + Pod B đầy đủ (edge2, spine3–4, leaf4–6) |
| `compliance/configs/scale_before/` | 12 tệp `.cfg` trước chuẩn hóa, nhân bản từ `configs/golden` |
| `compliance/configs/scale_after/` | 12 tệp `.cfg` sau chuẩn hóa, nhân bản từ `configs/after` |
| `scripts/gen_scenarios.py` | Công cụ sinh lại toàn bộ các tệp trên |

**Cách sinh dữ liệu.** Pod B là bản sao của Pod A, được đổi tên, địa chỉ IP, ASN và địa chỉ quản trị:

| Thiết bị | Nhân bản từ | Địa chỉ quản trị | ASN |
|---|---|---|---|
| edge2 | edge1 | 172.20.20.14 | 65001 |
| spine3 | spine1 | 172.20.20.15 | 65030 |
| spine4 | spine2 | 172.20.20.16 | 65040 |
| leaf4 | leaf1 | 172.20.20.24 | 65104 |
| leaf5 | leaf2 | 172.20.20.25 | 65105 |
| leaf6 | leaf3 | 172.20.20.26 | 65106 |

Mỗi tệp SoT chỉ giữ những cổng và láng giềng BGP nối tới thiết bị có mặt trong kịch bản đó.

**Lưu ý.** Cấu hình trong hai thư mục `scale_*` là **giả lập**, không lấy từ thiết bị thật. Mật khẩu BGP và khóa SNMP được thay bằng chuỗi `MAU_*`. Các luật CIS vẫn khớp, vì regex chỉ kiểm tra từ khóa.

## Cách chạy

Chạy ở thư mục gốc repo:

```bash
# (tùy chọn) sinh lại dữ liệu
python3 scripts/gen_scenarios.py

# chấm một kịch bản, ghi báo cáo ra thư mục riêng để không đè số liệu của dashboard
python3 compliance/tools/score.py --sot sot/scenarios/devices_12.yaml \
  --compare compliance/configs/scale_before compliance/configs/scale_after \
  --out compliance/reports/scale
```

Thay `devices_12.yaml` bằng `devices_3.yaml` hoặc `devices_9.yaml` để chạy các kịch bản còn lại.

## Kết quả kiểm chứng

| Kịch bản | Số thiết bị | Điểm trước | Điểm sau | Vi phạm trước → sau | Điểm trọng số trước |
|---|---|---|---|---|---|
| devices_3 | 3 | 52.0% | 100.0% | 22 → 0 | 78/150 |
| devices_9 | 9 | 53.6% | 100.0% | 63 → 0 | 241/450 |
| devices_12 | 12 | 54.3% | 100.0% | 82 → 0 | 326/600 |

Ở cả ba quy mô, điểm từng thiết bị giữ nguyên. Ví dụ edge1 và edge2 đều ra 61.7% → 100%. Điều này cho thấy logic chấm không phụ thuộc vào số lượng thiết bị. Điểm tổng thay đổi theo tỉ lệ thiết bị FRR (18 luật) và SR Linux (15 luật) trong kịch bản, vì điểm tổng là trung bình có trọng số.

## Deploy thật trên lab: `./run.sh scale-lab`

`scripts/scale_lab.py` chạy lần lượt 3, 6, 9, 12 thiết bị. Với mỗi quy mô:

1. Sinh topology Containerlab từ SoT (`lab/scale/topo_<n>.clab.yml`) và dựng lab.
2. Sinh inventory từ chính SoT đó (`sot_to_inventory.py --sot ...`).
3. Deploy lần 1, đếm phiên eBGP Established, deploy lần 2 (lũy đẳng).
4. Backup và chấm điểm cấu hình thật trước harden; harden; backup và chấm điểm sau.
5. Ghi RAM các container, xóa lab.

Kết quả: `compliance/reports/scale_lab.md` (bảng tổng hợp và chi tiết từng thiết bị) và `scale_lab.json`. Script ghi lại sau mỗi quy mô, nên dừng giữa chừng vẫn giữ được số liệu đã đo. Khi xong, script khôi phục `inventory/hosts.yml` và dựng lại lab 6 thiết bị.

```bash
./run.sh scale-lab                 # cả 4 quy mô, khoảng 40–60 phút
./run.sh scale-lab --only 3 6      # chỉ 3 và 6 thiết bị
./run.sh scale-lab --topo-only     # chỉ sinh file topology để xem trước
```

Nếu RAM trống của máy ảo nhỏ hơn ước tính (mặc định 1500 MiB mỗi SR Linux, 150 MiB mỗi FRR), quy mô đó được bỏ qua và ghi lý do vào báo cáo. Dùng `--force` để vẫn chạy, hoặc `--mem-srl` để chỉnh ước tính sau khi xem cột RAM thực tế.
