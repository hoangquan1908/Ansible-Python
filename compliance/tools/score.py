#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CÔNG CỤ CHẤM ĐIỂM TUÂN THỦ (Compliance Scoring)
================================================
Phần việc của Quân (Business Analyst / Compliance-as-Code).

Luồng xử lý:
  1. Đọc Nguồn dữ liệu tin cậy (SoT)  -> biết có những thiết bị nào.
  2. Đọc bộ chính sách CIS (policy)    -> các phép kiểm chứng.
  3. Với mỗi thiết bị, đọc file cấu hình tương ứng.
  4. Đánh giá từng luật áp dụng: đạt / vi phạm.
  5. Tính điểm tuân thủ có trọng số theo mức nghiêm trọng.
  6. Xuất: bảng ra màn hình + reports/compliance.json + reports/compliance.html

Chạy:
  python tools/score.py                         # dùng configs/golden
  python tools/score.py --configs configs/live  # dùng cấu hình thật (Chung sinh)

Không phụ thuộc code của ai khác: chỉ cần file config dạng text.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path

import yaml

MODULE = Path(__file__).resolve().parent.parent   # thư mục compliance/
REPO = MODULE.parent                               # gốc repo (chứa sot/ dùng chung)
ROOT = MODULE                                      # giữ tương thích các mặc định dưới


# --------------------------------------------------------------------- I/O
def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def strip_comments(text: str) -> str:
    """Bỏ các dòng chú thích (bắt đầu bằng ! hoặc #) để không chấm nhầm vào
    lời giải thích trong file. Chỉ giữ lại cấu hình thực."""
    lines = []
    for ln in text.splitlines():
        if re.match(r"^\s*[!#]", ln):
            continue
        lines.append(ln)
    return "\n".join(lines)


def read_config(configs_dir: Path, name: str) -> str | None:
    """Đọc file cấu hình <name>.cfg trong thư mục configs_dir. Chưa có -> None."""
    p = configs_dir / f"{name}.cfg"
    if not p.exists():
        return None
    return strip_comments(p.read_text(encoding="utf-8"))


# ----------------------------------------------------------------- đánh giá
def rule_applies(rule: dict, os_name: str) -> bool:
    scope = rule.get("applies_to", "all")
    return scope == "all" or scope == os_name


def evaluate_rule(rule: dict, config_text: str) -> bool:
    """True = ĐẠT, False = VI PHẠM."""
    chk = rule["check"]
    pattern = chk["pattern"]
    found = re.search(pattern, config_text) is not None
    if chk["type"] == "must_contain":
        return found
    if chk["type"] == "must_not_contain":
        return not found
    raise ValueError(f"Kiểu kiểm tra không hỗ trợ: {chk['type']}")


def score_device(device: dict, policy: dict, config_text: str) -> dict:
    weights = policy["weights"]
    results, earned, total = [], 0, 0
    for rule in policy["rules"]:
        if not rule_applies(rule, device["os"]):
            continue
        w = weights[rule["severity"]]
        total += w
        passed = evaluate_rule(rule, config_text)
        if passed:
            earned += w
        results.append({
            "id": rule["id"],
            "title": rule["title"],
            "severity": rule["severity"],
            "passed": passed,
            "remediation": rule["remediation"],
            "clo": rule.get("clo", []),
        })
    pct = round(earned / total * 100, 1) if total else 0.0
    violations = [r for r in results if not r["passed"]]
    return {
        "device": device["name"],
        "os": device["os"],
        "role": device.get("role", ""),
        "score": pct,
        "earned": earned,
        "total": total,
        "n_rules": len(results),
        "n_violations": len(violations),
        "results": results,
    }


# ------------------------------------------------------------------- output
def print_table(report: dict) -> None:
    print("\n" + "=" * 64)
    print(f"BÁO CÁO TUÂN THỦ  —  {report['generated_at']}")
    print("=" * 64)
    for d in report["devices"]:
        print(f"\n▌ {d['device']} ({d['os']}, {d['role']})   "
              f"Điểm: {d['score']}%  [{d['n_rules']-d['n_violations']}/{d['n_rules']} luật đạt]")
        for r in d["results"]:
            mark = "[OK] " if r["passed"] else "[FAIL]"
            flag = "" if r["passed"] else f"   → {r['remediation']}"
            print(f"   {mark} [{r['severity']:<6}] {r['id']}  {r['title']}{flag}")
    print("\n" + "-" * 64)
    print(f"ĐIỂM TUÂN THỦ TOÀN HỆ THỐNG: {report['overall_score']}%")
    print("-" * 64 + "\n")


def render_html(report: dict) -> str:
    def color(p):
        return "#16a34a" if p >= 90 else "#d97706" if p >= 70 else "#dc2626"

    rows_html = ""
    for d in report["devices"]:
        rules_html = ""
        for r in d["results"]:
            badge = ("<span class='ok'>ĐẠT</span>" if r["passed"]
                     else "<span class='bad'>VI PHẠM</span>")
            rem = "" if r["passed"] else f"<div class='rem'>Khắc phục: {r['remediation']}</div>"
            rules_html += (
                f"<tr class='{'r-ok' if r['passed'] else 'r-bad'}'>"
                f"<td>{r['id']}</td><td>{r['title']}{rem}</td>"
                f"<td>{r['severity']}</td><td>{', '.join(r['clo'])}</td>"
                f"<td>{badge}</td></tr>")
        rows_html += f"""
        <div class="card">
          <div class="card-h">
            <div><b>{d['device']}</b> <span class="muted">{d['os']} · {d['role']}</span></div>
            <div class="score" style="color:{color(d['score'])}">{d['score']}%</div>
          </div>
          <div class="muted small">{d['n_rules']-d['n_violations']}/{d['n_rules']} luật đạt · {d['n_violations']} vi phạm</div>
          <table>
            <thead><tr><th>Mã</th><th>Yêu cầu</th><th>Mức</th><th>CLO</th><th>Trạng thái</th></tr></thead>
            <tbody>{rules_html}</tbody>
          </table>
        </div>"""

    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Báo cáo tuân thủ an ninh mạng</title>
<style>
  :root{{--bg:#f8fafc;--fg:#0f172a;--muted:#64748b;--line:#e2e8f0;--card:#fff;}}
  @media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#0f172a;--fg:#e2e8f0;--muted:#94a3b8;--line:#1e293b;--card:#1e293b;}}}}
  body{{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:0;background:var(--bg);color:var(--fg);}}
  .wrap{{max-width:960px;margin:0 auto;padding:24px 16px;}}
  h1{{font-size:22px;margin:0 0 4px;}}
  .overall{{font-size:40px;font-weight:800;color:{color(report['overall_score'])};}}
  .muted{{color:var(--muted);}} .small{{font-size:13px;}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:16px 0;}}
  .card-h{{display:flex;justify-content:space-between;align-items:center;}}
  .score{{font-size:28px;font-weight:800;}}
  table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:14px;}}
  th,td{{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top;}}
  th{{color:var(--muted);font-weight:600;}}
  .ok{{color:#16a34a;font-weight:700;}} .bad{{color:#dc2626;font-weight:700;}}
  .r-bad{{background:rgba(220,38,38,.06);}}
  .rem{{color:var(--muted);font-size:12.5px;margin-top:2px;}}
</style></head><body><div class="wrap">
  <h1>Báo cáo kiểm soát tuân thủ an ninh mạng</h1>
  <div class="muted small">Sinh lúc {report['generated_at']} · Bộ luật: {report['n_rules']} · Thiết bị: {len(report['devices'])}</div>
  <div style="margin:14px 0;">Điểm tuân thủ toàn hệ thống: <span class="overall">{report['overall_score']}%</span></div>
  {rows_html}
  <p class="muted small">Sinh tự động bởi tools/score.py — Đồ án tự động hóa cấu hình & an ninh mạng.</p>
</div></body></html>"""


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Chấm điểm tuân thủ cấu hình mạng theo CIS.")
    ap.add_argument("--sot", default=str(REPO / "sot/devices.yaml"),
                    help="Nguồn dữ liệu tin cậy dùng chung ở gốc repo")
    ap.add_argument("--policy", default=str(ROOT / "policy/cis_rules.yaml"))
    ap.add_argument("--configs", default=str(ROOT / "configs/golden"),
                    help="Thư mục chứa <tên-thiết-bị>.cfg")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    args = ap.parse_args()

    sot = load_yaml(Path(args.sot))
    policy = load_yaml(Path(args.policy))
    configs_dir = Path(args.configs)
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    devices_out, tot_earned, tot_total = [], 0, 0
    for device in sot["devices"]:
        cfg = read_config(configs_dir, device["name"])
        if cfg is None:
            print(f"[!] Bỏ qua {device['name']}: chưa có {configs_dir}/{device['name']}.cfg")
            continue
        d = score_device(device, policy, cfg)
        devices_out.append(d)
        tot_earned += d["earned"]; tot_total += d["total"]

    overall = round(tot_earned / tot_total * 100, 1) if tot_total else 0.0
    report = {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config_source": str(configs_dir),
        "n_rules": len(policy["rules"]),
        "overall_score": overall,
        "devices": devices_out,
    }

    (out_dir / "compliance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "compliance.html").write_text(render_html(report), encoding="utf-8")
    print_table(report)
    print(f"Đã ghi: {out_dir/'compliance.json'}")
    print(f"Đã ghi: {out_dir/'compliance.html'}")


if __name__ == "__main__":
    main()
