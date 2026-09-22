#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUET AN NINH MANG (Network Security Scanner)
=============================================
Phan viec cua Tung — do be mat tan cong TRUOC va SAU hardening.

Cong cu nay:
  1. Doc danh sach thiet bi tu SoT.
  2. Quet cong mo (port scan) bang nmap.
  3. Kiem tra dich vu nguy hiem (telnet, HTTP, SNMP v1/v2c).
  4. Xuat bao cao JSON de so sanh truoc/sau.

Chay:
  python security/attacks/network_scan.py                    # quet tat ca
  python security/attacks/network_scan.py --target 172.20.20.11  # quet 1 IP
  python security/attacks/network_scan.py --output before.json   # chi dinh file output

Yeu cau: pip install python-nmap ; nmap phai duoc cai tren he thong.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent.parent
SOT = REPO / "sot/devices.yaml"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


KNOWN_SERVICES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 143: "imap", 161: "snmp", 443: "https",
    830: "netconf", 8080: "http-alt", 57400: "gnmi",
}
RISKY_SERVICES = {"telnet", "finger", "snmp", "http", "ftp"}


def check_nmap_installed() -> bool:
    try:
        subprocess.run(["nmap", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def parse_port_range(ports: str) -> list:
    result = []
    for part in ports.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            result.extend(range(int(lo), int(hi) + 1))
        else:
            result.append(int(part))
    return result


def scan_ports_python(ip: str, ports: str = "1-1024") -> dict:
    """Quet cong mo bang Python socket (khong can nmap)."""
    import socket
    result = {
        "ip": ip,
        "open_ports": [],
        "risky_services": [],
        "scan_time": dt.datetime.now().isoformat(),
        "scanner": "python-socket",
    }
    port_list = parse_port_range(ports)
    for port in port_list:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            if s.connect_ex((ip, port)) == 0:
                service = KNOWN_SERVICES.get(port, "unknown")
                result["open_ports"].append({
                    "port": port, "protocol": "tcp",
                    "service": service, "product": "",
                })
                if service in RISKY_SERVICES:
                    result["risky_services"].append({
                        "port": port, "service": service,
                        "risk": f"Dich vu {service} khong an toan, nen tat hoac thay the.",
                    })
            s.close()
        except Exception:
            pass
    return result


def scan_ports(ip: str, ports: str = "1-1024") -> dict:
    """Quet cong mo bang nmap va tra ve ket qua."""
    result = {
        "ip": ip,
        "open_ports": [],
        "risky_services": [],
        "scan_time": dt.datetime.now().isoformat(),
    }

    try:
        proc = subprocess.run(
            ["nmap", "-sV", "-p", ports, "--open", ip, "-oX", "-"],
            capture_output=True, text=True, timeout=120,
        )
        output = proc.stdout

        import xml.etree.ElementTree as ET
        root = ET.fromstring(output)

        for host in root.findall(".//host"):
            for port_el in host.findall(".//port"):
                port_id = port_el.get("portid")
                protocol = port_el.get("protocol", "tcp")
                state_el = port_el.find("state")
                service_el = port_el.find("service")

                state = state_el.get("state", "unknown") if state_el is not None else "unknown"
                service_name = service_el.get("name", "unknown") if service_el is not None else "unknown"
                product = service_el.get("product", "") if service_el is not None else ""

                if state == "open":
                    port_info = {
                        "port": int(port_id),
                        "protocol": protocol,
                        "service": service_name,
                        "product": product,
                    }
                    result["open_ports"].append(port_info)

                    risky = ["telnet", "finger", "snmp", "http"]
                    if service_name in risky:
                        result["risky_services"].append({
                            "port": int(port_id),
                            "service": service_name,
                            "risk": f"Dich vu {service_name} khong an toan, nen tat hoac thay the.",
                        })

    except subprocess.TimeoutExpired:
        result["error"] = "Timeout khi quet"
    except Exception as e:
        result["error"] = str(e)

    return result


def scan_ssh_version(ip: str) -> dict:
    """Kiem tra phien ban SSH."""
    try:
        proc = subprocess.run(
            ["nmap", "-sV", "-p", "22", ip],
            capture_output=True, text=True, timeout=30,
        )
        return {"ip": ip, "ssh_scan": proc.stdout}
    except Exception as e:
        return {"ip": ip, "ssh_scan": f"Loi: {e}"}


def check_snmp_community(ip: str) -> dict:
    """Kiem tra SNMP community mac dinh (public/private)."""
    findings = []
    for community in ["public", "private"]:
        try:
            proc = subprocess.run(
                ["nmap", "-sU", "-p", "161", "--script",
                 f"snmp-brute", "--script-args",
                 f"snmp-brute.communitiesdb=/dev/null",
                 ip],
                capture_output=True, text=True, timeout=30,
            )
            if community in proc.stdout.lower():
                findings.append(f"SNMP community '{community}' dang hoat dong!")
        except Exception:
            pass
    return {"ip": ip, "snmp_findings": findings}


def main():
    ap = argparse.ArgumentParser(description="Quet an ninh mang truoc/sau hardening.")
    ap.add_argument("--target", help="IP cu the (mac dinh: quet tat ca tu SoT)")
    ap.add_argument("--output", default="scan_result.json", help="Ten file ket qua")
    ap.add_argument("--ports", default="1-1024", help="Dai cong quet (mac dinh: 1-1024)")
    args = ap.parse_args()

    use_nmap = check_nmap_installed()
    if not use_nmap:
        print("[*] nmap khong co — dung Python socket scanner (cai nmap de ket qua tot hon)")
    else:
        print("[*] Su dung nmap de quet")

    targets = []
    if args.target:
        targets.append({"name": "custom", "ip": args.target})
    else:
        sot = yaml.safe_load(SOT.read_text(encoding="utf-8"))
        for d in sot["devices"]:
            targets.append({"name": d["name"], "ip": d["mgmt_ip"]})

    print(f"\n{'='*60}")
    print(f"QUET AN NINH MANG — {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    report = {
        "scan_time": dt.datetime.now().isoformat(),
        "targets": [],
        "summary": {"total_open_ports": 0, "total_risky_services": 0},
    }

    for t in targets:
        print(f"\n[*] Dang quet {t['name']} ({t['ip']})...")
        result = scan_ports(t["ip"], args.ports) if use_nmap else scan_ports_python(t["ip"], args.ports)
        result["device_name"] = t["name"]
        report["targets"].append(result)

        n_open = len(result["open_ports"])
        n_risky = len(result["risky_services"])
        report["summary"]["total_open_ports"] += n_open
        report["summary"]["total_risky_services"] += n_risky

        print(f"    Cong mo: {n_open}")
        for p in result["open_ports"]:
            print(f"      {p['port']}/{p['protocol']}  {p['service']}  {p['product']}")

        if n_risky > 0:
            print(f"    [!] Dich vu NGUY HIEM: {n_risky}")
            for r in result["risky_services"]:
                print(f"      Port {r['port']}: {r['risk']}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / args.output
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] Da ghi bao cao: {out_path}")

    print(f"\n{'='*60}")
    print(f"TONG KET: {report['summary']['total_open_ports']} cong mo, "
          f"{report['summary']['total_risky_services']} dich vu nguy hiem")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
