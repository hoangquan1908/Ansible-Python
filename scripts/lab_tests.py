#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHAY CAC CA KIEM THU TREN LAB (L-01 .. L-11) VA GHI SO LIEU THEO TUNG THIET BI
=============================================================================
Yeu cau: lab dang chay (./run.sh lab-up), dung o thu muc goc repo.
Chay:    python3 scripts/lab_tests.py
Ket qua: compliance/reports/lab_tests.json va lab_tests.md (bang de dua vao bao cao)

Anh chup cau hinh duoc ghi vao compliance/configs/lab_before va lab_after (co mat khau BGP
-> them 2 thu muc nay vao .git/info/exclude, KHONG commit).

Luu y: script SE THAY DOI cau hinh lab (deploy, harden, gay troi tren leaf3 roi khac phuc).
Khong chay tren he thong that.
"""
import datetime as dt
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "compliance/tools"))
from score import run_scoring  # noqa: E402

SOT = yaml.safe_load((REPO / "sot/devices.yaml").read_text(encoding="utf-8"))
DEVS = SOT["devices"]
POL = REPO / "compliance/policy/cis_rules.yaml"
CFG = REPO / "compliance/configs"
LAB = "clab-datn-lab-"
OUT = REPO / "compliance/reports"
RESULTS = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "tests": []}


def sh(cmd, timeout=900):
    t0 = time.time()
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
    return r, round(time.time() - t0, 1)


def recap(stdout):
    """Doc PLAY RECAP: {host: {ok, changed, failed, ...}}"""
    res = {}
    for m in re.finditer(r'^(\S+)\s*:\s*ok=(\d+)\s+changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)', stdout, re.M):
        res[m.group(1)] = {"ok": int(m.group(2)), "changed": int(m.group(3)),
                           "unreachable": int(m.group(4)), "failed": int(m.group(5))}
    return res


def playbook(name, limit=None):
    cmd = ["ansible-playbook", "-i", "inventory/hosts.yml", f"{name}.yml"]
    if limit:
        cmd += ["--limit", limit]
    r, t = sh(cmd)
    return {"seconds": t, "returncode": r.returncode, "recap": recap(r.stdout)}


SECRET = re.compile(r'\b(password|secret|key|community)(\s+\d)?\s+\S+', re.I)


def mask(obj):
    """Che mat khau/khoa trong du lieu ghi ra (tranh lo bi mat len repo)."""
    if isinstance(obj, str):
        return SECRET.sub(lambda m: f"{m.group(1)}{m.group(2) or ''} ****", obj)
    if isinstance(obj, list):
        return [mask(x) for x in obj]
    if isinstance(obj, dict):
        return {k: mask(v) for k, v in obj.items()}
    return obj


def add(tid, title, expected, actual, passed, data=None):
    actual, data = mask(actual), mask(data)
    RESULTS["tests"].append({"id": tid, "title": title, "expected": expected, "actual": actual,
                             "result": "Đạt" if passed else "Chưa đạt", "data": data or {}})
    print(f"[{tid}] {'DAT ' if passed else 'CHUA'} {title}: {actual}")


def bgp_established(dev):
    c = LAB + dev["name"]
    try:
        if dev["os"] == "frr":
            r, _ = sh(["docker", "exec", c, "vtysh", "-c", "show bgp summary json"], 60)
            peers = json.loads(r.stdout).get("ipv4Unicast", {}).get("peers", {})
            return sum(1 for p in peers.values() if p.get("state") == "Established")
        r, _ = sh(["docker", "exec", c, "sr_cli", "-d", "show network-instance default protocols bgp neighbor"], 60)
        n = len(re.findall(r'\|\s*established\s*\|', r.stdout, re.I))   # dong bang, khong dem dong Summary
        if n == 0:
            m = re.search(r'(\d+)\s+configured sessions are established', r.stdout)
            n = int(m.group(1)) if m else 0
        return n
    except Exception:
        return -1


def tcp_open(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=3):
            return True
    except OSError:
        return False


def snapshot(name):
    playbook("backup")
    dst = CFG / name
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(CFG / "live", dst)
    return run_scoring(REPO / "sot/devices.yaml", POL, dst)


def main():
    n = len(DEVS)
    # L-01 ket noi
    r, t = sh(["ansible", "all", "-m", "ping", "-i", "inventory/hosts.yml"], 120)
    ok = len(re.findall(r'SUCCESS', r.stdout))
    add("L-01", "Ansible kết nối tới thiết bị", f"{n}/{n} SUCCESS", f"{ok}/{n} SUCCESS ({t} s)", ok == n)

    # L-02 trien khai lan 1, theo tung thiet bi
    d1 = playbook("deploy")
    fails = [h for h, v in d1["recap"].items() if v["failed"] or v["unreachable"]]
    add("L-02", "Triển khai deploy.yml lần 1", "failed=0 trên mọi thiết bị",
        f"{d1['seconds']} s; lỗi: {fails or 'không'}", d1["returncode"] == 0 and not fails, d1)

    # L-03 BGP theo tung thiet bi
    time.sleep(20)
    bgp = {d["name"]: bgp_established(d) for d in DEVS}
    want = {d["name"]: len(d["bgp"]["neighbors"]) for d in DEVS}
    add("L-03", "Phiên eBGP Established theo thiết bị", f"{sum(want.values())} láng giềng",
        f"{sum(max(v, 0) for v in bgp.values())}/{sum(want.values())} láng giềng",
        all(bgp[k] >= want[k] for k in want), {"established": bgp, "expected": want})

    # L-04 luy dang
    d2 = playbook("deploy")
    ch = {h: v["changed"] for h, v in d2["recap"].items()}
    add("L-04", "Chạy deploy.yml lần 2 (lũy đẳng)", "changed=0 trên mọi thiết bị",
        f"changed theo thiết bị: {ch}", all(v == 0 for v in ch.values()), d2)

    # L-05 cham diem live truoc harden
    before = snapshot("lab_before")
    # L-06 harden
    h = playbook("harden")
    add("L-06", "Chuẩn hóa an ninh harden.yml", "failed=0", f"{h['seconds']} s, mã trả về {h['returncode']}",
        h["returncode"] == 0, h)
    after = snapshot("lab_after")
    b = {d["device"]: d for d in before["devices"]}
    a = {d["device"]: d for d in after["devices"]}
    per = {k: {"truoc": b[k]["score"], "sau": a[k]["score"], "vp_truoc": b[k]["n_violations"],
               "vp_sau": a[k]["n_violations"],
               "da_sua": sorted({r["id"] for r in b[k]["results"] if not r["passed"]}
                                - {r["id"] for r in a[k]["results"] if not r["passed"]})} for k in b}
    add("L-05", "Chấm điểm cấu hình thật trước/sau chuẩn hóa", "điểm sau ≥ điểm trước",
        f"{before['overall_score']}% → {after['overall_score']}%",
        after["overall_score"] >= before["overall_score"], per)

    # L-07 sao luu
    files = sorted(p.name for p in (CFG / "live").glob("*.cfg"))
    add("L-07", "Sao lưu cấu hình (backup.yml)", f"{n} tệp .cfg", f"{len(files)} tệp", len(files) == n,
        {"files": files})

    # L-08 troi cau hinh tren leaf3 (FRR): xoa 1 lang gieng BGP ngoai quy trinh
    l3 = next(d for d in DEVS if d["name"] == "leaf3")
    nb = l3["bgp"]["neighbors"][0]["address"]
    sh(["docker", "exec", LAB + "leaf3", "vtysh", "-c", "conf t", "-c", f"router bgp {l3['bgp']['asn']}",
        "-c", f"no neighbor {nb}"])
    t0 = time.time()
    sh([sys.executable, "scripts/drift_check.py", "--target", "leaf3", "--baseline", "lab_after",
        "--output", "drift_test.json"], 120)
    t_detect = round(time.time() - t0, 1)
    rep = json.loads((OUT / "drift_test.json").read_text(encoding="utf-8"))["devices"][0]
    missing = rep.get("removed_lines", [])
    add("L-08", "Phát hiện trôi cấu hình trên leaf3", f"báo trôi, thiếu các dòng neighbor {nb}",
        f"{len(missing)} dòng thiếu, {len(rep.get('added_lines', []))} dòng thừa, {t_detect} s",
        bool(rep.get("drifted")) and any(nb in x for x in missing), {"removed": missing})
    fx = playbook("deploy", limit="leaf3")
    sh([sys.executable, "scripts/drift_check.py", "--target", "leaf3", "--baseline", "lab_after",
        "--output", "drift_test.json"], 120)
    rep2 = json.loads((OUT / "drift_test.json").read_text(encoding="utf-8"))["devices"][0]
    add("L-09", "Khắc phục trôi bằng deploy.yml --limit leaf3", "hết trôi sau khắc phục",
        f"{fx['seconds']} s; drifted={rep2.get('drifted')}", rep2.get("drifted") is False)

    # L-10 cong Telnet
    tel = {d["name"]: tcp_open(d["mgmt_ip"], 23) for d in DEVS}
    add("L-10", "Cổng Telnet 23 đóng trên mọi thiết bị", "0 thiết bị mở 23",
        f"{sum(tel.values())} thiết bị mở 23", not any(tel.values()), tel)

    # L-11 thoi gian theo so thiet bi (--limit)
    order = [d["name"] for d in DEVS]
    scale = {}
    for k in (1, 2, 4, n):
        scale[k] = playbook("deploy", limit=",".join(order[:k]))["seconds"]
    add("L-11", "Thời gian deploy theo số thiết bị", "tăng chậm hơn tuyến tính",
        "; ".join(f"{k} TB: {v} s" for k, v in scale.items()), scale[n] < scale[1] * n, scale)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lab_tests.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["| Mã | Ca kiểm thử | Kỳ vọng | Kết quả thực tế | Đánh giá |", "|---|---|---|---|---|"]
    md += [f"| {t['id']} | {t['title']} | {t['expected']} | {t['actual']} | {t['result']} |"
           for t in sorted(RESULTS["tests"], key=lambda x: x["id"])]
    md += ["", "| Thiết bị | Điểm trước | Điểm sau | Vi phạm trước | Vi phạm sau | Luật đã sửa |",
           "|---|---|---|---|---|---|"]
    md += [f"| {k} | {v['truoc']} | {v['sau']} | {v['vp_truoc']} | {v['vp_sau']} | {', '.join(v['da_sua']) or '–'} |"
           for k, v in per.items()]
    (OUT / "lab_tests.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nDa ghi {OUT / 'lab_tests.json'} va lab_tests.md")


if __name__ == "__main__":
    main()
