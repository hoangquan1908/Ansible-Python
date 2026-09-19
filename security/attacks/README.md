# security/ (Tùng)

Kịch bản tấn công mô phỏng đối chứng **trước/sau** hardening và luồng phản ứng sự cố.

- `attacks/` — kịch bản (nmap, script Python) đo bề mặt tấn công.
- `reports/` — kết quả kiểm thử xâm nhập, số liệu MTTR (không commit — xem .gitignore).

Quy trình: đo đường cơ sở (trước) → `ansible-playbook playbooks/harden.yml` →
đo lại (sau) → so sánh mức giảm rủi ro.
