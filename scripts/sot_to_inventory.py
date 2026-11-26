#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sinh inventory Ansible TU Nguon du lieu tin cay (SoT).
Chi can sua 1 cho (sot/devices.yaml) la ca inventory tu cap nhat.

Chay:  python scripts/sot_to_inventory.py
       python scripts/sot_to_inventory.py --sot sot/scenarios/devices_12.yaml   # kich ban quy mo
"""
import argparse
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parent.parent
SOT = REPO / "sot/devices.yaml"
OUT = REPO / "inventory/hosts.yml"


def main():
    sot = yaml.safe_load(SOT.read_text(encoding="utf-8"))
    groups: dict[str, dict] = {}
    for d in sot["devices"]:
        g = groups.setdefault(d["os"], {"hosts": {}})
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
        f"# TU SINH tu {SOT.relative_to(REPO) if SOT.is_relative_to(REPO) else SOT} — DUNG sua tay, sua o SoT roi chay lai.\n"
        + yaml.safe_dump(inventory, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    n = sum(len(g["hosts"]) for g in groups.values())
    print(f"Da sinh {OUT} voi {n} thiet bi thuoc {len(groups)} nhom: {', '.join(groups)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sinh inventory Ansible tu SoT.")
    ap.add_argument("--sot", default=str(SOT), help="file SoT (mac dinh sot/devices.yaml)")
    ap.add_argument("--out", default=str(OUT), help="file inventory dau ra")
    a = ap.parse_args()
    SOT = Path(a.sot) if Path(a.sot).is_absolute() else REPO / a.sot
    OUT = Path(a.out) if Path(a.out).is_absolute() else REPO / a.out
    main()
