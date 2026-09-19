# Hướng dẫn tạo repo Git & quy trình làm việc nhóm 3 người

## 1. Khởi tạo repo (làm 1 lần, do 1 người — vd. Quân)

```bash
cd "D:\ĐATN\Ansible Python"      # thư mục này LÀ gốc repo
git init
git add .
git commit -m "khởi tạo: khung dự án tự động hóa & tuân thủ mạng"
```

## 2. Đưa lên GitHub/GitLab (để 3 người cùng làm)

1. Tạo repo rỗng trên GitHub (vd. tên `network-automation`), **không** thêm README.
2. Nối remote và đẩy lên:

```bash
git branch -M main
git remote add origin https://github.com/<tài-khoản>/network-automation.git
git push -u origin main
```

3. Mời Chung và Tùng làm **Collaborator** (Settings → Collaborators).

## 3. Hai người kia lấy code về

```bash
git clone https://github.com/<tài-khoản>/network-automation.git
cd network-automation
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml
```

## 4. Quy trình nhánh (tránh giẫm chân nhau)

Mỗi người làm trên **nhánh riêng theo vùng phụ trách**, không đẩy thẳng vào `main`:

| Người | Nhánh | Chủ yếu sửa |
|---|---|---|
| Chung | `feat/config` | `roles/base_config,vlan_port,routing,backup_restore`, `inventory/`, `lab/` |
| Tùng | `feat/hardening` | `roles/hardening`, `security/` |
| Quân | `feat/compliance` | `compliance/`, `sot/`, `scripts/` |

Vòng làm việc hằng ngày:

```bash
git checkout -b feat/compliance      # lần đầu; sau này: git checkout feat/compliance
# ... sửa code ...
git add -A
git commit -m "compliance: thêm 5 luật CIS mới"
git push -u origin feat/compliance
```

Khi xong một phần → mở **Pull Request** vào `main`, người khác xem rồi merge.
Trước khi làm tiếp, đồng bộ `main` mới nhất:

```bash
git checkout main && git pull
git checkout feat/compliance && git merge main
```

## 5. Quy tắc quan trọng

- **KHÔNG commit bí mật** (mật khẩu, khóa). Dùng `ansible-vault`; đã chặn sẵn trong `.gitignore`.
- **SoT là nguồn dữ liệu tin cậy duy nhất**: sửa thiết bị chỉ ở `sot/devices.yaml`, rồi
  chạy `python scripts/sot_to_inventory.py` — đừng sửa tay `inventory/hosts.yml`.
- Ai đổi "hợp đồng dữ liệu" (SoT, định dạng policy, định dạng báo cáo) phải báo cả nhóm.
