"""TC-D: kiem thu tinh nhat quan cua nguon du lieu tin cay va viec sinh inventory."""
import ipaddress
from collections import Counter

import yaml

from conftest import REPO
import sot_to_inventory

SOT = yaml.safe_load((REPO / "sot/devices.yaml").read_text(encoding="utf-8"))
DEV = SOT["devices"]


def test_device_count_and_os():
    assert len(DEV) == 6
    assert Counter(d["os"] for d in DEV) == {"srlinux": 4, "frr": 2}


def test_unique_keys():
    for key in ("name", "mgmt_ip", "loopback_ip"):
        vals = [d[key] for d in DEV]
        assert len(vals) == len(set(vals)), key
    asns = [d["bgp"]["asn"] for d in DEV]
    assert len(asns) == len(set(asns))


def _links():
    nets = {}
    for d in DEV:
        for i in d.get("interfaces", []):
            nets.setdefault(ipaddress.ip_interface(i["ipv4"]).network, []).append((d["name"], i["ipv4"]))
    return nets


def test_every_p2p_subnet_has_two_ends():
    nets = _links()
    assert len(nets) == 6
    assert all(len(v) == 2 for v in nets.values())


def test_bgp_neighbors_match_peers():
    ip_owner = {i["ipv4"].split("/")[0]: d for d in DEV for i in d.get("interfaces", [])}
    total = 0
    for d in DEV:
        for nb in d["bgp"]["neighbors"]:
            peer = ip_owner[nb["address"]]
            assert peer["bgp"]["asn"] == nb["remote_as"], (d["name"], nb)
            total += 1
    assert total == 12          # 6 phien eBGP x 2 phia


def test_inventory_generated(tmp_path, monkeypatch):
    out = tmp_path / "hosts.yml"
    monkeypatch.setattr(sot_to_inventory, "OUT", out)
    sot_to_inventory.main()
    inv = yaml.safe_load(out.read_text(encoding="utf-8").split("\n", 1)[1])
    groups = inv["all"]["children"]
    assert sorted(groups) == ["frr", "srlinux"]
    assert len(groups["srlinux"]["hosts"]) == 4 and len(groups["frr"]["hosts"]) == 2
    assert groups["frr"]["hosts"]["edge1"]["ansible_host"] == "172.20.20.10"
