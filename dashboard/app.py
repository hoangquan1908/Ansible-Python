#!/usr/bin/env python3
"""
WEB DASHBOARD — Giao dien quan ly tuan thu an ninh mang
=======================================================
Phan viec cua Quan (Business Analyst).

Chay:  python3 dashboard/app.py
Truy cap: http://localhost:5000
"""
import datetime as dt
import json
import sqlite3
from pathlib import Path

from flask import Flask, render_template, jsonify, request

REPO = Path(__file__).resolve().parent.parent
COMPLIANCE = REPO / "compliance"
DB_PATH = REPO / "dashboard" / "compliance.db"

import sys
sys.path.insert(0, str(COMPLIANCE / "tools"))
from score import run_scoring

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
    device_scores = []
    if latest:
        device_scores = conn.execute(
            "SELECT * FROM device_scores WHERE scan_id=? ORDER BY device",
            (latest["id"],)
        ).fetchall()
    conn.close()
    sot = load_sot()
    return render_template("index.html",
                           latest=latest,
                           history=history,
                           device_scores=device_scores,
                           sot=sot)


@app.route("/api/scan", methods=["POST"])
def api_scan():
    config_dir = request.json.get("config_dir", "golden")
    configs_path = COMPLIANCE / "configs" / config_dir
    if not configs_path.exists():
        return jsonify({"error": f"Thu muc {configs_path} khong ton tai"}), 400
    sot_path = REPO / "sot" / "devices.yaml"
    policy_path = COMPLIANCE / "policy" / "cis_rules.yaml"
    report = run_scoring(str(sot_path), str(policy_path), str(configs_path))
    scan_id = save_scan(report, config_dir)
    return jsonify({"scan_id": scan_id, "overall_score": report["overall_score"],
                     "devices": len(report["devices"])})


@app.route("/api/compare", methods=["POST"])
def api_compare():
    before_dir = request.json.get("before", "golden")
    after_dir = request.json.get("after", "after")
    sot_path = REPO / "sot" / "devices.yaml"
    policy_path = COMPLIANCE / "policy" / "cis_rules.yaml"
    before = run_scoring(str(sot_path), str(policy_path), str(COMPLIANCE / "configs" / before_dir))
    after = run_scoring(str(sot_path), str(policy_path), str(COMPLIANCE / "configs" / after_dir))
    return jsonify({
        "before": {"score": before["overall_score"], "devices": before["devices"]},
        "after": {"score": after["overall_score"], "devices": after["devices"]},
        "improvement": round(after["overall_score"] - before["overall_score"], 1)
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
    return render_template("topology.html", sot=sot)


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

    return render_template("metrics.html",
                           benchmark=benchmark,
                           risk=risk,
                           drift=drift,
                           comparison=comparison)


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
