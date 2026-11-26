#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DO HE THONG TREN LAB THAT THEO NHIEU QUY MO (3 / 6 / 9 / 12 thiet bi)
=====================================================================
Voi moi file SoT, script:
  1. sinh topology Containerlab tu SoT (lab/scale/topo_<n>.clab.yml) va dung lab
  2. sinh inventory tu chinh SoT do
  3. deploy lan 1 (do thoi gian, failed/changed tung thiet bi)
  4. dem phien eBGP Established tung thiet bi
  5. deploy lan 2 (kiem tra luy dang)
  6. backup -> cham diem cau hinh that TRUOC harden
  7. harden (do thoi gian) -> backup -> cham diem SAU harden
  8. ghi RAM cac container, xoa lab
Cuoi cung khoi phuc inventory 6 thiet bi va dung lai lab goc (tru khi --no-restore).

Chay (o thu muc goc repo, may ao co Containerlab):
    python3 scripts/scale_lab.py                 # chay ca 4 quy mo
    python3 scripts/scale_lab.py --only 3 6      # chi chay 3 va 6 thiet bi
    python3 scripts/scale_lab.py --topo-only     # chi sinh file topology de xem truoc
Ket qua: compliance/reports/scale_lab.md va scale_lab.json

CANH BAO: script XOA lab dang chay va dung lai nhieu lan (moi quy mo ~10-15 phut).
Can quyen sudo cho clab va khoa ~/.ssh/id_ed25519 (giong ./run.sh lab-up).
"""
import argparse
import datetime as dt
import ipaddress
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
from score import run_scoring  # noqa: E402

POLICY = REPO / "compliance/policy/cis_rules.yaml"
LIVE = REPO / "compliance/configs/live"
SNAP = REPO / "compliance/configs/scale_live"      # anh chup cau hinh that (co the chua mat khau -> .gitignore)
TOPO_DIR = REPO / "lab/scale"
REPORTS = REPO / "compliance/reports"
MAIN_SOT = REPO / "sot/devices.yaml"
MAIN_TOPO = REPO / "lab/topo.clab.yml"
LAB_NAME = "datn-lab"                                # giu ten cu de ten container khong doi
PREFIX = f"clab-{LAB_NAME}-"
SCENARIOS = {3: "sot/scenarios/devices_3.yaml", 6: "sot/devices.yaml",
             9: "sot/scenarios/devices_9.yaml", 12: "sot/scenarios/devices_12.yaml"}
SRL_IMAGE = "ghcr.io/nokia/srlinux:latest"
FRR_IMAGE = "quay.io/frrouting/frr:master"
FRR_EXEC = ["apk add --no-cache python3 openssh-server", "ssh-keygen -A",
            'echo "PermitRootLogin yes" >> /etc/ssh/sshd_config', "/usr/sbin/sshd",
            "sed -i 's/^bgpd=no/bgpd=yes/' /etc/frr/daemons"]
SECRET = re.compile(r'\b(password|secret|key|community)(\s+\d)?\s+\S+', re.I)


# ------------------------------------------------------------------ tien ich
def log(msg):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def sh(cmd, timeout=900, check=False):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=timeout,
                           shell=isinstance(cmd, str))
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "TIMEOUT"), round(time.time() - t0, 1)
    if check and r.returncode != 0:
        raise RuntimeError(f"Lenh loi: {cmd}\n{r.stderr[-800:]}")
    return r, round(time.time() - t0, 1)


def recap(stdout):
    res = {}
    for m in re.finditer(r'^(\S+)\s*:\s*ok=(\d+)\s+changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)', stdout, re.M):
        res[m.group(1)] = {"ok": int(m.group(2)), "changed": int(m.group(3)),
                           "unreachable": int(m.group(4)), "failed": int(m.group(5))}
    return res


def playbook(name):
    r, t = sh(["ansible-playbook", "-i", "inventory/hosts.yml", f"{name}.yml"])
    return {"seconds": t, "returncode": r.returncode, "recap": recap(r.stdout)}


def clab_name(ifname):
    """ethernet-1/3 -> e1-3 ; eth1 -> eth1"""
    m = re.fullmatch(r'ethernet-(\d+)/(\d+)', ifname)
    return f"e{m.group(1)}-{m.group(2)}" if m else ifname


# ------------------------------------------------------------------ topology tu SoT
def build_topology(sot):
    nodes, nets = {}, {}
    for d in sot["devices"]:
        if d["os"] == "srlinux":
            nodes[d["name"]] = {"kind": "nokia_srlinux", "image": SRL_IMAGE, "mgmt-ipv4": d["mgmt_ip"]}
        else:
            nodes[d["name"]] = {"kind": "linux", "image": FRR_IMAGE, "mgmt-ipv4": d["mgmt_ip"], "exec": FRR_EXEC}
        for i in d.get("interfaces", []):
            net = ipaddress.ip_interface(i["ipv4"]).network
            nets.setdefault(net, []).append(f"{d['name']}:{clab_name(i['name'])}")
    links, lonely = [], []
    for net, ends in sorted(nets.items(), key=lambda x: int(x[0].network_address)):
        if len(ends) == 2:
            links.append({"endpoints": ends})
        else:
            lonely.append(f"{net}: {ends}")
    topo = {"name": LAB_NAME, "topology": {"nodes": nodes, "links": links},
            "mgmt": {"network": "datn-mgmt", "ipv4-subnet": "172.20.20.0/24"}}
    return topo, lonely


def write_topology(n, sot_path):
    sot = yaml.safe_load((REPO / sot_path).read_text(encoding="utf-8"))
    topo, lonely = build_topology(sot)
    TOPO_DIR.mkdir(parents=True, exist_ok=True)
    out = TOPO_DIR / f"topo_{n}.clab.yml"
    out.write_text(f"# TU SINH tu {sot_path} boi scripts/scale_lab.py — khong sua tay\n"
                   + yaml.safe_dump(topo, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out, sot, lonely


# ------------------------------------------------------------------ lab
def lab_destroy(topo):
    sh(["sudo", "clab", "destroy", "-t", str(topo), "--cleanup"], 600)


def lab_up(topo, sot):
    r, t = sh(["sudo", "clab", "deploy", "-t", str(topo), "--reconfigure"], 1200)
    if r.returncode != 0:
        return t, r.stderr[-600:] or r.stdout[-600:]
    time.sleep(5)
    pub = Path.home() / ".ssh/id_ed25519.pub"
    for d in sot["devices"]:
        if d["os"] != "frr":
            continue
        c = PREFIX + d["name"]
        sh(["ssh-keygen", "-R", d["mgmt_ip"]])
        sh(["docker", "exec", c, "sh", "-c",
            'echo "PermitRootLogin yes" >> /etc/ssh/sshd_config && killall sshd 2>/dev/null; /usr/sbin/sshd'])
        sh(["docker", "exec", c, "sh", "-c", "mkdir -p /root/.ssh && chmod 700 /root/.ssh"])
        sh(["docker", "cp", str(pub), f"{c}:/root/.ssh/authorized_keys"])
        sh(["docker", "exec", c, "sh", "-c", "chown root:root /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys"])
        sh(["docker", "exec", c, "sh", "-c", "/usr/lib/frr/bgpd -d -F traditional -A 127.0.0.1 2>/dev/null"])
    return t, None


def wait_ping(n, limit=420):
    t0 = time.time(); ok = 0
    while time.time() - t0 < limit:
        r, _ = sh(["ansible", "all", "-m", "ping", "-i", "inventory/hosts.yml"], 180)
        ok = len(re.findall(r'SUCCESS', r.stdout))
        if ok >= n:
            break
        time.sleep(15)
    return ok, round(time.time() - t0, 1)


def mem_usage():
    r, _ = sh(["docker", "stats", "--no-stream", "--format", "{{.Name}};{{.MemUsage}}"], 120)
    total, per = 0.0, {}
    unit = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "kB": 1 / 1024, "MB": 1, "GB": 1024}
    for line in r.stdout.splitlines():
        name, _, use = line.partition(";")
        if not name.startswith(PREFIX):
            continue
        m = re.match(r'([\d.]+)\s*([A-Za-z]+)', use.strip())
        if m:
            mib = float(m.group(1)) * unit.get(m.group(2), 1)
            per[name[len(PREFIX):]] = round(mib)
            total += mib
    return round(total), per


def mem_available_mib():
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


def bgp_established(d):
    c = PREFIX + d["name"]
    if d["os"] == "frr":
        r, _ = sh(["docker", "exec", c, "vtysh", "-c", "show bgp summary json"], 60)
        try:
            peers = json.loads(r.stdout).get("ipv4Unicast", {}).get("peers", {})
            return sum(1 for p in peers.values() if p.get("state") == "Established")
        except (ValueError, AttributeError):
            return -1
    r, _ = sh(["docker", "exec", c, "sr_cli", "-d", "show network-instance default protocols bgp neighbor"], 60)
    n = len(re.findall(r'\|\s*established\s*\|', r.stdout, re.I))
    if n == 0:
        m = re.search(r'(\d+)\s+configured sessions are established', r.stdout)
        n = int(m.group(1)) if m else 0
    return n


def snapshot_and_score(tag, sot_path):
    """backup.yml -> chep compliance/configs/live sang scale_live/<tag> -> cham diem"""
    for f in LIVE.glob("*.cfg"):
        f.unlink()
    b = playbook("backup")
    dst = SNAP / tag
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    for f in LIVE.glob("*.cfg"):
        shutil.copy(f, dst / f.name)
    rep = run_scoring(REPO / sot_path, POLICY, dst)
    return b["seconds"], rep


def gen_inventory(sot_path):
    sh([sys.executable, "scripts/sot_to_inventory.py", "--sot", str(sot_path)], check=True)


# ------------------------------------------------------------------ mot kich ban
def run_scenario(n, sot_path, args):
    topo, sot, lonely = write_topology(n, sot_path)
    devs = sot["devices"]
    n_frr = sum(d["os"] == "frr" for d in devs)
    res = {"n": n, "sot": sot_path, "topo": str(topo.relative_to(REPO)), "frr": n_frr, "srl": len(devs) - n_frr,
           "per_device": {d["name"]: {"os": d["os"]} for d in devs}, "errors": []}
    if lonely:
        res["errors"].append(f"Mang /30 thieu dau: {lonely}")
    need = res["srl"] * args.mem_srl + n_frr * args.mem_frr
    avail = mem_available_mib()
    res["mem_available_mib"] = avail
    if avail is not None and avail < need and not args.force:
        res["errors"].append(f"Bo qua: RAM trong {avail} MiB < uoc tinh can {need} MiB (dung --force de van chay)")
        log(res["errors"][-1])
        return res

    log(f"== {n} thiet bi: dung lab ({res['srl']} SR Linux, {n_frr} FRR)")
    res["lab_up_s"], err = lab_up(topo, sot)
    if err:
        res["errors"].append(f"clab deploy loi: {err}")
        lab_destroy(topo)
        return res
    try:
        gen_inventory(sot_path)
        res["ping_ok"], res["ready_s"] = wait_ping(len(devs))
        log(f"   ping {res['ping_ok']}/{len(devs)} sau {res['ready_s']} s")

        d1 = playbook("deploy"); res["deploy1"] = d1
        log(f"   deploy lan 1: {d1['seconds']} s, rc={d1['returncode']}")
        time.sleep(args.bgp_wait)
        for d in devs:
            pd = res["per_device"][d["name"]]
            pd["bgp_expected"] = len(d.get("bgp", {}).get("neighbors", []))
            pd["bgp_established"] = bgp_established(d)
            rc = d1["recap"].get(d["name"], {})
            pd["deploy1_changed"], pd["deploy1_failed"] = rc.get("changed"), rc.get("failed")

        d2 = playbook("deploy"); res["deploy2"] = d2
        for name, v in d2["recap"].items():
            if name in res["per_device"]:
                res["per_device"][name]["deploy2_changed"] = v["changed"]
        log(f"   deploy lan 2: {d2['seconds']} s")

        res["backup_s"], before = snapshot_and_score(f"{n}_truoc", sot_path)
        h = playbook("harden"); res["harden"] = h
        log(f"   harden: {h['seconds']} s, rc={h['returncode']}")
        _, after = snapshot_and_score(f"{n}_sau", sot_path)
        res["score_before"], res["score_after"] = before["overall_score"], after["overall_score"]
        for d in before["devices"]:
            res["per_device"][d["device"]]["score_before"] = d["score"]
        for d in after["devices"]:
            res["per_device"][d["device"]]["score_after"] = d["score"]
        res["mem_total_mib"], per = mem_usage()
        for k, v in per.items():
            if k in res["per_device"]:
                res["per_device"][k]["mem_mib"] = v
    except Exception as e:  # ghi loi, van xoa lab
        res["errors"].append(str(e)[:500])
        log(f"   LOI: {e}")
    finally:
        log("   xoa lab")
        lab_destroy(topo)
    return res


# ------------------------------------------------------------------ bao cao
def mask(s):
    return SECRET.sub(lambda m: f"{m.group(1)}{m.group(2) or ''} ****", s)


def write_report(results):
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "scale_lab.json").write_text(mask(json.dumps(results, ensure_ascii=False, indent=2)), encoding="utf-8")

    def v(x, suf=""):
        return "–" if x is None else f"{x}{suf}"
    L = [f"# Do he thong theo quy mo tren lab — {results['run_at']}", "",
         "| Số TB | FRR / SRL | Dựng lab | Sẵn sàng | Ping | Deploy lần 1 | failed | eBGP Established / kỳ vọng "
         "| changed lần 2 | Harden | Điểm live trước → sau | RAM container | Ghi chú |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results["scenarios"]:
        pd = r["per_device"].values()
        est = sum(max(p.get("bgp_established") or 0, 0) for p in pd)
        exp = sum(p.get("bgp_expected") or 0 for p in pd)
        fail = sum(p.get("deploy1_failed") or 0 for p in pd) if "deploy1" in r else None
        ch2 = sum(p.get("deploy2_changed") or 0 for p in pd) if "deploy2" in r else None
        L.append(f"| {r['n']} | {r['frr']} / {r['srl']} | {v(r.get('lab_up_s'), ' s')} | {v(r.get('ready_s'), ' s')} "
                 f"| {v(r.get('ping_ok'))}/{r['n']} | {v(r.get('deploy1', {}).get('seconds'), ' s')} | {v(fail)} "
                 f"| {est}/{exp} | {v(ch2)} | {v(r.get('harden', {}).get('seconds'), ' s')} "
                 f"| {v(r.get('score_before'), '%')} → {v(r.get('score_after'), '%')} | {v(r.get('mem_total_mib'), ' MiB')} "
                 f"| {'; '.join(r['errors']) or 'OK'} |")
    for r in results["scenarios"]:
        L += ["", f"## {r['n']} thiết bị — chi tiết", "",
              "| Thiết bị | HĐH | changed lần 1 | failed | eBGP | changed lần 2 | Điểm trước | Điểm sau | RAM |",
              "|---|---|---|---|---|---|---|---|---|"]
        for name, p in r["per_device"].items():
            L.append(f"| {name} | {p['os']} | {v(p.get('deploy1_changed'))} | {v(p.get('deploy1_failed'))} "
                     f"| {v(p.get('bgp_established'))}/{v(p.get('bgp_expected'))} | {v(p.get('deploy2_changed'))} "
                     f"| {v(p.get('score_before'), '%')} | {v(p.get('score_after'), '%')} | {v(p.get('mem_mib'), ' MiB')} |")
    (REPORTS / "scale_lab.md").write_text(mask("\n".join(L)) + "\n", encoding="utf-8")
    log(f"Da ghi {REPORTS / 'scale_lab.md'} va scale_lab.json")


def main():
    ap = argparse.ArgumentParser(description="Do he thong tren lab that theo nhieu quy mo.")
    ap.add_argument("--only", type=int, nargs="+", choices=sorted(SCENARIOS), help="chi chay cac quy mo nay")
    ap.add_argument("--topo-only", action="store_true", help="chi sinh file topology, khong dung lab")
    ap.add_argument("--no-restore", action="store_true", help="khong dung lai lab 6 thiet bi khi xong")
    ap.add_argument("--force", action="store_true", help="van chay du uoc tinh RAM khong du")
    ap.add_argument("--mem-srl", type=int, default=1500, help="RAM uoc tinh moi SR Linux (MiB)")
    ap.add_argument("--mem-frr", type=int, default=150, help="RAM uoc tinh moi FRR (MiB)")
    ap.add_argument("--bgp-wait", type=int, default=45, help="giay cho BGP len sau deploy")
    args = ap.parse_args()
    sizes = args.only or sorted(SCENARIOS)

    if args.topo_only:
        for n in sizes:
            out, _, lonely = write_topology(n, SCENARIOS[n])
            log(f"{out.relative_to(REPO)}" + (f"  CANH BAO thieu dau: {lonely}" if lonely else ""))
        return

    # xin quyen sudo mot lan va giu song trong suot qua trinh do (~1 gio)
    if subprocess.run(["sudo", "-v"]).returncode != 0:
        sys.exit("Can quyen sudo de chay clab")
    stop = threading.Event()

    def keep_sudo():
        while not stop.wait(240):
            subprocess.run(["sudo", "-n", "-v"], capture_output=True)
    threading.Thread(target=keep_sudo, daemon=True).start()

    inv_backup = (REPO / "inventory/hosts.yml").read_text(encoding="utf-8")
    results = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "scenarios": []}
    log("Xoa lab 6 thiet bi dang chay (neu co)")
    lab_destroy(MAIN_TOPO)
    try:
        for n in sizes:
            results["scenarios"].append(run_scenario(n, SCENARIOS[n], args))
            write_report(results)           # ghi sau moi quy mo de khong mat so lieu neu dung giua chung
    finally:
        (REPO / "inventory/hosts.yml").write_text(inv_backup, encoding="utf-8")
        log("Da khoi phuc inventory/hosts.yml (6 thiet bi)")
        if not args.no_restore:
            log("Dung lai lab 6 thiet bi bang ./run.sh lab-up")
            r, _ = sh(["bash", "run.sh", "lab-up"], 1200)
            log("   xong" if r.returncode == 0 else f"   LOI lab-up: {r.stderr[-300:]}")
        stop.set()


if __name__ == "__main__":
    main()
