#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sinh inventory Ansible TU Nguon du lieu tin cay (SoT).
Chi can sua 1 cho (sot/devices.yaml) la ca inventory tu cap nhat.

Chay:  python scripts/sot_to_inventory.py
"""
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
        "# TU SINH tu sot/devices.yaml — DUNG sua tay, sua o SoT roi chay lai.\n"
        + yaml.safe_dump(inventory, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    n = sum(len(g["hosts"]) for g in groups.values())
    print(f"Da sinh {OUT} voi {n} thiet bi thuoc {len(groups)} nhom: {', '.join(groups)}")


if __name__ == "__main__":
    main()
