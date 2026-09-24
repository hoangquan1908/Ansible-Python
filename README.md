# Tu dong hoa cau hinh & kiem soat tuan thu an ninh mang
### Do an tot nghiep — Ansible + Python | Nhom 3 nguoi (Quan, Chung, Tung)

Repo dung chung cho ca nhom. **Mot Nguon du lieu tin cay (SoT)** o `sot/`, moi
cau hinh va phep kiem tra deu bat nguon tu do.

## Tong quan he thong

- **6 thiet bi** mang doanh nghiep: 2 FRRouting + 4 Nokia SR Linux
- **3 tang** (Edge – Spine – Leaf) voi **eBGP multi-AS**
- **18 luat CIS Benchmark** kiem soat tuan thu an ninh
- **Web dashboard** (Flask) hien thi diem, so sanh, so lieu danh gia
- **Security scanner** quet cong mo va dich vu nguy hiem
- **Drift detection** phat hien va khac phuc troi cau hinh
- **Benchmark** do hieu qua tu dong vs thu cong
- **Risk assessment** ma tran rui ro + MTTR

## Phan chia theo thanh vien

| Thu muc | Chu tri | Noi dung |
|---|---|---|
| `sot/` | **Quan** (ca nhom dung) | Nguon du lieu tin cay: thiet bi, VLAN, cong, tham so |
| `inventory/`, `lab/` | **Chung** | Inventory Ansible (sinh tu SoT) + topo Containerlab |
| `roles/base_config`, `vlan_port`, `routing`, `backup_restore` | **Chung** | Cau hinh nen tang, VLAN/cong, dinh tuyen, sao luu/rollback |
| `roles/hardening`, `security/` | **Tung** | Chuan hoa an ninh (CIS) + quet an ninh doi chung |
| `compliance/`, `dashboard/` | **Quan** | Chinh sach CIS dang ma, cong cu cham diem, web dashboard |
| `scripts/drift_check.py`, `benchmark.py` | **Chung** | Phat hien troi cau hinh + do hieu qua van hanh |
| `scripts/risk_assessment.py` | **Tung** | Danh gia rui ro va MTTR |
| `playbooks/` | Ca nhom | Diem vao chay tung khoi va toan he thong |
| `docs/` | Ca nhom | Thuyet minh, kien truc, so lieu danh gia |

## Cay thu muc

```
.
├─ sot/devices.yaml              # Nguon du lieu tin cay (SoT v2.0 — 6 thiet bi)
├─ inventory/
│  ├─ hosts.yml                  # sinh tu SoT: python scripts/sot_to_inventory.py
│  └─ group_vars/
│     ├─ all.yml
│     ├─ srlinux/{vars,vault}.yml  # HTTPAPI + ansible-vault
│     └─ frr.yml                   # SSH key auth
├─ lab/topo.clab.yml             # topo Containerlab (4 SRL + 2 FRR, 3 tang)
├─ roles/
│  ├─ base_config/               # Chung — cau hinh hostname, NTP, syslog, banner
│  ├─ routing/                   # Chung — eBGP, IP interface, loopback
│  ├─ vlan_port/                 # Chung — VLAN L2 tren SR Linux
│  ├─ hardening/                 # Tung — chuan hoa an ninh CIS
│  └─ backup_restore/            # Chung — sao luu + rollback
├─ deploy.yml                    # Playbook: trien khai cau hinh
├─ harden.yml                    # Playbook: chuan hoa an ninh
├─ backup.yml                    # Playbook: sao luu cau hinh
├─ playbooks/
│  ├─ site.yml                   # chay toan bo vong khep kin
│  └─ compliance.yml             # thu thap config + cham diem
├─ compliance/                   # Module cham diem tuan thu
│  ├─ policy/cis_rules.yaml      # 18 luat CIS (11 nhom)
│  ├─ configs/{golden,after,live}/
│  ├─ tools/score.py             # Cong cu cham diem + so sanh + bao cao HTML
│  └─ reports/                   # JSON/HTML bao cao
├─ security/                     # Module quet an ninh mang
│  ├─ attacks/network_scan.py    # Port scan (nmap hoac Python socket)
│  └─ reports/
├─ dashboard/                    # Web dashboard
│  ├─ app.py                     # Flask server + SQLite
│  └─ templates/                 # 5 trang: base, index, topology, devices, metrics
├─ scripts/
│  ├─ sot_to_inventory.py        # Sinh inventory tu SoT
│  ├─ drift_check.py             # Phat hien troi cau hinh
│  ├─ benchmark.py               # Do hieu qua van hanh
│  └─ risk_assessment.py         # Danh gia rui ro + MTTR
├─ run.sh                        # Script dieu phoi (13 lenh)
├─ docs/
│  ├─ architecture.md            # Kien truc tong the
│  ├─ BANG_DANH_GIA.md           # So lieu danh gia thuc nghiem
│  └─ LO_TRINH_HOAN_THIEN.md    # Trang thai hoan thien
├─ ansible.cfg  requirements.yml  requirements.txt  .gitignore
```

## Cai dat nhanh

```bash
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml
```

## Cach chay nhanh (run.sh)

```bash
./run.sh help        # Xem huong dan
./run.sh lab-up      # Khoi tao lab 6 thiet bi (can sudo)
./run.sh ping        # Kiem tra ket noi Ansible
./run.sh deploy      # Trien khai cau hinh
./run.sh harden      # Ap dung chuan hoa an ninh
./run.sh backup      # Sao luu cau hinh
./run.sh scan        # Quet an ninh mang
./run.sh score golden   # Cham diem truoc hardening
./run.sh score after    # Cham diem sau hardening
./run.sh score compare  # So sanh truoc/sau
./run.sh drift       # Kiem tra troi cau hinh
./run.sh benchmark   # Do hieu qua van hanh
./run.sh risk        # Danh gia rui ro & MTTR
./run.sh dashboard   # Khoi dong web dashboard (port 5000)
./run.sh demo        # Chay demo toan bo he thong
```

## Ket qua da kiem chung

### Tuan thu an ninh

| Chi so | Truoc hardening | Sau hardening | Cai thien |
|--------|----------------|---------------|-----------|
| Diem tuan thu TB | **54.3%** | **100.0%** | +45.7% |
| So vi pham CIS | 41 | 0 | -41 (100%) |

### Hieu qua van hanh

| Chi so | Thu cong | Tu dong | Cai thien |
|--------|---------|---------|-----------|
| Thoi gian trien khai | 90 phut | 1.11 phut | Nhanh 81.1x |
| So thao tac | 138 buoc | 3 lenh | Giam 97.8% |
| MTTR khac phuc | ~30 phut | 16 giay | Nhanh 112.5x |
| Ti le loi | 15-20% | 0% | Giam 100% |

Xem chi tiet: `docs/BANG_DANH_GIA.md` | Kien truc: `docs/architecture.md`
