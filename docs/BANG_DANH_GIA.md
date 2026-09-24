# Bang tong hop danh gia ket qua thuc nghiem

> **De tai:** Tu dong hoa cau hinh va kiem soat tuan thu an ninh mang
> **Moi truong:** 6 thiet bi mang (4 Nokia SR Linux + 2 FRRouting) tren Containerlab
> **Ngay do:** 2026-09-24

---

## 1. Hieu qua tuan thu an ninh (CIS Benchmark — 18 luat)

| Thiet bi | Vai tro | Nen tang | Truoc hardening | Sau hardening | Cai thien |
|----------|---------|----------|-----------------|---------------|-----------|
| edge1 | border | FRR | 61.7% | 100.0% | +38.3% |
| spine1 | distribution | SR Linux | 48.9% | 100.0% | +51.1% |
| spine2 | distribution | SR Linux | 55.6% | 100.0% | +44.4% |
| leaf1 | access | SR Linux | 42.2% | 100.0% | +57.8% |
| leaf2 | access | SR Linux | 44.4% | 100.0% | +55.6% |
| leaf3 | access | FRR | 66.7% | 100.0% | +33.3% |
| **Trung binh** | | | **54.3%** | **100.0%** | **+45.7%** |

- Tong so vi pham: 41 → 0 (da khac phuc 100%)
- Ti le dat chuan sau hardening: 6/6 thiet bi (100%)

---

## 2. Hieu qua van hanh — Tu dong vs Thu cong

| Playbook | Mo ta | Tu dong | Thu cong | Tang toc | Tiet kiem | Thao tac |
|----------|-------|---------|----------|----------|-----------|----------|
| deploy.yml | Cau hinh + dinh tuyen 6 TB | 43.1s | 45 phut | 62.5x | 44.3 phut | 1 vs 72 |
| harden.yml | Chuan hoa an ninh CIS | 15.8s | 30 phut | 115.4x | 29.7 phut | 1 vs 48 |
| backup.yml | Sao luu cau hinh | 7.6s | 15 phut | 115.4x | 14.9 phut | 1 vs 18 |
| **Tong** | **Toan bo pipeline** | **1.11 phut** | **90 phut** | **81.1x** | **88.9 phut** | **3 vs 138** |

- Ti le giam thao tac: 97.8% (138 buoc → 3 lenh)
- Ti le loi uoc tinh: 15-20% (thu cong) → 0% (tu dong, idempotent)

---

## 3. MTTR — Thoi gian khac phuc trung binh

| Chi so | Gia tri |
|--------|---------|
| MTTR tu dong (chay harden.yml) | 16.0 giay (0.27 phut) |
| MTTR thu cong (uoc tinh) | ~30 phut |
| Tang toc | 112.5x |
| So vi pham khac phuc / lan | 41 vi pham tren 6 thiet bi |

---

## 4. Ma tran rui ro

| Loai rui ro | Truoc | Sau | Bien phap giam thieu |
|-------------|-------|-----|---------------------|
| Truy cap trai phep (Telnet) | CAO | THAP | Tat Telnet, chi SSH |
| Lo thong tin (SNMP public) | CAO | THAP | Xoa community public, dung SNMPv3 |
| Tan cong brute-force | TRUNG BINH | THAP | ACL, timeout, login auth |
| Mat khau ban ro | CAO | THAP | password-encryption, ansible-vault |
| Troi cau hinh | TRUNG BINH | THAP | Drift detection tu dong |

---

## 5. Be mat tan cong (Security Scan)

| Chi so | Truoc | Sau | Ghi chu |
|--------|-------|-----|---------|
| Cong mo | 18 | 18 | Cong quan ly can thiet |
| Dich vu nguy hiem | 4 | 4 | HTTP port 80 tren SRL (management UI) |

> Ghi chu: 4 dich vu HTTP (port 80) tren SRL la management UI, khong the tat trong moi truong lab.
> Trong moi truong thuc te, se gioi han bang ACL hoac chuyen sang HTTPS-only.

---

## 6. Bang tong hop (dung cho Chuong 6 bao cao)

| STT | Chi so danh gia | Truoc / Thu cong | Sau / Tu dong | Cai thien |
|-----|----------------|------------------|----------------|-----------|
| 1 | Diem tuan thu CIS trung binh | 54.3% | 100.0% | +45.7% |
| 2 | So luat CIS vi pham (tong) | 41 | 0 | -41 (100%) |
| 3 | Thoi gian trien khai 6 TB | 90 phut | 1.11 phut | Nhanh 81.1x |
| 4 | So thao tac trien khai | 138 buoc | 3 lenh | Giam 97.8% |
| 5 | MTTR khac phuc vi pham | ~30 phut | 16 giay | Nhanh 112.5x |
| 6 | Ti le loi khi cau hinh | 15-20% | 0% | Giam 100% |
| 7 | Muc rui ro tong the | CAO | THAP | Giam dang ke |
| 8 | Kha nang phat hien troi | Khong co | Tu dong | Moi |
| 9 | Quan ly bi mat | Ban ro | Vault ma hoa | An toan |
| 10 | So thiet bi dat chuan | 0/6 | 6/6 | +6 |

---

## 7. Ket luan danh gia

He thong tu dong hoa dat duoc cac muc tieu chinh:

1. **Hieu qua van hanh**: giam 97.8% thao tac, tang toc 81x, tiet kiem ~89 phut/lan trien khai
2. **Tuan thu an ninh**: nang diem CIS tu 54.3% len 100.0%, khac phuc toan bo 41 vi pham
3. **Khac phuc nhanh**: MTTR giam tu 30 phut xuong 16 giay (nhanh 112.5x)
4. **Nhat quan**: idempotent, 0% ti le loi, cau hinh dong nhat tren 6 thiet bi
5. **Kiem soat lien tuc**: phat hien troi cau hinh tu dong, canh bao va khac phuc
