#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KIEM THU THEO KICH BAN CAU HINH TREN LAB (6 thiet bi, nhieu cach cau hinh)
=========================================================================
Cung 6 thiet bi (sot/devices.yaml), moi kich ban trong lab/profiles/profiles.yml
dua mot tap vi pham (hoac bien phap lam bang tay) khac nhau vao thiet bi, nen
diem "truoc harden" khac nhau giua cac kich ban. Voi moi lan chay:
  1. dung lab moi (lab/scale/topo_6.clab.yml), sinh inventory, cho ping
  2. deploy.yml, cho BGP, dem phien eBGP
  3. (K6) harden.yml + cham diem "da harden" de lam moc
  4. dua thay doi cua kich ban vao (lab/profiles/inject.yml)
  5. backup.yml -> cham diem TRUOC harden
  6. harden.yml (do thoi gian) -> backup.yml -> cham diem SAU harden
  7. dem lai eBGP (harden khong lam mat dich vu), xoa lab
Moi log Ansible luu o compliance/reports/profile_logs/ (da che mat khau),
cau hinh thu tu thiet bi luu o compliance/configs/profile_live/ (khong commit).

Chay (o thu muc goc repo, may ao co Containerlab):
    python3 scripts/profile_lab.py                  # ca 6 kich ban (K2 lap 3 lan) ~40 phut
    python3 scripts/profile_lab.py --only K1 K2     # chi chay mot so kich ban
    python3 scripts/profile_lab.py --repeat 1       # moi kich ban chi chay 1 lan
Ket qua: compliance/reports/profile_lab.md va profile_lab.json
"""
import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "compliance/tools"))
sys.path.insert(0, str(REPO / "scripts"))
from score import run_scoring, read_config_fmt, mask_secrets  # noqa: E402
from scale_lab import (log, sh, write_topology, lab_up, lab_destroy, wait_ping,  # noqa: E402
                       gen_inventory, bgp_established, mask, MAIN_TOPO)

POLICY = REPO / "compliance/policy/cis_rules.yaml"
LIVE = REPO / "compliance/configs/live"
SNAP = REPO / "compliance/configs/profile_live"
LOGS = REPO / "compliance/reports/profile_logs"
REPORTS = REPO / "compliance/reports"
PROFILES = REPO / "lab/profiles/profiles.yml"
INJECT = REPO / "lab/profiles/inject.yml"
SOT = "sot/devices.yaml"


# ------------------------------------------------------------------ ansible co ghi log
def recap(stdout):
    res = {}
    for m in re.finditer(r'^(\S+)\s*:\s*ok=(\d+)\s+changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)'
                         r'(?:\s+skipped=(\d+))?(?:\s+rescued=(\d+))?(?:\s+ignored=(\d+))?', stdout, re.M):
        res[m.group(1)] = {"ok": int(m.group(2)), "changed": int(m.group(3)), "unreachable": int(m.group(4)),
                           "failed": int(m.group(5)), "ignored": int(m.group(8) or 0)}
    return res


def playbook(path, tag, extra=None):
    cmd = ["ansible-playbook", "-i", "inventory/hosts.yml", str(path)] + (extra or [])
    r, t = sh(cmd, 1200)
    LOGS.mkdir(parents=True, exist_ok=True)
    name = Path(path).stem
    (LOGS / f"{tag}_{name}.log").write_text(
        mask(f"$ {' '.join(cmd)}\n# {dt.datetime.now().isoformat(timespec='seconds')}  ({t} s, rc={r.returncode})\n\n"
             + r.stdout + ("\n--- stderr ---\n" + r.stderr if r.stderr.strip() else "")), encoding="utf-8")
    return {"seconds": t, "returncode": r.returncode, "recap": recap(r.stdout)}


def per_os(rep):
    """Diem co trong so theo tung HDH tu ket qua run_scoring."""
    out = {}
    for os_name in ("frr", "srlinux"):
        ds = [d for d in rep["devices"] if d["os"] == os_name]
        e, t = sum(d["earned"] for d in ds), sum(d["total"] for d in ds)
        out[os_name] = round(e / t * 100, 1) if t else None
    return out


def failed_rules(rep):
    """{luat: so thiet bi truot}"""
    cnt = {}
    for d in rep["devices"]:
        for r in d["results"]:
            if not r["passed"]:
                cnt[r["id"]] = cnt.get(r["id"], 0) + 1
    return dict(sorted(cnt.items(), key=lambda x: [int(p) for p in x[0][4:].split(".")]))


def snapshot_and_score(tag, sot_path):
    for f in LIVE.glob("*.cfg"):
        f.unlink()
    b = playbook(REPO / "backup.yml", tag)
    dst = SNAP / tag
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    for f in LIVE.glob("*.cfg"):
        shutil.copy(f, dst / f.name)
    rep = run_scoring(REPO / sot_path, POLICY, dst)
    # luu ban lam phang (da che mat khau) cua mot thiet bi SR Linux de doi chieu mau luat
    for d in rep["devices"]:
        if d["os"] == "srlinux":
            rf = read_config_fmt(dst, d["device"])
            if rf and rf[1] == "flat":
                (LOGS / f"{tag}_{d['device']}_flat.txt").write_text(mask_secrets(rf[0]) + "\n", encoding="utf-8")
            break
    s = {"overall": rep["overall_score"], "by_os": per_os(rep), "failed": failed_rules(rep),
         "per_device": {d["device"]: d["score"] for d in rep["devices"]},
         "formats": sorted({d["format"] for d in rep["devices"]}), "backup_rc": b["returncode"],
         "n_devices": len(rep["devices"])}
    return s


def count_bgp(devs):
    est = sum(max(bgp_established(d), 0) for d in devs)
    exp = sum(len(d.get("bgp", {}).get("neighbors", [])) for d in devs)
    return est, exp


# ------------------------------------------------------------------ mot lan chay
def run_profile(key, prof, run_no, args):
    tag = f"{key}_{run_no}"
    topo, sot, _ = write_topology(6, SOT)
    devs = sot["devices"]
    res = {"key": key, "run": run_no, "title": prof["title"], "desc": prof.get("desc", ""),
           "n_frr_cmds": len(prof.get("frr") or []), "n_srl_changes": len(prof.get("srl_delete") or [])
           + len(prof.get("srl_update") or []), "errors": []}
    log(f"== {tag}: {prof['title']} — dung lab")
    res["lab_up_s"], err = lab_up(topo, sot)
    if err:
        res["errors"].append(f"clab deploy loi: {err}")
        lab_destroy(topo)
        return res
    try:
        gen_inventory(SOT)
        res["ping_ok"], res["ready_s"] = wait_ping(len(devs))
        log(f"   ping {res['ping_ok']}/{len(devs)} sau {res['ready_s']} s")
        d = playbook(REPO / "deploy.yml", tag)
        res["deploy_s"] = d["seconds"]
        res["deploy_failed"] = sum(v["failed"] for v in d["recap"].values())
        time.sleep(args.bgp_wait)
        res["bgp_deploy"] = count_bgp(devs)
        log(f"   deploy {d['seconds']} s, failed={res['deploy_failed']}, eBGP {res['bgp_deploy'][0]}/{res['bgp_deploy'][1]}")

        if prof.get("harden_first"):
            h0 = playbook(REPO / "harden.yml", tag + "_h0")
            res["harden0_s"] = h0["seconds"]
            res["score_hardened"] = snapshot_and_score(tag + "_dahard", SOT)
            log(f"   harden lan dau -> {res['score_hardened']['overall']}%")

        if res["n_frr_cmds"] or res["n_srl_changes"]:
            vars_file = LOGS / f"{tag}_inject_vars.json"
            LOGS.mkdir(parents=True, exist_ok=True)
            vars_file.write_text(json.dumps({"frr_cmds": prof.get("frr") or [],
                                             "srl_delete": prof.get("srl_delete") or [],
                                             "srl_update": prof.get("srl_update") or []},
                                            ensure_ascii=False, indent=2), encoding="utf-8")
            i = playbook(INJECT, tag, ["-e", f"@{vars_file}"])
            res["inject_s"] = i["seconds"]
            res["inject_ignored"] = sum(v["ignored"] for v in i["recap"].values())
            res["inject_failed"] = sum(v["failed"] for v in i["recap"].values())
            log(f"   dua thay doi vao: {i['seconds']} s, task loi bo qua={res['inject_ignored']}")
            time.sleep(5)

        res["before"] = snapshot_and_score(tag + "_truoc", SOT)
        h = playbook(REPO / "harden.yml", tag)
        res["harden_s"] = h["seconds"]
        res["harden_failed"] = sum(v["failed"] for v in h["recap"].values())
        res["after"] = snapshot_and_score(tag + "_sau", SOT)
        res["bgp_end"] = count_bgp(devs)
        log(f"   {res['before']['overall']}% -> {res['after']['overall']}%  (harden {h['seconds']} s, "
            f"eBGP cuoi {res['bgp_end'][0]}/{res['bgp_end'][1]})")
    except Exception as e:  # ghi loi, van xoa lab
        res["errors"].append(str(e)[:500])
        log(f"   LOI: {e}")
    finally:
        lab_destroy(topo)
    return res


# ------------------------------------------------------------------ bao cao
def v(x, suf=""):
    return "–" if x is None else f"{x}{suf}"


def write_report(results):
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "profile_lab.json").write_text(mask(json.dumps(results, ensure_ascii=False, indent=2)), encoding="utf-8")
    L = [f"# Kiem thu theo kich ban cau hinh tren lab 6 thiet bi — {results['run_at']}", "",
         f"Bo luat: {results['policy']} ; SoT: {SOT}", "",
         "| Mã | Kịch bản | Lần | Thay đổi đưa vào (FRR / SRL) | Điểm trước | FRR trước | SRL trước | Điểm sau "
         "| FRR sau | SRL sau | Luật còn trượt sau harden | Harden | eBGP cuối | Ghi chú |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results["runs"]:
        b, a = r.get("before") or {}, r.get("after") or {}
        bo, ao = b.get("by_os", {}), a.get("by_os", {})
        rem = ", ".join(f"{k}×{n}" for k, n in a.get("failed", {}).items()) or "không"
        note = list(r["errors"])
        if r.get("score_hardened"):
            note.append(f"ngay sau harden lần đầu: {r['score_hardened']['overall']}%")
        if r.get("inject_ignored"):
            note.append(f"{r['inject_ignored']} task đưa thay đổi bị lỗi (bỏ qua)")
        if r.get("deploy_failed"):
            note.append(f"deploy failed={r['deploy_failed']}")
        bgp = r.get("bgp_end")
        L.append(f"| {r['key']} | {r['title']} | {r['run']} | {r['n_frr_cmds']} / {r['n_srl_changes']} "
                 f"| {v(b.get('overall'), '%')} | {v(bo.get('frr'), '%')} | {v(bo.get('srlinux'), '%')} "
                 f"| {v(a.get('overall'), '%')} | {v(ao.get('frr'), '%')} | {v(ao.get('srlinux'), '%')} "
                 f"| {rem} | {v(r.get('harden_s'), ' s')} | {f'{bgp[0]}/{bgp[1]}' if bgp else '–'} "
                 f"| {'; '.join(note) or 'OK'} |")
    L += ["", "## Luật trượt trước harden (luật × số thiết bị)", "",
          "| Mã | Lần | Trước harden | Sau harden |", "|---|---|---|---|"]
    for r in results["runs"]:
        f = lambda s: ", ".join(f"{k}×{n}" for k, n in (s or {}).get("failed", {}).items()) or "không"
        L.append(f"| {r['key']} | {r['run']} | {f(r.get('before'))} | {f(r.get('after'))} |")
    L += ["", "## Điểm từng thiết bị (trước → sau)", ""]
    names = list((results["runs"][0].get("before") or {}).get("per_device", {}))
    if names:
        L += ["| Mã | Lần | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
        for r in results["runs"]:
            b = (r.get("before") or {}).get("per_device", {})
            a = (r.get("after") or {}).get("per_device", {})
            L.append(f"| {r['key']} | {r['run']} | " + " | ".join(f"{v(b.get(n))} → {v(a.get(n))}" for n in names) + " |")
    L += ["", "## Mô tả kịch bản", ""]
    for k, p in results["profiles"].items():
        L.append(f"- **{k} – {p['title']}**: {p.get('desc', '')}")
    L += ["", "Log Ansible: compliance/reports/profile_logs/ ; cấu hình thu từ thiết bị: "
          "compliance/configs/profile_live/<mã>_<lần>_truoc|sau"]
    (REPORTS / "profile_lab.md").write_text(mask("\n".join(L)) + "\n", encoding="utf-8")
    log(f"Da ghi {REPORTS / 'profile_lab.md'} va profile_lab.json")


def main():
    profiles = yaml.safe_load(PROFILES.read_text(encoding="utf-8"))["profiles"]
    ap = argparse.ArgumentParser(description="Kiem thu theo kich ban cau hinh tren lab 6 thiet bi.")
    ap.add_argument("--only", nargs="+", choices=list(profiles), help="chi chay cac kich ban nay")
    ap.add_argument("--repeat", type=int, help="ghi de so lan lap cua moi kich ban")
    ap.add_argument("--no-restore", action="store_true", help="khong dung lai lab 6 thiet bi khi xong")
    ap.add_argument("--bgp-wait", type=int, default=45, help="giay cho BGP len sau deploy")
    args = ap.parse_args()
    keys = args.only or list(profiles)

    if subprocess.run(["sudo", "-v"]).returncode != 0:
        sys.exit("Can quyen sudo de chay clab")
    stop = threading.Event()

    def keep_sudo():
        while not stop.wait(240):
            subprocess.run(["sudo", "-n", "-v"], capture_output=True)
    threading.Thread(target=keep_sudo, daemon=True).start()

    inv_backup = (REPO / "inventory/hosts.yml").read_text(encoding="utf-8")
    results = {"run_at": dt.datetime.now().isoformat(timespec="seconds"),
               "policy": str(POLICY.relative_to(REPO)), "profiles": {k: profiles[k] for k in keys}, "runs": []}
    log("Xoa lab 6 thiet bi dang chay (neu co)")
    lab_destroy(MAIN_TOPO)
    try:
        for k in keys:
            n = args.repeat or int(profiles[k].get("repeat", 1))
            for run_no in range(1, n + 1):
                results["runs"].append(run_profile(k, profiles[k], run_no, args))
                write_report(results)        # ghi sau moi lan chay de khong mat so lieu
    finally:
        (REPO / "inventory/hosts.yml").write_text(inv_backup, encoding="utf-8")
        log("Da khoi phuc inventory/hosts.yml")
        if not args.no_restore:
            log("Dung lai lab 6 thiet bi bang ./run.sh lab-up")
            r, _ = sh(["bash", "run.sh", "lab-up"], 1200)
            log("   xong" if r.returncode == 0 else f"   LOI lab-up: {r.stderr[-300:]}")
        stop.set()


if __name__ == "__main__":
    main()
