#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONG CU CHAM DIEM TUAN THU (Compliance Scoring) — v2.0
=======================================================
Phan viec cua Quan (Business Analyst / Compliance-as-Code).

Luong xu ly:
  1. Doc Nguon du lieu tin cay (SoT)  -> biet co nhung thiet bi nao.
  2. Doc bo chinh sach CIS (policy)   -> cac phep kiem chung.
  3. Voi moi thiet bi, doc file cau hinh tuong ung.
  4. Danh gia tung luat ap dung: dat / vi pham.
  5. Tinh diem tuan thu co trong so theo muc nghiem trong.
  6. Xuat: bang ra man hinh + reports/compliance.json + reports/compliance.html

Chay:
  python tools/score.py                                  # dung configs/golden
  python tools/score.py --configs configs/live           # dung cau hinh that
  python tools/score.py --compare configs/golden configs/live   # doi chung truoc/sau
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path

import yaml

MODULE = Path(__file__).resolve().parent.parent
REPO = MODULE.parent
ROOT = MODULE


# --------------------------------------------------------------------- I/O
def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def strip_comments(text: str) -> str:
    lines = []
    for ln in text.splitlines():
        if re.match(r"^\s*[!#]", ln):
            continue
        lines.append(ln)
    return "\n".join(lines)


def read_config(configs_dir: Path, name: str) -> str | None:
    p = configs_dir / f"{name}.cfg"
    if not p.exists():
        return None
    return strip_comments(p.read_text(encoding="utf-8"))


# ----------------------------------------------------------------- danh gia
def rule_applies(rule: dict, os_name: str) -> bool:
    scope = rule.get("applies_to", "all")
    return scope == "all" or scope == os_name


def evaluate_rule(rule: dict, config_text: str) -> bool:
    chk = rule["check"]
    pattern = chk["pattern"]
    found = re.search(pattern, config_text) is not None
    if chk["type"] == "must_contain":
        return found
    if chk["type"] == "must_not_contain":
        return not found
    raise ValueError(f"Kieu kiem tra khong ho tro: {chk['type']}")


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
def print_table(report: dict, label: str = "") -> None:
    header = f"BAO CAO TUAN THU  —  {report['generated_at']}"
    if label:
        header += f"  [{label}]"
    print("\n" + "=" * 64)
    print(header)
    print("=" * 64)
    for d in report["devices"]:
        print(f"\n  {d['device']} ({d['os']}, {d['role']})   "
              f"Diem: {d['score']}%  [{d['n_rules']-d['n_violations']}/{d['n_rules']} luat dat]")
        for r in d["results"]:
            mark = "[OK] " if r["passed"] else "[FAIL]"
            flag = "" if r["passed"] else f"   -> {r['remediation']}"
            print(f"   {mark} [{r['severity']:<6}] {r['id']}  {r['title']}{flag}")
    print("\n" + "-" * 64)
    print(f"DIEM TUAN THU TOAN HE THONG: {report['overall_score']}%")
    print("-" * 64 + "\n")


def print_comparison(before: dict, after: dict) -> None:
    print("\n" + "=" * 64)
    print("DOI CHUNG TRUOC / SAU HARDENING")
    print("=" * 64)
    for db, da in zip(before["devices"], after["devices"]):
        diff = da["score"] - db["score"]
        arrow = "+" if diff >= 0 else ""
        print(f"\n  {db['device']}:  {db['score']}% -> {da['score']}%  ({arrow}{diff}%)")
        fixed = []
        for rb, ra in zip(db["results"], da["results"]):
            if not rb["passed"] and ra["passed"]:
                fixed.append(rb["id"])
        if fixed:
            print(f"    Da khac phuc: {', '.join(fixed)}")
        remaining = [r["id"] for r in da["results"] if not r["passed"]]
        if remaining:
            print(f"    Con vi pham:  {', '.join(remaining)}")
    diff_overall = after["overall_score"] - before["overall_score"]
    arrow = "+" if diff_overall >= 0 else ""
    print(f"\n  TONG THE: {before['overall_score']}% -> {after['overall_score']}%  ({arrow}{diff_overall}%)")
    print("=" * 64 + "\n")


def render_html(report: dict, comparison: dict | None = None) -> str:
    def color(p):
        return "#16a34a" if p >= 90 else "#d97706" if p >= 70 else "#dc2626"

    rows_html = ""
    for d in report["devices"]:
        rules_html = ""
        for r in d["results"]:
            badge = ("<span class='ok'>DAT</span>" if r["passed"]
                     else "<span class='bad'>VI PHAM</span>")
            rem = "" if r["passed"] else f"<div class='rem'>Khac phuc: {r['remediation']}</div>"
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
          <div class="muted small">{d['n_rules']-d['n_violations']}/{d['n_rules']} luat dat · {d['n_violations']} vi pham</div>
          <table>
            <thead><tr><th>Ma</th><th>Yeu cau</th><th>Muc</th><th>CLO</th><th>Trang thai</th></tr></thead>
            <tbody>{rules_html}</tbody>
          </table>
        </div>"""

    comparison_html = ""
    if comparison:
        comp_rows = ""
        for cb, ca in zip(comparison["before"]["devices"], comparison["after"]["devices"]):
            diff = ca["score"] - cb["score"]
            diff_color = "#16a34a" if diff > 0 else ("#dc2626" if diff < 0 else "#64748b")
            comp_rows += f"""<tr>
                <td><b>{cb['device']}</b></td>
                <td style="color:{color(cb['score'])}">{cb['score']}%</td>
                <td style="color:{color(ca['score'])}">{ca['score']}%</td>
                <td style="color:{diff_color};font-weight:700;">{"+" if diff>=0 else ""}{diff}%</td>
                <td>{cb['n_violations']}</td><td>{ca['n_violations']}</td>
            </tr>"""
        diff_overall = comparison["after"]["overall_score"] - comparison["before"]["overall_score"]
        comparison_html = f"""
        <div class="card" style="border-left:3px solid #16a34a;">
          <div class="card-h">
            <div><b>Doi chung truoc / sau hardening</b></div>
            <div class="score" style="color:#16a34a">+{diff_overall}%</div>
          </div>
          <table>
            <thead><tr><th>Thiet bi</th><th>Truoc</th><th>Sau</th><th>Thay doi</th><th>VP truoc</th><th>VP sau</th></tr></thead>
            <tbody>{comp_rows}</tbody>
          </table>
        </div>"""

    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bao cao tuan thu an ninh mang</title>
<style>
  :root{{--bg:#f8fafc;--fg:#0f172a;--muted:#64748b;--line:#e2e8f0;--card:#fff;}}
  @media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#0f172a;--fg:#e2e8f0;--muted:#94a3b8;--line:#1e293b;--card:#1e293b;}}}}
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
  <h1>Bao cao kiem soat tuan thu an ninh mang</h1>
  <div class="muted small">Sinh luc {report['generated_at']} · Bo luat: {report['n_rules']} · Thiet bi: {len(report['devices'])}</div>
  <div style="margin:14px 0;">Diem tuan thu toan he thong: <span class="overall">{report['overall_score']}%</span></div>
  {comparison_html}
  {rows_html}
  <p class="muted small">Sinh tu dong boi tools/score.py — Do an tu dong hoa cau hinh & an ninh mang.</p>
</div></body></html>"""


# --------------------------------------------------------------------- main
def run_scoring(sot_path, policy_path, configs_dir) -> dict:
    sot = load_yaml(sot_path)
    policy = load_yaml(policy_path)
    configs_dir = Path(configs_dir)

    devices_out, tot_earned, tot_total = [], 0, 0
    for device in sot["devices"]:
        cfg = read_config(configs_dir, device["name"])
        if cfg is None:
            print(f"[!] Bo qua {device['name']}: chua co {configs_dir}/{device['name']}.cfg")
            continue
        d = score_device(device, policy, cfg)
        devices_out.append(d)
        tot_earned += d["earned"]
        tot_total += d["total"]

    overall = round(tot_earned / tot_total * 100, 1) if tot_total else 0.0
    return {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config_source": str(configs_dir),
        "n_rules": len(policy["rules"]),
        "overall_score": overall,
        "devices": devices_out,
    }


def main():
    ap = argparse.ArgumentParser(description="Cham diem tuan thu cau hinh mang theo CIS.")
    ap.add_argument("--sot", default=str(REPO / "sot/devices.yaml"),
                    help="Nguon du lieu tin cay dung chung o goc repo")
    ap.add_argument("--policy", default=str(ROOT / "policy/cis_rules.yaml"))
    ap.add_argument("--configs", default=str(ROOT / "configs/golden"),
                    help="Thu muc chua <ten-thiet-bi>.cfg")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                    help="Doi chung 2 thu muc config (vd: configs/golden configs/live)")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.compare:
        before_dir, after_dir = args.compare
        print(f"[*] Cham diem TRUOC hardening: {before_dir}")
        report_before = run_scoring(args.sot, args.policy, before_dir)
        print_table(report_before, "TRUOC")

        print(f"[*] Cham diem SAU hardening: {after_dir}")
        report_after = run_scoring(args.sot, args.policy, after_dir)
        print_table(report_after, "SAU")

        print_comparison(report_before, report_after)

        comparison_data = {
            "before": report_before,
            "after": report_after,
            "improvement": round(
                report_after["overall_score"] - report_before["overall_score"], 1),
        }

        (out_dir / "comparison.json").write_text(
            json.dumps(comparison_data, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "comparison.html").write_text(
            render_html(report_after, comparison_data), encoding="utf-8")
        print(f"Da ghi: {out_dir / 'comparison.json'}")
        print(f"Da ghi: {out_dir / 'comparison.html'}")
    else:
        report = run_scoring(args.sot, args.policy, args.configs)
        print_table(report)

        (out_dir / "compliance.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "compliance.html").write_text(
            render_html(report), encoding="utf-8")
        print(f"Da ghi: {out_dir / 'compliance.json'}")
        print(f"Da ghi: {out_dir / 'compliance.html'}")


if __name__ == "__main__":
    main()
