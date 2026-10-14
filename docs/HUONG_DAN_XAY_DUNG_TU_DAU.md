# Hướng dẫn xây dựng đồ án TỪ SỐ 0 (dành cho người mới)

> **Đề tài:** Tự động hóa cấu hình & kiểm soát tuân thủ an ninh mạng — Ansible + Python
> **Người đọc:** Sinh viên chưa từng dùng Ansible / Containerlab. Đọc tới đâu làm tới đó.
> **Cách dùng file này:** Làm tuần tự từ Phần 0 → Phần 12. Mỗi phần có 3 khối:
> **(?) Vì sao** — kiến thức nền · **(>) Làm gì** — tạo file/gõ lệnh · **(v) Kiểm tra** — xác nhận đã đúng.
>
> Mẹo: đừng copy cả cục. Hãy **tự gõ lại** từng file nhỏ, chạy, thấy nó chạy, rồi mới sang bước sau. Hiểu đến đâu chắc đến đó.

---

## Mục lục
- [Phần 0 — Hiểu bài toán & lập kế hoạch](#phần-0)
- [Phần 1 — Dựng môi trường (máy Linux + công cụ)](#phần-1)
- [Phần 2 — Khởi tạo khung dự án](#phần-2)
- [Phần 3 — Viết SoT (nguồn dữ liệu tin cậy)](#phần-3)
- [Phần 4 — Dựng phòng lab bằng Containerlab](#phần-4)
- [Phần 5 — Sinh inventory + khai báo kết nối](#phần-5)
- [Phần 6 — "Bắt tay" Ansible với thiết bị (ping)](#phần-6)
- [Phần 7 — Viết role cấu hình (deploy)](#phần-7)
- [Phần 8 — Phần an ninh: CIS + hardening + chấm điểm](#phần-8)
- [Phần 9 — Sao lưu, drift, benchmark, risk, scan](#phần-9)
- [Phần 10 — Dashboard web](#phần-10)
- [Phần 11 — run.sh: gói tất cả thành 1 cửa](#phần-11)
- [Phần 12 — Chạy toàn bộ & chuẩn bị bảo vệ](#phần-12)

---

<a name="phần-0"></a>
## Phần 0 — Hiểu bài toán & lập kế hoạch

### (?) Vì sao
Trước khi gõ 1 dòng code, phải trả lời được: *xây cái gì, cho ai, đo bằng gì?*

- **Bài toán:** cấu hình mạng bằng tay thì chậm (90 phút), dễ sai (15–20%), và không ai kiểm soát được thiết bị có an toàn không.
- **Lời giải:** tự động hóa cấu hình bằng **Ansible**, và kiểm soát an ninh tự động bằng **Python** theo chuẩn **CIS Benchmark**.
- **Triết lý cốt lõi — SoT-first:** có **một** file duy nhất mô tả "mạng đúng phải thế nào" (gọi là **Source of Truth**). Mọi thứ khác (danh sách thiết bị, cấu hình, bài kiểm tra) đều **sinh ra / đối chiếu** từ file đó. Sửa 1 chỗ → cả hệ thống đổi theo. Đây là điểm ăn tiền của đồ án.

### (>) Làm gì — thiết kế trên giấy trước
Chốt 5 quyết định sau (ghi ra giấy / file nháp), vì Phần 3 sẽ mã hóa chúng:

1. **Topology:** 6 thiết bị, 3 tầng **Edge – Spine – Leaf**.
   ```
             [edge1]            (FRR — router biên)
                |
         ┌──────┴──────┐
      [spine1]      [spine2]    (SR Linux — phân phối)
       /    \        /    \
   [leaf1] [leaf2]        [leaf3]   (SRL x2 + FRR — truy cập)
   ```
2. **Nền tảng:** 4 **Nokia SR Linux** + 2 **FRRouting** → để chứng minh chạy được đa nền tảng.
3. **Kế hoạch IP:**
   - Mạng quản lý (mgmt): `172.20.20.0/24` (edge1=.10, spine1=.11, spine2=.12, leaf1=.21, leaf2=.22, leaf3=.23)
   - Link giữa các thiết bị: dùng `/30` (mỗi link 1 dải riêng, vd `10.0.1.0/30`)
   - Loopback mỗi thiết bị: `10.255.0.x/32`
4. **Định tuyến:** **eBGP**, mỗi thiết bị một số **AS** riêng (edge=65000, spine1=65010, spine2=65020, leaf1=65101, leaf2=65102, leaf3=65103).
5. **An ninh:** dùng khung **CIS Benchmark**, chốt ~18 luật (cấm Telnet, mã hóa mật khẩu, banner, ACL quản trị, NTP, syslog...).

### (v) Kiểm tra
Bạn vẽ được sơ đồ mạng + bảng IP/AS ra giấy. Nếu bí chỗ nào, xem lại file `sot/devices.yaml` bản gốc để tham chiếu.

> **Khái niệm mới:** *eBGP* = giao thức định tuyến giữa các "vùng tự trị" (AS) khác nhau. Mỗi thiết bị là 1 AS → chúng trao đổi đường đi với nhau. *Loopback* = một địa chỉ IP "ảo" luôn sống của thiết bị, thường dùng làm định danh (router-id).

---

<a name="phần-1"></a>
## Phần 1 — Dựng môi trường (máy Linux + công cụ)

### (?) Vì sao
**Containerlab chỉ chạy trên Linux** (vì nó cần Docker + Linux networking). Nếu bạn dùng Windows, hãy cài **WSL2 (Ubuntu)** hoặc một **máy ảo Linux** (VMware/VirtualBox với Ubuntu). Mọi lệnh bên dưới chạy trong Linux.

4 công cụ cần có:
- **Docker** — động cơ chạy container (mỗi thiết bị mạng là 1 container).
- **Containerlab** — dựng nhiều container thành một mạng có topology.
- **Python 3** — chạy các script chấm điểm/phân tích.
- **Ansible** — tự động hóa cấu hình thiết bị.

### (>) Làm gì — cài đặt

```bash
# 1) Cập nhật hệ thống (Ubuntu/Debian)
sudo apt update && sudo apt -y upgrade

# 2) Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER        # cho phép chạy docker không cần sudo
# ĐĂNG XUẤT và đăng nhập lại để áp quyền group

# 3) Containerlab
bash -c "$(curl -sL https://get.containerlab.dev)"

# 4) Python + pip + venv
sudo apt -y install python3 python3-pip python3-venv git

# 5) Ansible (cài trong môi trường ảo Python — xem Phần 2)
```

### (v) Kiểm tra
```bash
docker --version          # Docker version 2x.x
clab version              # phiên bản containerlab
python3 --version         # Python 3.1x
git --version
```
Nếu `docker ps` báo "permission denied" → bạn chưa đăng xuất/đăng nhập lại sau bước `usermod`.

> **Khái niệm mới:** *Container* = một "máy ảo nhẹ", khởi động trong vài giây, dùng chung nhân Linux của máy thật. *Image* = "khuôn" để tạo container (vd image `ghcr.io/nokia/srlinux`).

---

<a name="phần-2"></a>
## Phần 2 — Khởi tạo khung dự án

### (?) Vì sao
Cần một thư mục dự án có **cấu trúc rõ ràng** ngay từ đầu, và một **môi trường Python ảo (venv)** để cài thư viện không đụng hệ thống. Ansible cũng cần một file cấu hình `ansible.cfg` để biết các mặc định (inventory ở đâu, roles ở đâu...).

### (>) Làm gì

**B1. Tạo thư mục & git:**
```bash
mkdir -p ~/DATN/Ansible-Python && cd ~/DATN/Ansible-Python
git init
```

**B2. Tạo môi trường Python ảo & kích hoạt:**
```bash
python3 -m venv .venv
source .venv/bin/activate        # thấy (.venv) ở đầu dòng lệnh là đúng
```

**B3. Tạo khung thư mục rỗng:**
```bash
mkdir -p sot lab inventory/group_vars \
         roles scripts compliance/policy compliance/tools \
         compliance/configs/{golden,after,live} compliance/reports \
         security/attacks security/reports dashboard/templates docs
```

**B4. File `requirements.txt` (thư viện Python):**
```txt
ansible-core>=2.16
PyYAML>=6.0
Jinja2>=3.1
netmiko>=4.3
python-nmap>=0.7.1
flask>=3.0
```
Cài: `pip install -r requirements.txt`

**B5. File `requirements.yml` (collection Ansible — "trình điều khiển" cho từng loại thiết bị):**
```yaml
---
collections:
  - name: ansible.netcommon
    version: ">=5.0.0"
  - name: nokia.srlinux
    version: ">=0.2.0"
```
Cài: `ansible-galaxy collection install -r requirements.yml`

**B6. File `ansible.cfg` (mặc định của Ansible):**
```ini
[defaults]
inventory = inventory/hosts.yml
roles_path = roles
collections_path = collections
host_key_checking = false
retry_files_enabled = false
timeout = 30
interpreter_python = auto_silent
vault_password_file = vault-pass.txt

[persistent_connection]
command_timeout = 60
connect_timeout = 60
```

**B7. File `.gitignore`:**
```gitignore
.venv/
collections/
backups/
*.retry
vault-pass.txt
scan_result.json
```

### (v) Kiểm tra
```bash
ansible --version         # chạy được, hiện phiên bản
ansible-galaxy collection list | grep -E "nokia|netcommon"   # thấy 2 collection
```

> **Khái niệm mới:** *Collection* = gói mở rộng của Ansible chứa các "module" cho một hệ cụ thể (vd `nokia.srlinux` biết nói chuyện với SR Linux). *venv* = hộp cách ly thư viện Python cho riêng dự án.

---

<a name="phần-3"></a>
## Phần 3 — Viết SoT (nguồn dữ liệu tin cậy)

### (?) Vì sao
Đây là **viên gạch nền**. File `sot/devices.yaml` biến bản thiết kế ở Phần 0 thành dữ liệu máy đọc được. Từ đây sinh ra inventory, cấu hình, và các phép kiểm tra. YAML là định dạng "danh sách/đối tượng" dễ đọc (thụt lề = cấp bậc).

### (>) Làm gì — tạo `sot/devices.yaml`
Khai báo cho **cả 6 thiết bị** theo mẫu dưới (đây là 1 thiết bị, làm tương tự cho 6 con — lấy IP/AS từ bảng Phần 0):

```yaml
meta:
  ten_de_tai: "Tu dong hoa cau hinh va kiem soat tuan thu an ninh mang"
  phien_ban_sot: "2.0"

devices:
  - name: edge1
    os: frr                 # frr | srlinux  → quyết định nhánh cấu hình
    role: edge              # edge | spine | leaf
    mgmt_ip: 172.20.20.10
    profile: strict
    loopback_ip: 10.255.0.1
    interfaces:
      - name: eth1
        description: "Downlink to spine1"
        ipv4: 10.0.1.1/30
      - name: eth2
        description: "Downlink to spine2"
        ipv4: 10.0.2.1/30
    bgp:
      asn: 65000
      router_id: 10.255.0.1
      neighbors:
        - address: 10.0.1.2
          remote_as: 65010
          description: "eBGP to spine1"
  # ... làm tiếp spine1, spine2, leaf1, leaf2, leaf3 ...

# Tham số an ninh dùng chung (Phần 8 sẽ đọc lại)
policy_inputs:
  ntp_servers: [172.20.20.2]
  syslog_servers: [172.20.20.3]
  allowed_mgmt_cidr: "172.20.20.0/24"
  banner_text: >-
    CANH BAO: He thong noi bo - Cam truy cap trai phep.
  ssh_timeout: 300
```

> **Lưu ý khớp số:** `name`, `mgmt_ip`, `interfaces.ipv4`, `bgp.asn` phải khớp đúng với topology Phần 0. Hai đầu một link phải cùng dải `/30` (vd edge1 `10.0.1.1/30` ↔ spine1 `10.0.1.2/30`), và `remote_as` của bên này = `asn` của bên kia.

### (v) Kiểm tra
```bash
python3 -c "import yaml; d=yaml.safe_load(open('sot/devices.yaml')); print(len(d['devices']),'thiet bi')"
# -> 6 thiet bi
```
Nếu báo lỗi YAML → kiểm tra thụt lề (YAML dùng dấu cách, **không** dùng Tab).

---

<a name="phần-4"></a>
## Phần 4 — Dựng phòng lab bằng Containerlab

### (?) Vì sao
Cần **thiết bị thật để test** (ảo hóa). Containerlab đọc 1 file topology (`.clab.yml`) rồi tự bật các container và **đấu dây** chúng theo đúng sơ đồ. File này phải **khớp** SoT (cùng tên, cùng mgmt IP).

### (>) Làm gì — tạo `lab/topo.clab.yml`
```yaml
name: datn-lab

topology:
  nodes:
    edge1:
      kind: linux
      image: quay.io/frrouting/frr:master
      mgmt-ipv4: 172.20.20.10
      exec:                                    # lệnh chạy khi container bật
        - apk add --no-cache python3 openssh-server
        - ssh-keygen -A
        - echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
        - /usr/sbin/sshd
        - sed -i 's/^bgpd=no/bgpd=yes/' /etc/frr/daemons
    spine1:
      kind: nokia_srlinux
      image: ghcr.io/nokia/srlinux:latest
      mgmt-ipv4: 172.20.20.11
    # ... spine2, leaf1, leaf2 (srlinux), leaf3 (frr giống edge1) ...

  links:                                        # đấu dây đúng topology
    - endpoints: ["edge1:eth1", "spine1:e1-1"]
    - endpoints: ["edge1:eth2", "spine2:e1-1"]
    - endpoints: ["spine1:e1-2", "leaf1:e1-1"]
    # ... các link còn lại ...

mgmt:
  network: datn-mgmt
  ipv4-subnet: 172.20.20.0/24
```

Dựng lab:
```bash
sudo clab deploy -t lab/topo.clab.yml
```

Với 2 container FRR (edge1, leaf3) cần bật SSH key để Ansible vào được:
```bash
for node in edge1 leaf3; do
  cname="clab-datn-lab-${node}"
  docker cp ~/.ssh/id_ed25519.pub "${cname}:/root/.ssh/authorized_keys"
  docker exec "$cname" chmod 600 /root/.ssh/authorized_keys
done
```
> (Nếu chưa có khóa SSH: `ssh-keygen -t ed25519` rồi Enter hết.)

### (v) Kiểm tra
```bash
sudo clab inspect -t lab/topo.clab.yml    # thấy 6 node, trạng thái running
docker ps                                  # 6 container clab-datn-lab-*
ping -c2 172.20.20.11                       # ping tới mgmt IP của spine1
```

> **Khái niệm mới:** *kind* = loại thiết bị (containerlab biết cách khởi tạo riêng cho `nokia_srlinux` vs `linux`). *exec* = lệnh chạy lúc bật container (ở đây để bật SSH + bật tiến trình BGP của FRR).

---

<a name="phần-5"></a>
## Phần 5 — Sinh inventory + khai báo kết nối

### (?) Vì sao
Ansible cần **inventory** = danh sách thiết bị + cách đăng nhập. Nhưng ta **không gõ tay** inventory — ta viết một script Python **sinh** nó từ SoT (giữ nguyên tắc "1 nguồn"). Thiết bị được **gom nhóm theo OS** (`frr`, `srlinux`) để sau này role rẽ nhánh đúng.

### (>) Làm gì

**B1. Script sinh inventory — `scripts/sot_to_inventory.py`:**
```python
#!/usr/bin/env python3
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parent.parent
SOT = REPO / "sot/devices.yaml"
OUT = REPO / "inventory/hosts.yml"

def main():
    sot = yaml.safe_load(SOT.read_text(encoding="utf-8"))
    groups = {}
    for d in sot["devices"]:
        g = groups.setdefault(d["os"], {"hosts": {}})   # nhóm theo os
        g["hosts"][d["name"]] = {
            "ansible_host": d["mgmt_ip"],
            "device_role": d.get("role", ""),
            "hardening_profile": d.get("profile", "baseline"),
            "loopback_ip": d.get("loopback_ip", ""),
            "device_interfaces": d.get("interfaces", []),
            "device_bgp": d.get("bgp", {}),
        }
    inventory = {"all": {"children": {os: grp for os, grp in groups.items()}}}
    OUT.write_text(
        "# TU SINH tu sot/devices.yaml — DUNG sua tay.\n"
        + yaml.safe_dump(inventory, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    print(f"Da sinh {OUT}")

if __name__ == "__main__":
    main()
```
Chạy: `python3 scripts/sot_to_inventory.py` → tạo ra `inventory/hosts.yml`.

**B2. Khai báo CÁCH kết nối từng nhóm** (đây là phần không nằm trong SoT, vì nó là "bí mật đăng nhập"):

`inventory/group_vars/frr.yml` — FRR nối bằng **SSH**:
```yaml
---
ansible_connection: ssh
ansible_user: root
ansible_ssh_private_key_file: "~/.ssh/id_ed25519"
ansible_shell_type: sh
ansible_ssh_common_args: "-o StrictHostKeyChecking=no"
```

`inventory/group_vars/srlinux/vars.yml` — SR Linux nối bằng **API (HTTPAPI/JSON-RPC)**:
```yaml
---
ansible_connection: ansible.netcommon.httpapi
ansible_network_os: nokia.srlinux.srlinux
ansible_user: admin
ansible_password: "NokiaSrl1!"
ansible_httpapi_use_ssl: true
ansible_httpapi_validate_certs: false
ansible_httpapi_port: 443
```

`inventory/group_vars/all.yml` — biến dùng cho **mọi** thiết bị (lấy khớp SoT):
```yaml
---
ntp_servers: [172.20.20.2]
syslog_servers: [172.20.20.3]
allowed_mgmt_cidr: "172.20.20.0/24"
banner_text: >-
  CANH BAO: He thong noi bo - Cam truy cap trai phep.
ssh_timeout: 300
backup_dir: "backups"
compliance_configs_dir: "compliance/configs/live"
```

### (v) Kiểm tra
```bash
cat inventory/hosts.yml                 # thấy nhóm frr/srlinux + 6 host
ansible-inventory --graph               # xem cây nhóm/host
```

> **Khái niệm mới:** *group_vars/<tên nhóm>.yml* = biến tự động áp cho mọi host trong nhóm đó. Đây là lý do mọi host FRR dùng chung cách SSH, mọi host SRL dùng chung API — mà không lặp lại.

---

<a name="phần-6"></a>
## Phần 6 — "Bắt tay" Ansible với thiết bị (ping)

### (?) Vì sao
Trước khi cấu hình, phải chắc Ansible **đăng nhập được** vào cả 6 con. Module `ping` của Ansible = "thử đăng nhập + chạy thử", trả về `pong` nếu OK (khác ping ICMP thông thường).

### (>) Làm gì
```bash
ansible all -m ping -i inventory/hosts.yml
```

### (v) Kiểm tra
Cả 6 host trả `SUCCESS` + `"ping": "pong"`. Nếu con nào `UNREACHABLE`:
- FRR: kiểm tra đã `docker cp` khóa SSH chưa (Phần 4).
- SRL: kiểm tra mật khẩu/port trong `group_vars/srlinux/vars.yml`.

---

<a name="phần-7"></a>
## Phần 7 — Viết role cấu hình (deploy)

### (?) Vì sao
Giờ thiết bị còn trống. Ta viết **role** = gói công thức cấu hình theo chủ đề. 3 role cho phần "chạy được":
- `base_config` — hostname, syslog, banner, NTP
- `routing` — IP cổng + BGP
- `vlan_port` — VLAN ở leaf

**Mẫu chung mọi role:** `tasks/main.yml` chỉ **rẽ nhánh** theo nhóm OS → gọi `frr.yml` hoặc `srlinux.yml`. Vì FRR cấu hình bằng *template + vtysh*, còn SRL bằng *module API*.

### (>) Làm gì — ví dụ role `base_config`

**B1. Khung role:**
```bash
ansible-galaxy init roles/base_config    # tạo sẵn tasks/ handlers/ templates/ defaults/ ...
```
> `ansible-galaxy init` sinh đủ thư mục con **đúng chuẩn Ansible**. Tên thư mục con (`tasks`, `templates`, `defaults`...) là **cố định** — Ansible tìm theo đúng tên. Tên role (`base_config`) thì do bạn đặt.

**B2. `roles/base_config/tasks/main.yml` — người gác cổng:**
```yaml
---
- name: "[base] Cau hinh cho SR Linux"
  ansible.builtin.include_tasks: srlinux.yml
  when: "'srlinux' in group_names"
- name: "[base] Cau hinh cho FRR"
  ansible.builtin.include_tasks: frr.yml
  when: "'frr' in group_names"
```

**B3. `roles/base_config/tasks/frr.yml` — cách cấu hình FRR (template → file → nạp):**
```yaml
---
- name: "[base/frr] Sinh cau hinh tu template"
  ansible.builtin.template:
    src: base_frr.j2
    dest: /etc/frr/base.conf
- name: "[base/frr] Ap dung qua vtysh"
  ansible.builtin.shell: vtysh -f /etc/frr/base.conf
  changed_when: true
- name: "[base/frr] Dat banner"
  ansible.builtin.copy:
    content: "{{ banner_text }}"
    dest: /etc/motd
```

**B4. `roles/base_config/templates/base_frr.j2` — khuôn cấu hình (có chỗ trống):**
```jinja
! Sinh tu dong boi Ansible — {{ inventory_hostname }}
hostname {{ base_hostname | default(inventory_hostname) }}
log syslog informational
log file /var/log/frr/frr.log
end
```

**B5. `roles/base_config/tasks/srlinux.yml` — cách cấu hình SR Linux (module API):**
```yaml
---
- name: "[base/srl] Dat hostname"
  nokia.srlinux.config:
    update:
      - path: /system/name/host-name
        value: "{{ inventory_hostname }}"
- name: "[base/srl] Dat banner"
  nokia.srlinux.config:
    update:
      - path: /system/banner
        value:
          login-banner: "{{ banner_text }}"
```

**B6. Làm tương tự cho role `routing`** (interface IP + BGP). Với FRR dùng template `bgp_frr.j2`; với SRL dùng `nokia.srlinux.config` đặt `/network-instance/.../bgp`. Lấy dữ liệu từ biến `device_interfaces`, `device_bgp`, `loopback_ip` (đã bơm vào host từ SoT ở Phần 5).

**B7. Playbook `deploy.yml` — ra lệnh chạy role nào, trên host nào:**
```yaml
---
- name: "GIAI DOAN 1 — Co ban + dinh tuyen"
  hosts: all
  gather_facts: false
  collections: [nokia.srlinux]
  roles:
    - base_config
    - routing

- name: "GIAI DOAN 2 — VLAN (chi leaf SR Linux)"
  hosts: leaf1
  gather_facts: false
  collections: [nokia.srlinux]
  roles:
    - vlan_port
```

Chạy:
```bash
ansible-playbook -i inventory/hosts.yml deploy.yml
```

### (v) Kiểm tra
Xem bảng **PLAY RECAP** cuối cùng: `failed=0`, `unreachable=0`. Vào thử 1 thiết bị xem cấu hình có thật không:
```bash
# FRR
docker exec clab-datn-lab-edge1 vtysh -c "show running-config" | head
# SR Linux (hostname phải = spine1)
ssh admin@172.20.20.11 "info from state system name"
```

> **Khái niệm mới:** *Template Jinja2* = file cấu hình có `{{ biến }}` và `{% if %}`; Ansible "render" (điền giá trị) → ra cấu hình thật cho từng thiết bị. *vtysh* = CLI của FRR; `vtysh -f file` = nạp cấu hình từ file. *Idempotent* = chạy lại nhiều lần vẫn an toàn; task nào đã đúng thì báo `ok` (không `changed`).

---

<a name="phần-8"></a>
## Phần 8 — Phần an ninh: CIS + hardening + chấm điểm

> **Đây là phần trọng tâm "an ninh" của đồ án (phần của Tùng).** Gồm 3 mảnh khớp nhau: **policy** (định nghĩa luật) → **hardening** (vá) → **score** (đo).

### 8.1 — Policy: mã hóa chuẩn CIS thành luật (Compliance-as-Code)

**(?) Vì sao:** thay vì con người dò tay, ta viết mỗi yêu cầu an ninh thành 1 "luật" máy kiểm tra được (bằng biểu thức regex trên văn bản cấu hình).

**(>) Làm — `compliance/policy/cis_rules.yaml`:**
```yaml
weights:            # điểm theo mức nghiêm trọng (dùng để tính %)
  high: 5
  medium: 3
  low: 1

rules:
  - id: CIS-1.1
    title: "Cam dich vu Telnet (chi dung SSH)"
    severity: high
    applies_to: all            # all | frr | srlinux
    check:
      type: must_not_contain   # không được chứa mẫu này thì mới ĐẠT
      pattern: '(?im)^\s*(telnet\s+server|transport\s+input\s+telnet)'
    remediation: "Xoa telnet server; chi bat SSHv2."
  - id: CIS-7.2
    title: "Ma hoa mat khau luu trong cau hinh"
    severity: high
    applies_to: all
    check:
      type: must_contain       # phải chứa mẫu này thì mới ĐẠT
      pattern: '(?im)(service\s+password-encryption|hashed-password)'
    remediation: "Bat service password-encryption."
  # ... viết tiếp cho đủ ~18 luật ...
```
> *regex* = "mẫu tìm kiếm chữ". `must_contain` = có mẫu → đạt; `must_not_contain` = không có mẫu → đạt. `applies_to` để lọc luật theo nền tảng (vài luật chỉ hợp với FRR).

### 8.2 — Role hardening: tự động VÁ các luật đó

**(?) Vì sao:** mỗi task hardening tương ứng 1 luật CIS; chạy xong thì cấu hình thiết bị thỏa luật → điểm tăng.

**(>) Làm — `roles/hardening/tasks/`:** cũng theo mẫu `main.yml` rẽ nhánh. Ví dụ `frr.yml`:
```yaml
---
- name: "[harden/frr] Sinh cau hinh hardening tu template"
  ansible.builtin.template:
    src: hardening_frr.j2
    dest: /etc/frr/hardening.conf
- name: "[harden/frr] Ap dung"
  ansible.builtin.shell: vtysh -f /etc/frr/hardening.conf
  changed_when: true
- name: "[harden/frr] CIS-1.1 Tat telnet"
  ansible.builtin.shell: killall telnetd 2>/dev/null || true
  changed_when: false
- name: "[harden/frr] CIS-3.1 Banner"
  ansible.builtin.copy: { content: "{{ banner_text }}", dest: /etc/motd }
```
Template `hardening_frr.j2` chứa các lệnh vá: `service password-encryption`, `access-list mgmt-in permit {{ allowed_mgmt_cidr }}`, `exec-timeout ...`. Với SR Linux, `srlinux.yml` dùng `nokia.srlinux.config` đặt `/system/banner`, `/acl/...`, `/system/ntp`, v.v.

Các **công tắc bật/tắt** từng biện pháp đặt ở `roles/hardening/defaults/main.yml`:
```yaml
---
harden_disable_telnet: true
harden_set_banner: true
harden_mgmt_acl: true
harden_session_timeout: true
harden_password_encryption: true
# ...
```

Playbook `harden.yml`:
```yaml
---
- name: "Chuan hoa an ninh CIS"
  hosts: all
  gather_facts: false
  collections: [nokia.srlinux]
  roles: [hardening]
```

### 8.3 — Công cụ chấm điểm

**(?) Vì sao:** cần "thước" đo mức tuân thủ trước/sau, xuất báo cáo.

**(>) Làm — `compliance/tools/score.py`** (logic cốt lõi):
1. Đọc SoT (biết thiết bị + OS), đọc policy (các luật).
2. Với mỗi thiết bị, đọc file cấu hình `compliance/configs/<thư-mục>/<tên>.cfg`.
3. Lọc luật theo `applies_to`, chạy regex → ĐẠT/VI PHẠM.
4. Tính **điểm có trọng số**: `điểm = tổng_trọng_số_đạt / tổng_trọng_số × 100`.
5. In bảng + ghi `reports/compliance.json` và `.html`.

Có 3 thư mục cấu hình để minh họa/đo:
- `configs/golden/` — bản **trước** hardening (còn lỗ hổng) → chấm ra ~54%.
- `configs/after/`  — bản **sau** hardening → 100%.
- `configs/live/`   — bản **chụp thật** từ thiết bị (role backup ghi vào, Phần 9).

Chạy:
```bash
python3 compliance/tools/score.py --sot sot/devices.yaml \
  --policy compliance/policy/cis_rules.yaml --configs compliance/configs/golden
# so sánh trước/sau:
python3 compliance/tools/score.py --sot sot/devices.yaml \
  --policy compliance/policy/cis_rules.yaml \
  --compare compliance/configs/golden compliance/configs/after
```

### (v) Kiểm tra
- `score ... --configs golden` → tổng ~54%.
- Chạy `harden.yml` trên lab, rồi **backup** (Phần 9) để đổ cấu hình thật vào `configs/live/`, rồi `score --configs compliance/configs/live` → điểm tăng.
- Mở `compliance/reports/compliance.html` bằng trình duyệt.

> **Lưu ý trung thực (quan trọng khi bảo vệ):** `golden`/`after` là file mẫu minh họa quy trình. Con số đo trên **thiết bị thật** là `score live` (sau khi deploy+harden+backup). Nếu `live` chưa đạt 100%, giải thích: chấm bằng regex trên văn bản cấu hình là phép đơn giản hóa; hướng cải tiến là phân tích cấu trúc cấu hình thay vì so khớp chuỗi.

---

<a name="phần-9"></a>
## Phần 9 — Sao lưu, drift, benchmark, risk, scan

### 9.1 — `backup_restore` (sao lưu + chụp cấu hình thật vào `configs/live/`)
**(?)** Lưu lại running-config để rollback, và tạo nguồn cho `score live`.
**(>)** Role `backup_restore` với `frr.yml` (chạy `vtysh -c "show running-config"` rồi lưu) và `srlinux.yml` (lấy config qua API), ghi ra `backups/` và `compliance/configs/live/`. Playbook `backup.yml` gọi role này.
**(v)** Sau `ansible-playbook backup.yml` → có file trong `compliance/configs/live/*.cfg`.

### 9.2 — `scripts/drift_check.py` (phát hiện trôi cấu hình)
**(?)** So cấu hình **thật hiện tại** với bản chuẩn (baseline), chỉ ra dòng thừa/thiếu; có `--fix` để tự chạy lại deploy+harden.
**(>)** Logic: lấy live (SSH/`info flat`) → so với `configs/after/<tên>.cfg` bằng `difflib` → báo DRIFT/OK.
**(v)** `python3 scripts/drift_check.py` → in `OK`/`DRIFT` từng thiết bị.

### 9.3 — `scripts/benchmark.py` (đo tự động vs thủ công)
**(?)** Chứng minh lợi ích: đo **thật** thời gian chạy playbook (bằng `time.time()`), so với **số ước lượng** làm tay (ghi cứng trong code), tính "tăng tốc Nx".
**(>)** Chạy `ansible-playbook` cho deploy/harden/backup, bấm giờ, so với `MANUAL_ESTIMATES`.
**(v)** `python3 scripts/benchmark.py` → bảng tăng tốc. (Nhớ: số "thủ công" là ước lượng — nói rõ khi bảo vệ.)

### 9.4 — `scripts/risk_assessment.py` (ma trận rủi ro + MTTR)
**(?)** Đánh giá rủi ro trước/sau + thời gian khắc phục trung bình (MTTR).
**(v)** `python3 scripts/risk_assessment.py` → in ma trận rủi ro.

### 9.5 — `security/attacks/network_scan.py` (quét an ninh)
**(?)** Quét cổng mở / dịch vụ nguy hiểm trên 6 thiết bị (nmap hoặc socket Python) → đo "bề mặt tấn công".
**(v)** `python3 security/attacks/network_scan.py --output scan_result.json`.

---

<a name="phần-10"></a>
## Phần 10 — Dashboard web

**(?) Vì sao:** để trình bày trực quan (sơ đồ mạng, điểm tuân thủ, so sánh) khi demo.
**(>) Làm — `dashboard/app.py`:** một web server **Flask** nhỏ + **SQLite**, đọc các báo cáo JSON ở `compliance/reports/` và render ra các trang HTML (`templates/`). Chạy ở cổng 5000.
```bash
python3 dashboard/app.py          # mở http://localhost:5000
```
**(v)** Mở trình duyệt vào `http://<ip-may-linux>:5000` thấy điểm + biểu đồ.

> **Khái niệm mới:** *Flask* = thư viện Python để làm web nhỏ. *SQLite* = cơ sở dữ liệu gọn trong 1 file, không cần cài server.

---

<a name="phần-11"></a>
## Phần 11 — run.sh: gói tất cả thành 1 cửa

**(?) Vì sao:** gõ lệnh dài nhiều lần rất mệt và dễ sai khi demo. `run.sh` là script điều phối, mỗi lệnh ngắn gọi xuống playbook/script tương ứng.
**(>) Làm — `run.sh`:** một `case "$1"` với các nhánh `lab-up / ping / deploy / harden / backup / score / drift / benchmark / risk / scan / dashboard / demo`. Mỗi nhánh chỉ gọi lệnh thật (vd `deploy` → `ansible-playbook -i inventory/hosts.yml deploy.yml`).
```bash
chmod +x run.sh
./run.sh help
```
**(v)** `./run.sh help` liệt kê đủ lệnh; `./run.sh demo` chạy tuần tự cả pipeline.

---

<a name="phần-12"></a>
## Phần 12 — Chạy toàn bộ & chuẩn bị bảo vệ

### (>) Trình tự chạy "sạch" từ đầu
```bash
source .venv/bin/activate
python3 scripts/sot_to_inventory.py     # 1. sinh inventory từ SoT
./run.sh lab-up                          # 2. dựng lab 6 thiết bị
./run.sh ping                            # 3. bắt tay Ansible (6x pong)
./run.sh deploy                          # 4. cấu hình nền + định tuyến
./run.sh score golden                    # 5. điểm TRƯỚC (~54%)
./run.sh harden                          # 6. vá an ninh CIS
./run.sh backup                          # 7. chụp cấu hình thật -> live/
./run.sh score live                      # 8. điểm trên thiết bị THẬT
./run.sh score compare                   # 9. bảng trước/sau (demo)
./run.sh drift                           # 10. kiểm tra trôi cấu hình
./run.sh scan                            # 11. quét an ninh
./run.sh benchmark                       # 12. đo hiệu quả
./run.sh risk                            # 13. rủi ro + MTTR
./run.sh dashboard                       # 14. web trực quan
```

### Checklist nắm chắc trước khi bảo vệ
- [ ] Giải thích được **SoT** là gì và vì sao "mọi thứ bắt nguồn từ 1 file".
- [ ] Phân biệt **Docker / Containerlab / Ansible** (3 tầng: chạy container / dựng topology / cấu hình).
- [ ] Hiểu **idempotent** và đọc được **PLAY RECAP** (ok/changed/failed).
- [ ] Vì sao FRR dùng **SSH + template + vtysh**, còn SR Linux dùng **API**.
- [ ] Cách **chấm điểm có trọng số** (high=5, medium=3, low=1) → ra 61.7% thế nào.
- [ ] Trung thực về **golden/after là mẫu**, còn `score live` mới là thiết bị thật.
- [ ] Số **benchmark "thủ công" là ước lượng**, số "tự động" là đo thật.
- [ ] Mạch an ninh: **policy (phát hiện) → hardening (vá) → score (đo lại)**.

### Khi gặp lỗi — chẩn đoán nhanh
| Triệu chứng | Nguyên nhân thường gặp |
|-------------|------------------------|
| `clab` không có | Chưa cài Containerlab (Phần 1) |
| `docker permission denied` | Chưa đăng xuất/đăng nhập lại sau `usermod -aG docker` |
| ping FRR `UNREACHABLE` | Chưa `docker cp` khóa SSH vào container (Phần 4) |
| ping SRL `UNREACHABLE` | Sai mật khẩu/port trong `group_vars/srlinux/vars.yml` |
| playbook `failed` ở task template | Thiếu biến (kiểm tra SoT/group_vars có đủ chưa) |
| `score` ra 0% / bỏ qua thiết bị | Thiếu file `.cfg` trong thư mục configs tương ứng |
| Lỗi YAML | Dùng Tab thay vì dấu cách; sai thụt lề |

---

> **Lời khuyên cuối:** làm xong mỗi phần hãy **git commit** (`git add -A && git commit -m "phan X"`). Vừa lưu tiến độ, vừa có "lịch sử" để kể lại quá trình làm khi bảo vệ. Và nhớ: hiểu **tại sao** quan trọng hơn thuộc lòng lệnh — hội đồng hỏi "vì sao", không hỏi "gõ gì".
