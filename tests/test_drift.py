"""TC-T: kiem thu logic phat hien troi cau hinh (thay ket noi SSH bang du lieu gia lap)."""
import pytest

import drift_check

DEV = {"name": "leaf3", "os": "frr", "mgmt_ip": "172.20.20.23"}
BASE = ("frr version 10.0\nfrr defaults traditional\nhostname leaf3\nservice password-encryption\n"
        "log syslog informational\n!\nrouter bgp 65103\n neighbor 10.0.23.1 remote-as 65020\n")


@pytest.fixture()
def baseline(tmp_path, monkeypatch):
    (tmp_path / "compliance/configs/base").mkdir(parents=True)
    (tmp_path / "compliance/configs/base/leaf3.cfg").write_text(BASE, encoding="utf-8")
    monkeypatch.setattr(drift_check, "REPO", tmp_path)
    return "base"


def _live(monkeypatch, text):
    monkeypatch.setattr(drift_check, "collect_live_config", lambda *a: text)


def test_normalize_ignores_noise():
    lines = drift_check.normalize_config(BASE)
    assert "hostname leaf3" in lines
    assert not any(l.startswith(("frr version", "frr defaults", "!")) for l in lines)


def test_no_drift(baseline, monkeypatch):
    _live(monkeypatch, BASE.replace("hostname", "  hostname"))   # khac khoang trang van KHOP
    r = drift_check.check_drift(DEV, baseline)
    assert r["drifted"] is False and "error" not in r


def test_removed_line_detected(baseline, monkeypatch):
    _live(monkeypatch, BASE.replace("service password-encryption\n", ""))
    r = drift_check.check_drift(DEV, baseline)
    assert r["drifted"] and r["removed_lines"] == ["service password-encryption"]


def test_added_line_detected(baseline, monkeypatch):
    _live(monkeypatch, BASE + "ip http server\n")
    r = drift_check.check_drift(DEV, baseline)
    assert r["drifted"] and r["added_lines"] == ["ip http server"]


def test_unreachable_device(baseline, monkeypatch):
    _live(monkeypatch, "")
    r = drift_check.check_drift(DEV, baseline)
    assert r["error"] == "Khong the thu thap cau hinh"


def test_missing_baseline(baseline, monkeypatch):
    _live(monkeypatch, BASE)
    r = drift_check.check_drift(DEV, "khong_co")
    assert "Khong co file baseline" in r["error"]
