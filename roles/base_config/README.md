# role: base_config (Chung)

Cấu hình nền tảng (KB-01): hostname, user, NTP, syslog, banner.
Đầu vào: biến từ `sot/devices.yaml` + `group_vars`. Khuôn mẫu đặt ở `templates/`.
Yêu cầu: **idempotent** (chạy nhiều lần không đổi kết quả).
