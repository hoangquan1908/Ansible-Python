#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DO HIEU QUA VAN HANH — Tu dong vs Thu cong (KB-C3)
===================================================
Phan viec cua Chung.

Do thoi gian va so thao tac khi trien khai cau hinh bang Ansible
so voi thao tac thu cong (uoc tinh).

Chay:
  python scripts/benchmark.py                     # do toan bo
  python scripts/benchmark.py --playbook deploy   # chi do deploy
"""
import argparse
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "compliance" / "reports"

MANUAL_ESTIMATES = {
    "deploy": {
        "description": "Cau hinh co ban + dinh tuyen 6 thiet bi",
        "manual_minutes": 45,
        "manual_steps": 72,
        "manual_errors_pct": 15,
        "notes": "SSH vao tung thiet bi, go lenh CLI, 12 lenh/thiet bi x 6 thiet bi",
    },
    "harden": {
        "description": "Chuan hoa an ninh CIS 6 thiet bi",
        "manual_minutes": 30,
        "manual_steps": 48,
        "manual_errors_pct": 20,
        "notes": "8 thay doi an ninh/thiet bi x 6 thiet bi, de sai sot khi go tay",
    },
    "backup": {
        "description": "Sao luu cau hinh 6 thiet bi",
        "manual_minutes": 15,
        "manual_steps": 18,
        "manual_errors_pct": 5,
        "notes": "SSH + copy paste running-config, 3 thao tac/thiet bi",
    },
}


def run_playbook(name: str) -> dict:
    """Chay 1 playbook va do thoi gian."""
    playbook = f"{name}.yml"
    start = time.time()
    r = subprocess.run(
        ["ansible-playbook", "-i", "inventory/hosts.yml", playbook],
        capture_output=True, text=True, timeout=600,
        cwd=str(REPO),
    )
    elapsed = time.time() - start

    ok_count = r.stdout.count("ok=")
    changed_count = r.stdout.count("changed=")

    return {
        "playbook": name,
        "auto_seconds": round(elapsed, 1),
        "auto_minutes": round(elapsed / 60, 2),
        "success": r.returncode == 0,
        "tasks_run": ok_count,
        "returncode": r.returncode,
    }


def main():
    ap = argparse.ArgumentParser(description="Do hieu qua van hanh.")
    ap.add_argument("--playbook", choices=["deploy", "harden", "backup"],
                    help="Chi do 1 playbook")
    ap.add_argument("--output", default="benchmark.json")
    args = ap.parse_args()

    playbooks = [args.playbook] if args.playbook else ["deploy", "harden", "backup"]

    print(f"\n{'='*70}")
    print(f"DO HIEU QUA VAN HANH — {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    results = []
    total_auto = 0
    total_manual = 0

    for pb in playbooks:
        print(f"\n[*] Chay {pb}.yml ...")
        auto = run_playbook(pb)
        manual = MANUAL_ESTIMATES[pb]

        auto_min = auto["auto_minutes"]
        manual_min = manual["manual_minutes"]
        speedup = round(manual_min / auto_min, 1) if auto_min > 0 else 0
        time_saved = round(manual_min - auto_min, 1)
        total_auto += auto_min
        total_manual += manual_min

        result = {
            "playbook": pb,
            "description": manual["description"],
            "auto_seconds": auto["auto_seconds"],
            "auto_minutes": auto_min,
            "manual_minutes": manual_min,
            "speedup_factor": speedup,
            "time_saved_minutes": time_saved,
            "manual_steps": manual["manual_steps"],
            "auto_steps": 1,
            "manual_error_rate_pct": manual["manual_errors_pct"],
            "auto_error_rate_pct": 0,
            "success": auto["success"],
        }
        results.append(result)

        status = "OK" if auto["success"] else "FAIL"
        print(f"    [{status}] {auto['auto_seconds']}s (tu dong) vs {manual_min}m (thu cong)")
        print(f"    Tang toc: {speedup}x | Tiet kiem: {time_saved} phut")
        print(f"    Thao tac: 1 lenh vs {manual['manual_steps']} buoc thu cong")

    report = {
        "measured_at": dt.datetime.now().isoformat(),
        "n_devices": 6,
        "results": results,
        "summary": {
            "total_auto_minutes": round(total_auto, 2),
            "total_manual_minutes": total_manual,
            "total_speedup": round(total_manual / total_auto, 1) if total_auto > 0 else 0,
            "total_time_saved_minutes": round(total_manual - total_auto, 1),
            "total_manual_steps": sum(r["manual_steps"] for r in results),
            "total_auto_steps": len(results),
        },
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / args.output
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*70}")
    s = report["summary"]
    print(f"TONG KET:")
    print(f"  Tu dong : {s['total_auto_minutes']} phut ({s['total_auto_steps']} lenh)")
    print(f"  Thu cong: {s['total_manual_minutes']} phut ({s['total_manual_steps']} buoc)")
    print(f"  Tang toc: {s['total_speedup']}x | Tiet kiem: {s['total_time_saved_minutes']} phut")
    print(f"{'='*70}")
    print(f"\n[+] Da ghi: {out_path}")


if __name__ == "__main__":
    main()
