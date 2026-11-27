"""TC-R: kiem thu duong/am tung luat CIS trong compliance/policy/cis_rules.yaml.

Moi ca gom: ma luat, doan cau hinh dau vao, ket qua mong doi (True = dat).
Cac ca danh dau xfail ghi nhan han che da biet cua bo luat (dat gia / truot oan).
"""
import pytest

from conftest import REPO
from score import load_yaml, evaluate_rule, strip_comments

POLICY = load_yaml(REPO / "compliance/policy/cis_rules.yaml")
RULES = {r["id"]: r for r in POLICY["rules"]}

CASES = [
    # (ma ca, luat, cau hinh, mong doi)
    ("R01", "CIS-1.1", "ssh server {\n    admin-state enable\n}", True),
    ("R02", "CIS-1.1", "telnet server {\n    admin-state enable\n}", False),
    ("R03", "CIS-1.1", "line vty\n transport input telnet", False),
    ("R04", "CIS-1.2", "line vty\n transport input ssh", True),
    ("R05", "CIS-1.2", "ssh server {\n    admin-state enable\n}", True),
    ("R06", "CIS-1.2", "line vty\n login local", False),
    ("R07", "CIS-2.1", "snmp {\n    security-level auth-priv\n}", True),
    ("R08", "CIS-2.1", "snmp-server community public RO", False),
    ("R09", "CIS-2.1", "snmp {\n    community private\n}", False),
    ("R10", "CIS-2.2", "snmp-server group v3group v3 priv", True),
    ("R11", "CIS-2.2", "snmp {\n    security-level auth-priv\n}", True),
    ("R12", "CIS-2.2", "snmp-server community netops RO", False),
    ("R13", "CIS-3.1", "banner motd ^CCanh bao^C", True),
    ("R14", "CIS-3.1", 'banner {\n    login-banner "Canh bao"\n}', True),
    ("R15", "CIS-3.1", "hostname edge1", False),
    ("R16", "CIS-4.1", "log syslog informational", True),
    ("R17", "CIS-4.1", "logging {\n    remote-server 172.20.20.3\n}", True),
    ("R18", "CIS-4.1", "hostname edge1", False),
    ("R19", "CIS-4.2", "ntp server 172.20.20.2", True),
    ("R20", "CIS-4.2", "hostname edge1", False),
    ("R21", "CIS-5.1", "router bgp 65000\n neighbor 10.0.1.2 password MAU_BGP_KEY", True),
    ("R22", "CIS-5.1", "router bgp 65000\n neighbor 10.0.1.2 remote-as 65010", False),
    ("R23", "CIS-6.1", "access-list mgmt-in permit 172.20.20.0/24", True),
    ("R24", "CIS-6.1", "hostname edge1", False),
    ("R25", "CIS-7.1", "hostname edge1", True),
    ("R26", "CIS-7.1", "ip http server", False),
    ("R27", "CIS-7.2", "service password-encryption", True),
    ("R28", "CIS-7.2", "hostname edge1", False),
    ("R29", "CIS-8.1", "line vty\n exec-timeout 5 0", True),
    ("R30", "CIS-8.1", "ssh server {\n    idle-timeout 300\n}", True),
    ("R31", "CIS-8.1", "line vty\n transport input ssh", False),
    ("R32", "CIS-8.2", "hostname edge1", True),
    ("R33", "CIS-8.2", "service finger", False),
    ("R34", "CIS-9.1", "no ip source-route", True),
    ("R35", "CIS-9.1", "hostname edge1", False),
    ("R36", "CIS-9.2", "log file /var/log/frr/frr.log", True),
    ("R37", "CIS-9.2", "hostname edge1", False),
    ("R38", "CIS-10.1", "username admin secret Xy9#long", True),
    ("R39", "CIS-10.1", "password cisco", False),
    ("R40", "CIS-10.2", "line vty\n login local", True),
    ("R41", "CIS-10.2", "line vty\n exec-timeout 5 0", False),
    ("R42", "CIS-11.1", "hostname edge1", True),
    ("R43", "CIS-11.1", "system {\n    host-name spine1\n}", True),
    ("R44", "CIS-11.1", "interface eth1\n ip address 10.0.1.1/30", False),
    # Da sua mau CIS-5.1: chi tinh mat khau gan voi phien dinh tuyen
    ("R49", "CIS-5.1", "username admin password admin", False),
    ("R52", "CIS-5.1", "service password-encryption", False),
]

KNOWN_ISSUES = [
    # Dat gia: regex 'log.*local' cua CIS-9.2 khop dong 'login local'
    ("R45", "CIS-9.2", "line vty\n login local", False, "CIS-9.2 khop nham 'login local' (dat gia)"),
    # R46, R47 (SR Linux JSON truot oan) da khac phuc bang lam phang JSON: xem test_flatten.py
    # Dat gia: regex khong xet phu dinh / gia tri / ranh gioi tu
    ("R48", "CIS-3.1", "no banner motd", False, "CIS-3.1 khong xet phu dinh 'no banner' (dat gia)"),
    ("R50", "CIS-6.1", "database oracle", False, "CIS-6.1 khop chuoi con 'acl' trong 'oracle' (dat gia)"),
    ("R51", "CIS-8.1", "line vty\n exec-timeout 0 0", False, "CIS-8.1 khong kiem tra gia tri 0 0 (dat gia)"),
]


@pytest.mark.parametrize("case,rule,cfg,expected", CASES, ids=[c[0] for c in CASES])
def test_rule(case, rule, cfg, expected):
    assert evaluate_rule(RULES[rule], cfg) is expected


@pytest.mark.parametrize("case,rule,cfg,expected,why", KNOWN_ISSUES, ids=[c[0] for c in KNOWN_ISSUES])
def test_known_issue(case, rule, cfg, expected, why):
    if evaluate_rule(RULES[rule], cfg) is not expected:
        pytest.xfail(why)


def test_all_rules_covered():
    """Moi luat trong chinh sach co it nhat mot ca dat va mot ca vi pham."""
    pos = {r for _, r, _, e in CASES if e}
    neg = {r for _, r, _, e in CASES if not e}
    assert set(RULES) == pos == neg


def test_comment_lines_ignored():
    """Dong chu thich '!' hoac '#' khong duoc tinh khi cham."""
    text = strip_comments("! telnet server {\n# service finger\nhostname edge1")
    assert evaluate_rule(RULES["CIS-1.1"], text) is True
    assert evaluate_rule(RULES["CIS-8.2"], text) is True
