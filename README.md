# Tự động hóa cấu hình & kiểm soát tuân thủ an ninh mạng
### Đồ án tốt nghiệp — Ansible + Python | Nhóm 3 người

Repo dùng chung cho cả nhóm. **Một Nguồn dữ liệu tin cậy (SoT)** ở `sot/`, mọi
cấu hình và phép kiểm tra đều bắt nguồn từ đó.

## Phân chia theo thành viên

| Thư mục | Chủ trì | Nội dung |
|---|---|---|
| `sot/` | **Quân** (cả nhóm dùng) | Nguồn dữ liệu tin cậy: thiết bị, VLAN, cổng, tham số |
| `inventory/`, `lab/` | **Chung** | Inventory Ansible (sinh từ SoT) + topo Containerlab |
| `roles/base_config`, `vlan_port`, `routing`, `backup_restore` | **Chung** | Cấu hình nền tảng, VLAN/cổng, định tuyến, sao lưu/rollback |
| `roles/hardening`, `security/` | **Tùng** | Chuẩn hóa an ninh (CIS) + kịch bản tấn công đối chứng |
| `compliance/` | **Quân** | Chính sách CIS dạng mã, công cụ chấm điểm, báo cáo/dashboard |
| `playbooks/` | Cả nhóm | Điểm vào chạy từng khối và toàn hệ thống |
| `scripts/` | Cả nhóm | Tiện ích Python dùng chung (vd. sinh inventory từ SoT) |
| `docs/` | Cả nhóm | Thuyết minh, kiến trúc |

## Cây thư mục

```
.
├─ sot/devices.yaml            # ★ Nguồn dữ liệu tin cậy (single source of truth)
├─ inventory/
│  ├─ hosts.yml                # sinh từ SoT: python scripts/sot_to_inventory.py
│  └─ group_vars/{all,srlinux,frr}.yml
├─ lab/topo.clab.yml           # topo Containerlab (SR Linux + FRR)
├─ roles/
│  ├─ base_config/  vlan_port/  routing/  backup_restore/   # Chung
│  └─ hardening/                                            # Tùng
├─ playbooks/
│  ├─ site.yml                 # chạy tất cả
│  ├─ deploy.yml               # Chung: triển khai cấu hình
│  ├─ harden.yml               # Tùng: chuẩn hóa an ninh
│  └─ compliance.yml           # Quân: chấm điểm tuân thủ
├─ compliance/                 # Quân — module chấm điểm (chạy độc lập được)
│  ├─ policy/cis_rules.yaml
│  ├─ configs/{golden,live}/
│  ├─ tools/score.py
│  └─ reports/
├─ security/                   # Tùng — pentest & đối chứng
│  ├─ attacks/
│  └─ reports/
├─ scripts/sot_to_inventory.py
├─ docs/architecture.md
├─ ansible.cfg  requirements.yml  requirements.txt  .gitignore
```

## Cài đặt nhanh

```bash
python -m venv .venv && . .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml
```

## Vòng chạy end-to-end

```bash
python scripts/sot_to_inventory.py        # 1. SoT -> inventory
# (dựng lab: sudo clab deploy -t lab/topo.clab.yml)
ansible-playbook playbooks/deploy.yml     # 2. Chung: triển khai cấu hình
ansible-playbook playbooks/harden.yml     # 3. Tùng: chuẩn hóa an ninh
python compliance/tools/score.py --configs compliance/configs/live   # 4. Quân: chấm điểm
```

Xem `compliance/HUONG_DAN_QUAN.md` cho phần việc của Quân và `docs/architecture.md`
cho kiến trúc tổng thể.
