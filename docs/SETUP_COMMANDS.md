# Tổng hợp câu lệnh cài đặt môi trường lab
## Đồ án: Tự động hóa cấu hình và kiểm soát tuân thủ an ninh mạng (Ansible + Python)

> Chạy trên máy ảo Ubuntu (lab host — máy Quân 32 GB).
> Mở Terminal: nhấn phím Super (Windows) → gõ "terminal" → Enter.
> Chạy lần lượt từng nhóm lệnh theo thứ tự.

---

## BƯỚC 1 — Cập nhật hệ thống & công cụ cơ bản

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl python3 python3-pip python3-venv nano
```

---

## BƯỚC 2 — Docker + Containerlab (một lệnh, cài cả hai)

```bash
# Tải và chạy script cài trọn gói: Docker + Containerlab + gh CLI
curl -sL https://containerlab.dev/setup | sudo -E bash -s "all"

# Cho phép chạy docker không cần sudo
sudo usermod -aG docker $USER
```

> ⚠️ Sau lệnh usermod: ĐĂNG XUẤT rồi ĐĂNG NHẬP LẠI (hoặc khởi động lại VM)
> thì mới hết lỗi "permission denied" khi gõ docker.

Kiểm tra đã cài xong:

```bash
docker --version
containerlab version
```

---

## BƯỚC 3 — Ansible + thư viện Python cho mạng

```bash
sudo apt install -y ansible
pip3 install --break-system-packages netmiko napalm pybatfish pandas
ansible-galaxy collection install nokia.srlinux frrouting.frr ansible.netcommon
```

Kiểm tra:

```bash
ansible --version
```

---

## BƯỚC 4 — Tailscale (để Chung và Tùng truy cập từ xa)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Mở link hiện ra bằng trình duyệt, đăng nhập TÀI KHOẢN CHUNG của nhóm

# Xem địa chỉ Tailscale của máy ảo (dạng 100.x.x.x) — gửi cho nhóm để SSH vào
tailscale ip -4
```

Chung & Tùng (trên Windows): cài Tailscale, đăng nhập CÙNG tài khoản, rồi:

```bash
ssh <username>@100.x.x.x
```

---

## BƯỚC 5 — Kéo ảnh thiết bị & test lab 2 nút

```bash
# Tạo thư mục lab
mkdir -p ~/lab && cd ~/lab

# Kéo ảnh thiết bị (SR Linux + FRR — miễn phí, không cần đăng ký)
docker pull ghcr.io/nokia/srlinux:latest
docker pull quay.io/frrouting/frr:master
```

Tạo file topology test:

```bash
cat > test.clab.yml <<'EOF'
name: test
topology:
  nodes:
    srl1:
      kind: nokia_srlinux
      image: ghcr.io/nokia/srlinux:latest
    frr1:
      kind: linux
      image: quay.io/frrouting/frr:master
  links:
    - endpoints: ["srl1:e1-1", "frr1:eth1"]
EOF
```

Dựng lab và kiểm tra:

```bash
sudo containerlab deploy -t test.clab.yml   # dựng lab
sudo containerlab inspect -t test.clab.yml  # xem trạng thái node
sudo containerlab destroy -t test.clab.yml  # xóa lab khi xong
```

> Nếu deploy hiện bảng liệt kê 2 node đang chạy => toàn bộ chuỗi công cụ ĐÃ THÔNG (đầu việc G0).

---

## BƯỚC 6 — Snapshot môi trường sạch (làm trên VMware/Windows)

VMware menu: VM → Snapshot → Take Snapshot → đặt tên "moi-truong-sach".
Lỡ hỏng thì Restore lại trong 30 giây.

---

## GHI CHÚ THÊM

### SONiC (dòng thiết bị thứ ba) — cài sau khi SR Linux + FRR đã chạy ổn
```bash
# (Sẽ bổ sung lệnh cụ thể khi triển khai — ảnh SONiC nặng và cấu hình phức tạp hơn)
```

### Các lệnh Containerlab hay dùng
```bash
sudo containerlab deploy -t <file>.clab.yml     # dựng lab
sudo containerlab destroy -t <file>.clab.yml    # xóa lab
sudo containerlab inspect -t <file>.clab.yml    # xem node đang chạy
sudo containerlab graph -t <file>.clab.yml      # vẽ sơ đồ topology (mở web)
docker ps                                        # xem container đang chạy
docker stats                                     # xem RAM/CPU từng container
free -h                                          # xem RAM còn trống
```

### Nếu gặp lỗi "permission denied" khi gõ docker
```bash
# Chưa đăng nhập lại sau usermod. Khắc phục tạm:
newgrp docker
# hoặc đăng xuất/đăng nhập lại tài khoản Ubuntu
```

### Ansible-vault (dùng ở phần của Tùng — quản lý bí mật)
```bash
ansible-vault create secrets.yml     # tạo file bí mật mã hóa
ansible-vault edit secrets.yml       # sửa
ansible-vault view secrets.yml       # xem
```

---

_Ghi chú: các dòng cảnh báo màu đỏ như "SMBus Host Controller not enabled"
hay "piix4_smbus" khi khởi động là bình thường trên máy ảo, bỏ qua._
