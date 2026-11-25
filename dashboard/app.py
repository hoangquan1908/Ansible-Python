#!/usr/bin/env python3
"""
WEB DASHBOARD — Giao dien quan ly tuan thu an ninh mang
=======================================================
Phan viec cua Quan.

Chay:  python3 dashboard/app.py
Truy cap: http://localhost:5000
"""
import datetime as dt
import ipaddress
import json
import math
import sqlite3
from pathlib import Path

from flask import Flask, render_template, jsonify, request

REPO = Path(__file__).resolve().parent.parent
COMPLIANCE = REPO / "compliance"
DB_PATH = REPO / "dashboard" / "compliance.db"

import sys
sys.path.insert(0, str(COMPLIANCE / "tools"))
from score import run_scoring, load_yaml, rule_applies

app = Flask(__name__)


# ----------------------------------------------------------------- DB
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_at TEXT NOT NULL,
            config_source TEXT NOT NULL,
            overall_score REAL NOT NULL,
            n_devices INTEGER NOT NULL,
            n_rules INTEGER NOT NULL,
            report_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS device_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            device TEXT NOT NULL,
            os TEXT NOT NULL,
            role TEXT NOT NULL,
            score REAL NOT NULL,
            n_rules INTEGER NOT NULL,
            n_violations INTEGER NOT NULL,
            FOREIGN KEY (scan_id) REFERENCES scan_history(id)
        );
    """)
    conn.commit()
    conn.close()


def save_scan(report: dict, config_source: str) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO scan_history (scanned_at, config_source, overall_score, n_devices, n_rules, report_json) VALUES (?,?,?,?,?,?)",
        (report["generated_at"], config_source, report["overall_score"],
         len(report["devices"]), report["n_rules"], json.dumps(report, ensure_ascii=False))
    )
    scan_id = cur.lastrowid
    for d in report["devices"]:
        conn.execute(
            "INSERT INTO device_scores (scan_id, device, os, role, score, n_rules, n_violations) VALUES (?,?,?,?,?,?,?)",
            (scan_id, d["device"], d["os"], d["role"], d["score"],
             d["n_rules"], d["n_violations"])
        )
    conn.commit()
    conn.close()
    return scan_id


# ----------------------------------------------------------------- SoT
def load_sot():
    import yaml
    sot_path = REPO / "sot" / "devices.yaml"
    with open(sot_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_config_dirs() -> list:
    base = COMPLIANCE / "configs"
    return sorted(p.name for p in base.iterdir() if p.is_dir() and any(p.glob("*.cfg")))


def load_policy_stats(os_names) -> dict:
    policy = load_yaml(COMPLIANCE / "policy" / "cis_rules.yaml")
    rules = policy.get("rules", [])
    return {
        "n_rules": len(rules),
        "n_groups": len({r["id"].rsplit(".", 1)[0] for r in rules}),
        "per_os": {o: sum(1 for r in rules if rule_applies(r, o)) for o in os_names},
    }


# -------------------------------------------------------------- Routes
@app.route("/")
def index():
    conn = get_db()
    latest = conn.execute(
        "SELECT * FROM scan_history ORDER BY id DESC LIMIT 1"
    ).fetchone()
    history = conn.execute(
        "SELECT id, scanned_at, config_source, overall_score, n_devices FROM scan_history ORDER BY id DESC LIMIT 20"
    ).fetchall()
    total_scans = conn.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
    device_scores = []
    if latest:
        device_scores = conn.execute(
            "SELECT * FROM device_scores WHERE scan_id=? ORDER BY device",
            (latest["id"],)
        ).fetchall()
    conn.close()
    sot = load_sot()
    policy_stats = load_policy_stats(sorted({d["os"] for d in sot["devices"]}))
    return render_template("index.html",
                           config_dirs=list_config_dirs(),
                           latest=latest,
                           history=history,
                           device_scores=device_scores,
                           total_scans=total_scans,
                           sot=sot,
                           policy_stats=policy_stats)


@app.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.get_json(silent=True) or {}
    config_dir = data.get("config_dir", "golden")
    allowed = list_config_dirs()
    if config_dir not in allowed:
        return jsonify({"error": f"Thu muc '{config_dir}' khong hop le. Chon mot trong: {', '.join(allowed)}"}), 400
    configs_path = COMPLIANCE / "configs" / config_dir
    sot_path = REPO / "sot" / "devices.yaml"
    policy_path = COMPLIANCE / "policy" / "cis_rules.yaml"
    report = run_scoring(str(sot_path), str(policy_path), str(configs_path))
    scan_id = save_scan(report, config_dir)
    return jsonify({"scan_id": scan_id, "overall_score": report["overall_score"],
                     "devices": len(report["devices"])})


@app.route("/api/compare", methods=["POST"])
def api_compare():
    data = request.get_json(silent=True) or {}
    before_dir = data.get("before", "golden")
    after_dir = data.get("after", "after")
    allowed = list_config_dirs()
    for name in (before_dir, after_dir):
        if name not in allowed:
            return jsonify({"error": f"Thu muc '{name}' khong hop le. Chon mot trong: {', '.join(allowed)}"}), 400
    sot_path = REPO / "sot" / "devices.yaml"
    policy_path = COMPLIANCE / "policy" / "cis_rules.yaml"
    before = run_scoring(str(sot_path), str(policy_path), str(COMPLIANCE / "configs" / before_dir))
    after = run_scoring(str(sot_path), str(policy_path), str(COMPLIANCE / "configs" / after_dir))
    return jsonify({
        "before": {"score": before["overall_score"], "devices": before["devices"]},
        "after": {"score": after["overall_score"], "devices": after["devices"]},
        "improvement": round(after["overall_score"] - before["overall_score"], 1),
        "before_dir": before_dir,
        "after_dir": after_dir,
    })


@app.route("/api/history")
def api_history():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, scanned_at, config_source, overall_score, n_devices FROM scan_history ORDER BY id"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/scan/<int:scan_id>")
def api_scan_detail(scan_id):
    conn = get_db()
    scan = conn.execute("SELECT * FROM scan_history WHERE id=?", (scan_id,)).fetchone()
    if not scan:
        return jsonify({"error": "Khong tim thay"}), 404
    devices = conn.execute(
        "SELECT * FROM device_scores WHERE scan_id=? ORDER BY device", (scan_id,)
    ).fetchall()
    conn.close()
    return jsonify({
        "scan": dict(scan),
        "devices": [dict(d) for d in devices],
        "report": json.loads(scan["report_json"])
    })


@app.route("/topology")
def topology():
    sot = load_sot()
    return render_template("topology.html", sot=sot, topo=build_topology(sot))


TIER_ORDER = ["edge", "spine", "leaf"]
TIER_COLOR = {"edge": "#f97316", "spine": "#4f8cff", "leaf": "#22c55e"}


def build_topology(sot: dict) -> dict:
    """Sinh so do tu SoT: tang theo truong 'role', lien ket theo cap cong cung subnet."""
    devices = sot.get("devices", [])
    role_of = {d["name"]: d.get("role") or "khac" for d in devices}
    roles = [r for r in TIER_ORDER if r in role_of.values()]
    roles += sorted(set(role_of.values()) - set(roles))
    row_of = {name: roles.index(r) for name, r in role_of.items()}

    # 1) Lien ket: 2 cong cung mot subnet IPv4 la mot duong noi
    by_net = {}
    for d in devices:
        for itf in d.get("interfaces", []):
            try:
                net = ipaddress.ip_interface(itf.get("ipv4", "")).network
            except ValueError:
                continue
            by_net.setdefault(str(net), []).append((d["name"], itf["name"]))
    links = []
    for net, eps in sorted(by_net.items()):
        if len(eps) != 2:
            continue
        (a, ia), (b, ib) = sorted(eps, key=lambda e: (row_of[e[0]], e[0]))   # a = tang tren
        links.append({"net": net, "a": a, "a_if": ia, "b": b, "b_if": ib})

    # 2) Vi tri: moi tang mot hang; tang duoi sap theo trung binh x cua thiet bi noi len (it cat cheo)
    node_w, gap, left, top, row_h = 148, 40, 70, 62, 165
    widest = max([sum(1 for r in role_of.values() if r == role) for role in roles] or [1])
    width = max(800, 2 * left + widest * (node_w + gap))
    pos, tiers = {}, []
    for row, role in enumerate(roles):
        members = [d for d in devices if role_of[d["name"]] == role]
        def order(d):
            xs = [pos[l["a"]][0] for l in links if l["b"] == d["name"] and l["a"] in pos]
            return (sum(xs) / len(xs) if xs else float("inf"), d["name"])
        members.sort(key=order if row else (lambda d: d["name"]))
        y = top + row * row_h
        step = (width - 2 * left) / max(len(members), 1)
        for k, d in enumerate(members):
            pos[d["name"]] = (round(left + step * (k + 0.5)), y)
        tiers.append({"role": role, "y": y, "color": TIER_COLOR.get(role, "#a78bfa"), "count": len(members)})

    # 3) Hinh hoc duong noi; thiet bi co >1 uplink: duong thu 2 tro di ve net dut (du phong)
    uplinks = {}
    for l in links:
        uplinks.setdefault(l["b"], []).append(l)
    for lst in uplinks.values():
        lst.sort(key=lambda l: pos[l["a"]][0])
        for k, l in enumerate(lst):
            l["backup"] = k > 0
    for l in links:
        (x1, y1), (x2, y2) = pos[l["a"]], pos[l["b"]]
        if y1 != y2:
            y1, y2 = y1 + 30, y2 - 30
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if ang > 90: ang -= 180
        if ang < -90: ang += 180
        l.update(x1=x1, y1=y1, x2=x2, y2=y2, mx=(x1 + x2) / 2, my=(y1 + y2) / 2, ang=round(ang, 1))

    nodes = [{"name": d["name"], "os": d.get("os", ""), "role": role_of[d["name"]],
              "asn": d.get("bgp", {}).get("asn", ""), "mgmt_ip": d.get("mgmt_ip", ""),
              "x": pos[d["name"]][0], "y": pos[d["name"]][1],
              "color": TIER_COLOR.get(role_of[d["name"]], "#a78bfa")} for d in devices]
    mgmt = ""
    if devices and devices[0].get("mgmt_ip"):
        mgmt = str(ipaddress.ip_network(devices[0]["mgmt_ip"] + "/24", strict=False))
    linked = {l["a"] for l in links} | {l["b"] for l in links}
    return {"width": width, "height": top + (len(roles) - 1) * row_h + 70, "tiers": tiers,
            "nodes": nodes, "links": links, "mgmt_net": mgmt,
            "unlinked": [d["name"] for d in devices if d["name"] not in linked]}


@app.route("/metrics")
def metrics():
    reports_dir = REPO / "compliance" / "reports"
    benchmark = {}
    bpath = reports_dir / "benchmark.json"
    if bpath.exists():
        benchmark = json.loads(bpath.read_text(encoding="utf-8"))

    risk = {}
    rpath = reports_dir / "risk_assessment.json"
    if rpath.exists():
        risk = json.loads(rpath.read_text(encoding="utf-8"))

    drift = {}
    dpath = reports_dir / "drift_report.json"
    if dpath.exists():
        drift = json.loads(dpath.read_text(encoding="utf-8"))

    comparison = {}
    cpath = reports_dir / "comparison.json"
    if cpath.exists():
        comparison = json.loads(cpath.read_text(encoding="utf-8"))

    sot = load_sot()
    policy_stats = load_policy_stats(sorted({d["os"] for d in sot["devices"]}))
    return render_template("metrics.html",
                           benchmark=benchmark,
                           risk=risk,
                           drift=drift,
                           comparison=comparison,
                           policy_stats=policy_stats,
                           n_devices=len(sot["devices"]))


@app.route("/api/metrics")
def api_metrics():
    reports_dir = REPO / "compliance" / "reports"
    data = {}
    for name in ["benchmark", "risk_assessment", "drift_report", "comparison"]:
        p = reports_dir / f"{name}.json"
        if p.exists():
            data[name] = json.loads(p.read_text(encoding="utf-8"))
    return jsonify(data)


@app.route("/devices")
def devices():
    sot = load_sot()
    conn = get_db()
    latest = conn.execute("SELECT id FROM scan_history ORDER BY id DESC LIMIT 1").fetchone()
    device_details = {}
    if latest:
        report_row = conn.execute("SELECT report_json FROM scan_history WHERE id=?", (latest["id"],)).fetchone()
        if report_row:
            report = json.loads(report_row["report_json"])
            for d in report["devices"]:
                device_details[d["device"]] = d
    conn.close()
    return render_template("devices.html", sot=sot, device_details=device_details)


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    init_db()
    print(f"Dashboard: http://localhost:5000")
    print(f"Database : {DB_PATH}")
    app.run(host="0.0.0.0", port=5000, debug=True)
