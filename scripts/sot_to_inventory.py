#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sinh inventory Ansible TỪ Nguồn dữ liệu tin cậy (SoT).
Nhờ vậy chỉ cần sửa 1 chỗ (sot/devices.yaml) là cả inventory tự cập nhật —
đúng nguyên tắc single source of truth.

Chạy:  python scripts/sot_to_inventory.py
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
        }
    inventory = {"all": {"children": {os: grp for os, grp in groups.items()}}}
    OUT.write_text(
        "# TỰ SINH từ sot/devices.yaml — ĐỪNG sửa tay, sửa ở SoT rồi chạy lại.\n"
        + yaml.safe_dump(inventory, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    n = sum(len(g["hosts"]) for g in groups.values())
    print(f"Đã sinh {OUT} với {n} thiết bị thuộc {len(groups)} nhóm: {', '.join(groups)}")


if __name__ == "__main__":
    main()
