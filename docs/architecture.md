# Kiến trúc tổng thể

Hệ thống theo mô hình **vòng khép kín** quanh một Nguồn dữ liệu tin cậy (SoT):

```
        ┌────────────────────── sot/devices.yaml (SoT) ──────────────────────┐
        │                                                                    │
        ▼                                                                    ▼
  scripts/sot_to_inventory.py                                   compliance/policy (CIS)
        │                                                                    │
        ▼                                                                    │
  inventory/hosts.yml                                                        │
        │                                                                    │
        ▼                                                                    ▼
  playbooks/deploy.yml ──► THIẾT BỊ (Containerlab) ◄── playbooks/harden.yml  │
     (Chung: cấu hình)         SR Linux + FRR          (Tùng: hardening)      │
        │                          │                                         │
        │              running-config (thật)                                 │
        │                          ▼                                         │
        │            compliance/configs/live/*.cfg ──► compliance/tools/score.py
        │                                                    (Quân: chấm điểm)
        │                                                          │
        └───────────── phát hiện trôi cấu hình / vi phạm ◄─────────┘
                          (đóng vòng: sửa SoT rồi triển khai lại)
```

Chi tiết kế hoạch và phân công xem `README.md` và `compliance/HUONG_DAN_QUAN.md`.
