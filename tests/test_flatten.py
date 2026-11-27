"""TC-F: lam phang cau hinh SR Linux dang JSON va cham bang mau check_flat.

Cau hinh mau duoi day mo phong ket qua nokia.srlinux.get path '/' (JSON-RPC),
gom tien to module YANG va danh sach co khoa. Gia tri mat khau la chuoi bam gia.
"""
import copy
import json

import pytest

from conftest import REPO
from score import load_yaml, evaluate_rule, normalize_config, flatten_json, mask_secrets, score_device

POLICY = load_yaml(REPO / "compliance/policy/cis_rules.yaml")
RULES = {r["id"]: r for r in POLICY["rules"]}

HARDENED = [{
    "srl_nokia-system:system": {
        "srl_nokia-system-name:name": {"host-name": "spine1"},
        "srl_nokia-ssh:ssh-server": {"admin-state": "enable", "timeout": 300},
        "srl_nokia-system-banner:banner": {"login-banner": "CANH BAO: He thong noi bo"},
        "srl_nokia-ntp:ntp": {"admin-state": "enable", "network-instance": "mgmt",
                              "server": [{"address": "172.20.20.2"}]},
        "srl_nokia-logging:logging": {
            "remote-server": [{"host": "172.20.20.3", "transport": "udp", "remote-port": 514}],
            "file": [{"file-name": "messages", "subsystem": [{"subsystem-name": "aaa"}]}],
        },
        "srl_nokia-json-rpc:json-rpc-server": {
            "network-instance": [{"name": "mgmt",
                                  "http": {"admin-state": "disable"},
                                  "https": {"admin-state": "enable"}}]},
        "srl_nokia-aaa:aaa": {"authentication": {"admin-user": {"password": "$y$j9T$GIA$BAM"}}},
    },
    "srl_nokia-acl:acl": {
        "acl-filter": [
            {"name": "cpm", "type": "ipv4", "entry": [{"sequence-id": 10}]},
            {"name": "mgmt-acl", "type": "ipv4",
             "entry": [{"sequence-id": 10, "action": {"accept": {}},
                        "match": {"ipv4": {"source-ip": {"prefix": "172.20.20.0/24"}}}},
                       {"sequence-id": 100, "action": {"drop": {}}}]},
        ]},
}]


def flat(cfg):
    text, fmt = normalize_config(json.dumps(cfg, indent=2))
    assert fmt == "flat"
    return text


def without(cfg, *keys):
    """Xoa mot nhanh theo chuoi khoa (vd 'srl_nokia-system:system', 'srl_nokia-ntp:ntp')."""
    c = copy.deepcopy(cfg)
    node = c[0]
    for k in keys[:-1]:
        node = node[k]
    del node[keys[-1]]
    return c


SYS = "srl_nokia-system:system"


def test_flatten_paths():
    text = flat(HARDENED)
    assert "/system/name/host-name = spine1" in text
    assert "/system/ntp/server[address=172.20.20.2]/address = 172.20.20.2" in text
    assert "/acl/acl-filter[name=mgmt-acl][type=ipv4]/entry[sequence-id=100]/action/drop" not in text  # dict rong
    assert "/acl/acl-filter[name=mgmt-acl][type=ipv4]/entry[sequence-id=10]/match/ipv4/source-ip/prefix" in text
    assert "srl_nokia" not in text


def test_cli_text_not_flattened():
    text, fmt = normalize_config("! chu thich\nhostname edge1\n")
    assert fmt == "cli" and text.strip() == "hostname edge1"


def test_mask_secrets():
    out = mask_secrets(flat(HARDENED))
    assert "$y$" not in out and "password = ***" in out


# (ma ca, luat, cau hinh, mong doi) — cau hinh da hardening thi moi luat SR Linux deu dat
MUTATIONS = [
    ("F01", "CIS-1.2", HARDENED, True),        # truoc day truot oan (R46)
    ("F02", "CIS-11.1", HARDENED, True),       # truoc day truot oan (R47)
    ("F03", "CIS-11.1", without(HARDENED, SYS, "srl_nokia-system-name:name"), False),
    ("F04", "CIS-3.1", HARDENED, True),
    ("F05", "CIS-3.1", without(HARDENED, SYS, "srl_nokia-system-banner:banner"), False),
    ("F06", "CIS-4.1", HARDENED, True),
    ("F07", "CIS-4.1", without(HARDENED, SYS, "srl_nokia-logging:logging", "remote-server"), False),
    ("F08", "CIS-4.2", HARDENED, True),
    ("F09", "CIS-4.2", without(HARDENED, SYS, "srl_nokia-ntp:ntp", "server"), False),
    ("F10", "CIS-6.1", HARDENED, True),
    ("F11", "CIS-7.1", HARDENED, True),
    ("F12", "CIS-7.2", HARDENED, True),
    ("F13", "CIS-8.1", HARDENED, True),
    ("F14", "CIS-8.1", without(HARDENED, SYS, "srl_nokia-ssh:ssh-server", "timeout"), False),
    ("F15", "CIS-9.2", HARDENED, True),
    ("F16", "CIS-1.1", HARDENED, True),
    ("F17", "CIS-10.1", HARDENED, True),
]


@pytest.mark.parametrize("case,rule,cfg,expected", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_flat_rule(case, rule, cfg, expected):
    assert evaluate_rule(RULES[rule], flat(cfg), "srlinux", "flat") is expected


def test_only_cpm_acl_fails():
    c = copy.deepcopy(HARDENED)
    c[0]["srl_nokia-acl:acl"]["acl-filter"] = c[0]["srl_nokia-acl:acl"]["acl-filter"][:1]
    assert evaluate_rule(RULES["CIS-6.1"], flat(c), "srlinux", "flat") is False


def test_http_enabled_fails():
    c = copy.deepcopy(HARDENED)
    c[0][SYS]["srl_nokia-json-rpc:json-rpc-server"]["network-instance"][0]["http"]["admin-state"] = "enable"
    assert evaluate_rule(RULES["CIS-7.1"], flat(c), "srlinux", "flat") is False


def test_cli_pattern_still_used_for_cli():
    """Cau hinh CLI cua SR Linux (bo mau) khong bi anh huong boi check_flat."""
    assert evaluate_rule(RULES["CIS-1.2"], "ssh server {\n admin-state enable\n}", "srlinux", "cli") is True


def test_flatten_list_without_key():
    lines = list(flatten_json({"a": [1, 2]}))
    assert lines == ["/a[0] = 1", "/a[1] = 2"]


def test_score_hardened_srlinux_full():
    dev = {"name": "spine1", "os": "srlinux", "role": "spine"}
    d = score_device(dev, POLICY, flat(HARDENED), "flat")
    failed = [r["id"] for r in d["results"] if not r["passed"]]
    # SNMPv3 chua cau hinh trong lab nen chi CIS-2.2 con truot
    assert failed == ["CIS-2.2"]


def _with(path_keys, value):
    c = copy.deepcopy(HARDENED)
    node = c[0]
    for k in path_keys[:-1]:
        node = node.setdefault(k, {})
    node[path_keys[-1]] = value
    return c


def test_snmpv2_noauth_group_fails():
    """Nhom SNMPv2 mac dinh cua Containerlab (community da ma hoa, no-auth-no-priv) bi tinh vi pham CIS-2.1."""
    c = _with([SYS, "srl_nokia-snmp:snmp", "access-group"],
              [{"name": "SNMPv2-RO-Community", "security-level": "no-auth-no-priv",
                "community-entry": [{"name": "RO-Community", "community": "$aes1$GIA$MA"}]}])
    assert evaluate_rule(RULES["CIS-2.1"], flat(c), "srlinux", "flat") is False
    assert evaluate_rule(RULES["CIS-2.2"], flat(c), "srlinux", "flat") is False


def test_aaa_idle_timeout_too_long_fails():
    c = _with([SYS, "srl_nokia-aaa:aaa", "authentication", "idle-timeout"], 7200)
    del c[0][SYS]["srl_nokia-ssh:ssh-server"]["timeout"]
    assert evaluate_rule(RULES["CIS-8.1"], flat(c), "srlinux", "flat") is False
    c[0][SYS]["srl_nokia-aaa:aaa"]["authentication"]["idle-timeout"] = 600
    assert evaluate_rule(RULES["CIS-8.1"], flat(c), "srlinux", "flat") is True


def test_telnet_in_acl_description_not_violation():
    c = copy.deepcopy(HARDENED)
    c[0]["srl_nokia-acl:acl"]["acl-filter"][0]["entry"][0]["description"] = "Accept incoming Telnet replies"
    assert evaluate_rule(RULES["CIS-1.1"], flat(c), "srlinux", "flat") is True


def test_ssh_server_list_form():
    """Ban SR Linux moi: ssh-server la danh sach co khoa name."""
    c = copy.deepcopy(HARDENED)
    c[0][SYS]["srl_nokia-ssh:ssh-server"] = [{"name": "mgmt", "admin-state": "enable", "timeout": 300}]
    t = flat(c)
    assert "/system/ssh-server[name=mgmt]/admin-state = enable" in t
    assert evaluate_rule(RULES["CIS-1.2"], t, "srlinux", "flat") is True
    assert evaluate_rule(RULES["CIS-8.1"], t, "srlinux", "flat") is True


def test_mask_keyed_path():
    t = "/system/snmp/access-group[name=A]/community-entry[name=B]/community = $aes1$X\n/system/tls/profile[name=p]/key = $aes1$Y"
    assert "$aes1$" not in mask_secrets(t)
