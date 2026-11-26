#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SINH KICH BAN QUY MO (3 / 9 / 12 thiet bi) DE CHAM THU score.py
================================================================
Tao ra:
  sot/scenarios/devices_3.yaml, devices_9.yaml, devices_12.yaml
  compliance/configs/scale_before/*.cfg   (nhan ban tu configs/golden)
  compliance/configs/scale_after/*.cfg    (nhan ban tu configs/after)

Pod A = 6 thiet bi cua lab hien tai (edge1, spine1-2, leaf1-3).
Pod B = ban sao cua Pod A (edge2, spine3-4, leaf4-6), doi ten / IP / ASN.
Cau hinh mau la GIA LAP (khong lay tu thiet bi that); cac gia tri bi mat
duoc thay bang chuoi MAU_* de khong nhan ban mat khau len kho ma.

Chay (o thu muc goc repo):
  python3 scripts/gen_scenarios.py
Cham thu:
  python3 compliance/tools/score.py --sot sot/scenarios/devices_12.yaml \
      --compare compliance/configs/scale_before compliance/configs/scale_after \
      --out compliance/reports/scale
"""
import copy
import ipaddress
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SOT = REPO / "sot" / "devices.yaml"
OUT_SOT = REPO / "sot" / "scenarios"
CFG = REPO / "compliance" / "configs"

# Thiet bi Pod B -> thiet bi Pod A duoc nhan ban
MIRROR = {"edge2": "edge1", "spine3": "spine1", "spine4": "spine2",
          "leaf4": "leaf1", "leaf5": "leaf2", "leaf6": "leaf3"}

# Doi ten, IP, ASN tu Pod A sang Pod B (thay the dong thoi)
SUBST = {
    "edge1": "edge2", "spine1": "spine3", "spine2": "spine4",
    "leaf1": "leaf4", "leaf2": "leaf5", "leaf3": "leaf6",
    "10.0.1.": "10.0.3.", "10.0.2.": "10.0.4.",
    "10.0.11.": "10.0.34.", "10.0.12.": "10.0.35.",
    "10.0.22.": "10.0.45.", "10.0.23.": "10.0.46.",
    "10.255.0.1": "10.255.0.2", "10.255.0.11": "10.255.0.13",
    "10.255.0.12": "10.255.0.14", "10.255.0.21": "10.255.0.24",
    "10.255.0.22": "10.255.0.25", "10.255.0.23": "10.255.0.26",
    "172.20.20.10": "172.20.20.14", "172.20.20.11": "172.20.20.15",
    "172.20.20.12": "172.20.20.16", "172.20.20.21": "172.20.20.24",
    "172.20.20.22": "172.20.20.25", "172.20.20.23": "172.20.20.26",
    "65000": "65001", "65010": "65030", "65020": "65040",
    "65101": "65104", "65102": "65105", "65103": "65106",
}
_KEYS = sorted(SUBST, key=len, reverse=True)
# Khoa ket thuc bang "." la tien to subnet (theo sau la chu so) nen khong chan phia sau
_RX = re.compile(r"(?<![\w.])(" + "|".join(
    re.escape(k) + ("" if k.endswith(".") else r"(?!\w)") for k in _KEYS) + ")")

# Bo thiet bi cua tung kich ban
SCENARIOS = {
    3: ["edge1", "spine1", "leaf1"],
    9: ["edge1", "spine1", "spine2", "leaf1", "leaf2", "leaf3",
        "edge2", "spine3", "leaf4"],
    12: ["edge1", "spine1", "spine2", "leaf1", "leaf2", "leaf3",
         "edge2", "spine3", "spine4", "leaf4", "leaf5", "leaf6"],
}


def pod_b(text: str) -> str:
    """Doi ten/IP/ASN cua Pod A thanh Pod B trong mot chuoi."""
    return _RX.sub(lambda m: SUBST[m.group(1)], text)


def mask_secrets(text: str) -> str:
    """Thay mat khau/khoa mau bang chuoi MAU_* (van khop regex cua luat)."""
    text = re.sub(r"(neighbor \S+ password )\S+", r"\1MAU_BGP_KEY", text)
    text = re.sub(r"(auth sha )\S+", r"\1MAU_AUTH_KEY", text)
    text = re.sub(r"(priv aes )\S+", r"\1MAU_PRIV_KEY", text)
    return text


def all_devices(sot: dict) -> dict:
    devs = {d["name"]: d for d in sot["devices"]}
    for new, old in MIRROR.items():
        d = yaml.safe_load(pod_b(yaml.safe_dump(devs[old], allow_unicode=True)))
        d["name"] = new
        devs[new] = d
    return devs


def trim(dev: dict, names: list, devs: dict) -> dict:
    """Giu lai cong va lang gieng BGP noi toi thiet bi khac co trong kich ban."""
    others = [devs[n] for n in names if n != dev["name"]]
    other_ifs = [ipaddress.ip_interface(i["ipv4"]) for o in others for i in o.get("interfaces", [])]
    other_ips = {str(x.ip) for x in other_ifs}
    other_nets = {x.network for x in other_ifs}
    d = copy.deepcopy(dev)
    d["interfaces"] = [i for i in d.get("interfaces", [])
                       if ipaddress.ip_interface(i["ipv4"]).network in other_nets]
    d.setdefault("bgp", {})["neighbors"] = [
        nb for nb in d["bgp"].get("neighbors", []) if nb["address"] in other_ips]
    return d


def main():
    sot = yaml.safe_load(SOT.read_text(encoding="utf-8"))
    devs = all_devices(sot)

    OUT_SOT.mkdir(parents=True, exist_ok=True)
    for n, names in SCENARIOS.items():
        doc = {
            "meta": dict(sot.get("meta", {}), phien_ban_sot="2.0-kichban",
                         kich_ban=f"{n} thiet bi (gia lap quy mo, chi dung de cham diem)"),
            "devices": [trim(devs[x], names, devs) for x in names],
            "vlans": sot.get("vlans", []),
            "policy_inputs": sot.get("policy_inputs", {}),
        }
        out = OUT_SOT / f"devices_{n}.yaml"
        out.write_text(
            f"# KICH BAN QUY MO {n} THIET BI — sinh boi scripts/gen_scenarios.py, khong sua tay.\n"
            "# Chi dung cho score.py --sot; Ansible va dashboard van dung sot/devices.yaml.\n"
            + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
            encoding="utf-8")
        print(f"Da ghi {out.relative_to(REPO)} ({n} thiet bi)")

    for src, dst in (("golden", "scale_before"), ("after", "scale_after")):
        d = CFG / dst
        d.mkdir(parents=True, exist_ok=True)
        for name in SCENARIOS[12]:
            base = MIRROR.get(name, name)
            text = (CFG / src / f"{base}.cfg").read_text(encoding="utf-8")
            if name in MIRROR:
                text = pod_b(text)
            (d / f"{name}.cfg").write_text(mask_secrets(text), encoding="utf-8")
        print(f"Da ghi compliance/configs/{dst}/ ({len(SCENARIOS[12])} tep .cfg)")


if __name__ == "__main__":
    main()
