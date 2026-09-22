#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SO SANH KET QUA QUET TRUOC/SAU HARDENING
=========================================
Phan viec cua Tung — tinh muc giam rui ro sau khi ap dung CIS.

Doc 2 file bao cao (truoc va sau), so sanh va tao bao cao doi chung.

Chay:
  python security/attacks/compare_results.py \\
      --before security/reports/scan_before.json \\
      --after  security/reports/scan_after.json
"""
import argparse
import datetime as dt
import json
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compare_device(before: dict, after: dict) -> dict:
    before_ports = {p["port"] for p in before.get("open_ports", [])}
    after_ports = {p["port"] for p in after.get("open_ports", [])}
    before_risky = {r["port"] for r in before.get("risky_services", [])}
    after_risky = {r["port"] for r in after.get("risky_services", [])}

    closed_ports = before_ports - after_ports
    new_ports = after_ports - before_ports
    fixed_risky = before_risky - after_risky
    remaining_risky = after_risky

    risk_before = len(before_risky)
    risk_after = len(after_risky)
    reduction = ((risk_before - risk_after) / risk_before * 100) if risk_before > 0 else 0.0

    return {
        "device": before.get("device_name", before.get("ip")),
        "ip": before.get("ip"),
        "ports_before": len(before_ports),
        "ports_after": len(after_ports),
        "closed_ports": sorted(closed_ports),
        "new_ports": sorted(new_ports),
        "risky_before": risk_before,
        "risky_after": risk_after,
        "fixed_risky": sorted(fixed_risky),
        "remaining_risky": sorted(remaining_risky),
        "risk_reduction_pct": round(reduction, 1),
    }


def render_html(comparison: dict) -> str:
    devices_html = ""
    for d in comparison["devices"]:
        color = "#16a34a" if d["risk_reduction_pct"] >= 80 else (
            "#d97706" if d["risk_reduction_pct"] >= 50 else "#dc2626")
        devices_html += f"""
        <div class="card">
          <div class="card-h">
            <div><b>{d['device']}</b> <span class="muted">{d['ip']}</span></div>
            <div class="score" style="color:{color}">-{d['risk_reduction_pct']}% rui ro</div>
          </div>
          <table>
            <tr><td>Cong mo truoc</td><td><b>{d['ports_before']}</b></td>
                <td>Cong mo sau</td><td><b>{d['ports_after']}</b></td></tr>
            <tr><td>Dich vu nguy hiem truoc</td><td><b>{d['risky_before']}</b></td>
                <td>Dich vu nguy hiem sau</td><td><b>{d['risky_after']}</b></td></tr>
            <tr><td>Cong da dong</td><td colspan="3">{', '.join(map(str, d['closed_ports'])) or 'Khong co'}</td></tr>
            <tr><td>Da khac phuc</td><td colspan="3">{', '.join(map(str, d['fixed_risky'])) or 'Khong co'}</td></tr>
            <tr><td>Con ton tai</td><td colspan="3">{', '.join(map(str, d['remaining_risky'])) or 'Khong co'}</td></tr>
          </table>
        </div>"""

    overall_color = "#16a34a" if comparison["overall_reduction"] >= 80 else (
        "#d97706" if comparison["overall_reduction"] >= 50 else "#dc2626")

    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>So sanh an ninh truoc/sau hardening</title>
<style>
  :root{{--bg:#f8fafc;--fg:#0f172a;--muted:#64748b;--line:#e2e8f0;--card:#fff;}}
  @media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#0f172a;--fg:#e2e8f0;--muted:#94a3b8;--line:#1e293b;--card:#1e293b;}}}}
  body{{font-family:system-ui,sans-serif;margin:0;background:var(--bg);color:var(--fg);}}
  .wrap{{max-width:960px;margin:0 auto;padding:24px 16px;}}
  h1{{font-size:22px;margin:0 0 4px;}}
  .overall{{font-size:40px;font-weight:800;}}
  .muted{{color:var(--muted);}} .small{{font-size:13px;}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:16px 0;}}
  .card-h{{display:flex;justify-content:space-between;align-items:center;}}
  .score{{font-size:28px;font-weight:800;}}
  table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:14px;}}
  td{{padding:7px 8px;border-bottom:1px solid var(--line);}}
</style></head><body><div class="wrap">
  <h1>Bao cao doi chung an ninh mang — Truoc/Sau hardening</h1>
  <div class="muted small">Sinh luc {comparison['generated_at']}</div>
  <div style="margin:14px 0;">Giam rui ro toan he thong:
    <span class="overall" style="color:{overall_color}">{comparison['overall_reduction']}%</span>
  </div>
  {devices_html}
  <p class="muted small">Sinh tu dong boi security/attacks/compare_results.py</p>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="So sanh ket qua quet truoc/sau hardening.")
    ap.add_argument("--before", required=True, help="File JSON ket qua TRUOC hardening")
    ap.add_argument("--after", required=True, help="File JSON ket qua SAU hardening")
    ap.add_argument("--output", default="comparison", help="Ten file output (khong can phan mo rong)")
    args = ap.parse_args()

    before = load_report(Path(args.before))
    after = load_report(Path(args.after))

    before_map = {t["device_name"]: t for t in before.get("targets", [])}
    after_map = {t["device_name"]: t for t in after.get("targets", [])}

    devices_comp = []
    total_risky_before, total_risky_after = 0, 0

    for name in before_map:
        if name in after_map:
            comp = compare_device(before_map[name], after_map[name])
            devices_comp.append(comp)
            total_risky_before += comp["risky_before"]
            total_risky_after += comp["risky_after"]

    overall = round(
        (total_risky_before - total_risky_after) / total_risky_before * 100, 1
    ) if total_risky_before > 0 else 0.0

    comparison = {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "before_scan": args.before,
        "after_scan": args.after,
        "overall_reduction": overall,
        "devices": devices_comp,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"{args.output}.json"
    html_path = REPORTS_DIR / f"{args.output}.html"

    json_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(comparison), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"BAO CAO DOI CHUNG AN NINH MANG")
    print(f"{'='*60}")
    for d in devices_comp:
        print(f"\n  {d['device']} ({d['ip']}):")
        print(f"    Cong mo:     {d['ports_before']} -> {d['ports_after']}")
        print(f"    Nguy hiem:   {d['risky_before']} -> {d['risky_after']}")
        print(f"    Giam rui ro: {d['risk_reduction_pct']}%")
        if d['closed_ports']:
            print(f"    Cong da dong: {d['closed_ports']}")
    print(f"\n  GIAM RUI RO TOAN HE THONG: {overall}%")
    print(f"\n[+] Da ghi: {json_path}")
    print(f"[+] Da ghi: {html_path}")


if __name__ == "__main__":
    main()
