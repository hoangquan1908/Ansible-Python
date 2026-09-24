#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHAT HIEN TROI CAU HINH (Configuration Drift Detection) — KB-12
================================================================
Phan viec cua Chung.

So sanh cau hinh hien tai tren thiet bi voi cau hinh chuan (SoT/golden).
Phat hien sai lech va tu dong khac phuc bang Ansible.

Chay:
  python scripts/drift_check.py                          # kiem tra tat ca
  python scripts/drift_check.py --fix                    # tu dong khac phuc
  python scripts/drift_check.py --target spine1          # chi 1 thiet bi
  python scripts/drift_check.py --baseline after         # so voi configs/after
"""
import argparse
import datetime as dt
import difflib
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SOT = REPO / "sot" / "devices.yaml"
REPORTS_DIR = REPO / "compliance" / "reports"


def collect_live_config(device_name: str, device_os: str, host: str) -> str:
    """Thu thap cau hinh hien tai tu thiet bi."""
    if device_os == "frr":
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-i",
             str(Path.home() / ".ssh/id_ed25519"),
             f"root@{host}", "vtysh -c 'show running-config'"],
            capture_output=True, text=True, timeout=30,
        )
        return r.stdout
    elif device_os == "srlinux":
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no",
             f"admin@{host}", "info flat"],
            capture_output=True, text=True, timeout=30,
        )
        return r.stdout
    return ""


def load_baseline(device_name: str, baseline_dir: str) -> str:
    """Doc cau hinh chuan tu file."""
    cfg_path = REPO / "compliance" / "configs" / baseline_dir / f"{device_name}.cfg"
    if cfg_path.exists():
        return cfg_path.read_text(encoding="utf-8")
    return ""


def normalize_config(text: str) -> list:
    """Chuan hoa: bo dong trong, comment, khoang trang thua."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("!") and not stripped.startswith("#"):
            if not any(skip in stripped.lower() for skip in
                       ["building configuration", "current configuration",
                        "frr version", "frr defaults"]):
                lines.append(stripped)
    return lines


def check_drift(device: dict, baseline_dir: str) -> dict:
    """Kiem tra troi cau hinh cua 1 thiet bi."""
    name = device["name"]
    os_type = device["os"]
    host = device["mgmt_ip"]

    result = {
        "device": name,
        "os": os_type,
        "ip": host,
        "checked_at": dt.datetime.now().isoformat(),
        "drifted": False,
        "added_lines": [],
        "removed_lines": [],
        "diff": "",
    }

    try:
        live = collect_live_config(name, os_type, host)
        baseline = load_baseline(name, baseline_dir)

        if not live:
            result["error"] = "Khong the thu thap cau hinh"
            return result
        if not baseline:
            result["error"] = f"Khong co file baseline ({baseline_dir}/{name}.cfg)"
            return result

        live_lines = normalize_config(live)
        base_lines = normalize_config(baseline)

        added = set(live_lines) - set(base_lines)
        removed = set(base_lines) - set(live_lines)

        if added or removed:
            result["drifted"] = True
            result["added_lines"] = sorted(added)
            result["removed_lines"] = sorted(removed)

            diff = difflib.unified_diff(
                base_lines, live_lines,
                fromfile=f"baseline/{name}", tofile=f"live/{name}",
                lineterm="",
            )
            result["diff"] = "\n".join(diff)

    except subprocess.TimeoutExpired:
        result["error"] = "Timeout khi ket noi"
    except Exception as e:
        result["error"] = str(e)

    return result


def fix_drift(fix_all: bool = False):
    """Khac phuc troi cau hinh bang cach chay lai deploy + harden."""
    print("\n[*] Khac phuc troi cau hinh — chay lai deploy.yml + harden.yml...")
    for playbook in ["deploy.yml", "harden.yml"]:
        print(f"    Chay {playbook}...")
        r = subprocess.run(
            ["ansible-playbook", "-i", "inventory/hosts.yml", playbook],
            capture_output=True, text=True, timeout=600,
            cwd=str(REPO),
        )
        if r.returncode != 0:
            print(f"    [!] {playbook} that bai")
            print(r.stderr[-500:])
            return False
        else:
            changed = r.stdout.count("changed=")
            print(f"    [OK] {playbook} hoan tat")
    print("[OK] Da khac phuc troi cau hinh")
    return True


def main():
    ap = argparse.ArgumentParser(description="Phat hien troi cau hinh.")
    ap.add_argument("--target", help="Ten thiet bi cu the")
    ap.add_argument("--baseline", default="after",
                    help="Thu muc baseline (golden|after, mac dinh: after)")
    ap.add_argument("--fix", action="store_true",
                    help="Tu dong khac phuc bang Ansible")
    ap.add_argument("--output", default="drift_report.json",
                    help="Ten file bao cao")
    args = ap.parse_args()

    sot = yaml.safe_load(SOT.read_text(encoding="utf-8"))
    devices = sot["devices"]
    if args.target:
        devices = [d for d in devices if d["name"] == args.target]
        if not devices:
            print(f"[!] Khong tim thay thiet bi: {args.target}")
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"KIEM TRA TROI CAU HINH — {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Baseline: {args.baseline} | Thiet bi: {len(devices)}")
    print(f"{'='*60}")

    report = {
        "checked_at": dt.datetime.now().isoformat(),
        "baseline": args.baseline,
        "devices": [],
        "summary": {"total": len(devices), "drifted": 0, "ok": 0, "error": 0},
    }

    for dev in devices:
        print(f"\n[*] Kiem tra {dev['name']} ({dev['mgmt_ip']})...")
        result = check_drift(dev, args.baseline)
        report["devices"].append(result)

        if result.get("error"):
            print(f"    [!] Loi: {result['error']}")
            report["summary"]["error"] += 1
        elif result["drifted"]:
            print(f"    [DRIFT] Phat hien sai lech!")
            print(f"      + Dong them : {len(result['added_lines'])}")
            print(f"      - Dong thieu: {len(result['removed_lines'])}")
            for line in result["removed_lines"][:5]:
                print(f"        - {line}")
            report["summary"]["drifted"] += 1
        else:
            print(f"    [OK] Khong co troi cau hinh")
            report["summary"]["ok"] += 1

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / args.output
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] Da ghi bao cao: {out_path}")

    print(f"\n{'='*60}")
    s = report["summary"]
    print(f"TONG KET: {s['ok']} OK / {s['drifted']} DRIFT / {s['error']} LOI")
    print(f"{'='*60}")

    if args.fix and report["summary"]["drifted"] > 0:
        fix_drift()

    return 0 if report["summary"]["drifted"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
