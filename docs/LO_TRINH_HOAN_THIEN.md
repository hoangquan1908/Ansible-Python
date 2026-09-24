# Lo trinh hoan thien Do an tot nghiep

> **De tai:** Tu dong hoa cau hinh va kiem soat tuan thu an ninh mang
> **Nhom:** Quan, Chung, Tung (3 nguoi)
> **Ngay danh gia:** 2026-09-24

---

## 1. Trang thai hien tai — TAT CA DA HOAN THANH

| # | Hang muc | Trang thai | Chi tiet |
|---|----------|-----------|----------|
| 1 | SoT v2.0 | XONG | `sot/devices.yaml` — 6 thiet bi, 3 tang (Edge-Spine-Leaf) |
| 2 | Lab Containerlab | XONG | `lab/topo.clab.yml` — 6 node (4 SRL + 2 FRR), da kiem chung |
| 3 | Inventory Ansible | XONG | `inventory/hosts.yml` — tu sinh tu SoT, 6 thiet bi |
| 4 | 5 Role Ansible | XONG | base_config, routing, vlan_port, hardening, backup_restore |
| 5 | Playbook chinh | XONG | deploy.yml, harden.yml, backup.yml — 6/6 OK |
| 6 | Playbook phu | XONG | playbooks/site.yml, compliance.yml — da dong bo |
| 7 | Compliance Engine | XONG | `compliance/tools/score.py` — 18 luat CIS, cham diem + so sanh |
| 8 | Golden + After configs | XONG | 6 golden (54.3%) + 6 after (100.0%) |
| 9 | Security Scanner | XONG | Port scan (nmap + Python fallback), so sanh truoc/sau |
| 10 | Web Dashboard | XONG | Flask + SQLite — 4 trang (Tong quan, Thiet bi, So lieu, Topology) |
| 11 | Script tien ich | XONG | `run.sh` — 13 lenh (lab, deploy, harden, backup, scan, score, drift, benchmark, risk, dashboard, demo) |
| 12 | Drift Detection | XONG | `scripts/drift_check.py` — phat hien + khac phuc troi cau hinh |
| 13 | Ansible Vault | XONG | Mat khau SRL ma hoa, vault-pass.txt trong .gitignore |
| 14 | Benchmark | XONG | `scripts/benchmark.py` — do hieu qua tu dong vs thu cong |
| 15 | Risk Assessment | XONG | `scripts/risk_assessment.py` — ma tran rui ro + MTTR |
| 16 | Bang danh gia | XONG | `docs/BANG_DANH_GIA.md` — so lieu thuc nghiem day du |
| 17 | Tai lieu | XONG | README.md, architecture.md, HUONG_DAN_QUAN.md, BANG_DANH_GIA.md |

---

## 2. Ket qua kiem chung (2026-09-24)

### Ansible Playbooks — 6/6 thiet bi, 0 failures

| Playbook | edge1 | spine1 | spine2 | leaf1 | leaf2 | leaf3 |
|----------|-------|--------|--------|-------|-------|-------|
| deploy.yml | OK | OK | OK | OK | OK | OK |
| harden.yml | OK | OK | OK | OK | OK | OK |
| backup.yml | OK | OK | OK | OK | OK | OK |

### Diem tuan thu CIS

| Thiet bi | Truoc hardening | Sau hardening | Cai thien |
|----------|----------------|---------------|-----------|
| edge1 | 61.7% | 100.0% | +38.3% |
| spine1 | 48.9% | 100.0% | +51.1% |
| spine2 | 55.6% | 100.0% | +44.4% |
| leaf1 | 42.2% | 100.0% | +57.8% |
| leaf2 | 44.4% | 100.0% | +55.6% |
| leaf3 | 66.7% | 100.0% | +33.3% |
| **TOAN HE THONG** | **54.3%** | **100.0%** | **+45.7%** |

### Hieu qua van hanh

| Playbook | Tu dong | Thu cong | Tang toc | Tiet kiem |
|----------|---------|----------|----------|-----------|
| deploy.yml | 43.1s | 45 phut | 62.5x | 44.3 phut |
| harden.yml | 15.8s | 30 phut | 115.4x | 29.7 phut |
| backup.yml | 7.6s | 15 phut | 115.4x | 14.9 phut |
| **Tong** | **1.11 phut** | **90 phut** | **81.1x** | **88.9 phut** |

### MTTR & Rui ro

- MTTR tu dong: 16.0s (vs ~30 phut thu cong = 112.5x)
- Vi pham: 41 → 0 (100% da khac phuc)
- Rui ro: CAO → THAP (5/5 loai)

### BGP Sessions — Tat ca established

- edge1: 2 neighbors (spine1 AS65010, spine2 AS65020)
- spine1: 3 neighbors (edge1 AS65000, leaf1 AS65101, leaf2 AS65102)
- spine2: 3 neighbors (edge1 AS65000, leaf2 AS65102, leaf3 AS65103)

### Web Dashboard

- http://localhost:5000 — 4 trang hoat dong
- Trang moi: /metrics — hien thi toan bo so lieu danh gia
- API: /api/scan, /api/compare, /api/history, /api/scan/<id>, /api/metrics

---

## 3. Cach chay lai

```bash
# Khoi tao lab (lan dau hoac sau khi tat may)
./run.sh lab-up

# Chay toan bo
./run.sh demo

# Hoac tung buoc
./run.sh deploy     # Trien khai cau hinh
./run.sh harden     # Chuan hoa an ninh
./run.sh backup     # Sao luu cau hinh
./run.sh score compare  # So sanh truoc/sau
./run.sh scan       # Quet an ninh
./run.sh drift      # Kiem tra troi cau hinh
./run.sh benchmark  # Do hieu qua van hanh
./run.sh risk       # Danh gia rui ro & MTTR
./run.sh dashboard  # Web dashboard (port 5000)
```

---

## 4. Phan cong nghien cuu

| Thanh vien | Phan chiu trach nhiem | File/Thu muc can doc |
|------------|----------------------|---------------------|
| **Chung** | Ansible roles, Jinja2 template, lab, routing eBGP, drift detection, benchmark | `roles/base_config/`, `roles/routing/`, `roles/vlan_port/`, `lab/`, `sot/`, `inventory/`, `scripts/drift_check.py`, `scripts/benchmark.py` |
| **Tung** | Hardening CIS, security scan, ansible-vault, risk assessment, MTTR | `roles/hardening/`, `security/`, `compliance/policy/`, `scripts/risk_assessment.py`, `inventory/group_vars/srlinux/vault.yml` |
| **Quan** | Compliance engine, web dashboard, SoT, bao cao, tong hop so lieu | `compliance/tools/`, `dashboard/`, `sot/`, `compliance/policy/`, `docs/BANG_DANH_GIA.md` |

### Huong dan doc code

1. Bat dau tu `sot/devices.yaml` — hieu cau truc du lieu tin cay
2. Doc `docs/architecture.md` — hieu vong khep kin
3. Doc role tuong ung voi phan viec cua minh
4. Chay `./run.sh demo` de thay ket qua thuc te
5. Mo dashboard `./run.sh dashboard` de xem giao dien web
6. Doc `docs/BANG_DANH_GIA.md` — so lieu danh gia thuc nghiem

---

## 5. Cac giai doan theo lo trinh

| Giai doan | Trang thai | Ghi chu |
|-----------|-----------|---------|
| A. Don repo & chuan hoa | XONG | run.sh, gitignore, docs |
| B. Chay lab & thu so lieu | XONG | 6/6 OK, so lieu truoc/sau day du |
| C1. Drift detection | XONG | scripts/drift_check.py |
| C2. Ansible vault | XONG | group_vars/srlinux/vault.yml |
| C3. Benchmark van hanh | XONG | scripts/benchmark.py — 81.1x |
| C4. Rui ro & MTTR | XONG | scripts/risk_assessment.py — 112.5x |
| C5. Tong hop dashboard | XONG | /metrics page + /api/metrics |
| D. Bang danh gia | XONG | docs/BANG_DANH_GIA.md |
| E. Viet thuyet minh | CON LAI | 6 chuong, nhom tu viet |
| F. Slide + demo + bao ve | CON LAI | Nhom tu chuan bi |
