#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DO GIAM RUI RO VA MTTR (Mean Time To Remediate) — KB-C4
========================================================
Phan viec cua Tung.

Tinh toan muc giam rui ro va thoi gian khac phuc trung binh
dua tren ket qua cham diem tuan thu va quet an ninh truoc/sau hardening.

Chay:
  python scripts/risk_assessment.py
"""
import datetime as dt
import json
import time
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "compliance" / "reports"
SECURITY_DIR = REPO / "security" / "reports"


def load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def measure_mttr() -> float:
    """Do MTTR: thoi gian chay harden.yml (= thoi gian khac phuc vi pham)."""
    start = time.time()
    r = subprocess.run(
        ["ansible-playbook", "-i", "inventory/hosts.yml", "harden.yml"],
        capture_output=True, text=True, timeout=600,
        cwd=str(REPO),
    )
    return round(time.time() - start, 1)


def main():
    print(f"\n{'='*70}")
    print(f"BAO CAO RUI RO & MTTR — {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    compliance_before = load_json(REPORTS_DIR / "compliance.json")
    comparison = load_json(REPORTS_DIR / "comparison.json")
    scan_before = load_json(SECURITY_DIR / "scan_before.json")
    scan_after = load_json(SECURITY_DIR / "scan_after.json")

    report = {
        "assessed_at": dt.datetime.now().isoformat(),
        "compliance": {},
        "attack_surface": {},
        "mttr": {},
        "risk_matrix": [],
    }

    if comparison:
        before_score = comparison.get("before", {}).get("overall_score", 0)
        after_score = comparison.get("after", {}).get("overall_score", 0)
        improvement = comparison.get("improvement", 0)

        before_devices = comparison.get("before", {}).get("devices", [])
        after_devices = comparison.get("after", {}).get("devices", [])
        violations_before = sum(d.get("n_violations", 0) for d in before_devices)
        violations_after = sum(d.get("n_violations", 0) for d in after_devices)

        report["compliance"] = {
            "score_before": before_score,
            "score_after": after_score,
            "improvement_pct": improvement,
            "violations_before": violations_before,
            "violations_after": violations_after,
            "violations_fixed": violations_before - violations_after,
            "fix_rate_pct": round((violations_before - violations_after) / violations_before * 100, 1) if violations_before > 0 else 0,
        }

        print(f"\n  TUAN THU CIS:")
        print(f"    Diem truoc:    {before_score}%")
        print(f"    Diem sau:      {after_score}%")
        print(f"    Cai thien:     +{improvement}%")
        print(f"    Vi pham:       {violations_before} -> {violations_after} (da sua {violations_before - violations_after})")

    if scan_before:
        ports_before = scan_before.get("summary", {}).get("total_open_ports", 0)
        risky_before = scan_before.get("summary", {}).get("total_risky_services", 0)
    else:
        ports_before = 0
        risky_before = 0

    if scan_after:
        ports_after = scan_after.get("summary", {}).get("total_open_ports", 0)
        risky_after = scan_after.get("summary", {}).get("total_risky_services", 0)
    else:
        ports_after = ports_before
        risky_after = risky_before

    if ports_before > 0:
        reduction_pct = round((risky_before - risky_after) / risky_before * 100, 1) if risky_before > 0 else 0
        report["attack_surface"] = {
            "open_ports_before": ports_before,
            "open_ports_after": ports_after,
            "risky_services_before": risky_before,
            "risky_services_after": risky_after,
            "risk_reduction_pct": reduction_pct,
        }

        print(f"\n  BE MAT TAN CONG:")
        print(f"    Cong mo:         {ports_before} -> {ports_after}")
        print(f"    Dich vu nguy hiem: {risky_before} -> {risky_after}")
        print(f"    Giam rui ro:     {reduction_pct}%")

    print(f"\n  DO MTTR (thoi gian khac phuc)...")
    mttr_seconds = measure_mttr()
    mttr_manual_minutes = 30

    report["mttr"] = {
        "auto_seconds": mttr_seconds,
        "auto_minutes": round(mttr_seconds / 60, 2),
        "manual_estimate_minutes": mttr_manual_minutes,
        "speedup": round(mttr_manual_minutes * 60 / mttr_seconds, 1) if mttr_seconds > 0 else 0,
    }

    print(f"    MTTR tu dong:  {mttr_seconds}s ({round(mttr_seconds / 60, 2)} phut)")
    print(f"    MTTR thu cong: ~{mttr_manual_minutes} phut (uoc tinh)")
    print(f"    Tang toc:      {report['mttr']['speedup']}x")

    risk_levels = [
        {"category": "Truy cap trai phep (Telnet)", "before": "CAO", "after": "THAP",
         "mitigation": "Tat Telnet, chi SSH"},
        {"category": "Lo thong tin (SNMP public)", "before": "CAO", "after": "THAP",
         "mitigation": "Xoa community public, dung SNMPv3"},
        {"category": "Tan cong brute-force", "before": "TRUNG BINH", "after": "THAP",
         "mitigation": "ACL, timeout, login auth"},
        {"category": "Mat khau ban ro", "before": "CAO", "after": "THAP",
         "mitigation": "password-encryption, vault"},
        {"category": "Troi cau hinh", "before": "TRUNG BINH", "after": "THAP",
         "mitigation": "Drift detection tu dong"},
    ]
    report["risk_matrix"] = risk_levels

    print(f"\n  MA TRAN RUI RO:")
    print(f"    {'Loai rui ro':<35} {'Truoc':<12} {'Sau':<12}")
    print(f"    {'-'*59}")
    for r in risk_levels:
        print(f"    {r['category']:<35} {r['before']:<12} {r['after']:<12}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "risk_assessment.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*70}")
    print(f"[+] Da ghi: {out_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
