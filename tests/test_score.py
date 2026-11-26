"""TC-S: kiem thu cong cu cham diem score.py tren bo cau hinh mau va kich ban quy mo."""
import json
import shutil
import subprocess
import sys
import time

import pytest

from conftest import REPO
from score import run_scoring

SOT = REPO / "sot/devices.yaml"
POL = REPO / "compliance/policy/cis_rules.yaml"
CFG = REPO / "compliance/configs"

GOLDEN = {  # thiet bi: (diem %, earned, total, so vi pham)
    "edge1": (61.7, 37, 60, 7), "spine1": (48.9, 22, 45, 7), "spine2": (55.6, 25, 45, 6),
    "leaf1": (42.2, 19, 45, 8), "leaf2": (44.4, 20, 45, 7), "leaf3": (66.7, 40, 60, 6),
}


@pytest.fixture(scope="module")
def golden():
    return run_scoring(SOT, POL, CFG / "golden")


@pytest.fixture(scope="module")
def after():
    return run_scoring(SOT, POL, CFG / "after")


@pytest.mark.parametrize("dev", list(GOLDEN))
def test_golden_per_device(golden, dev):
    d = {x["device"]: x for x in golden["devices"]}[dev]
    assert (d["score"], d["earned"], d["total"], d["n_violations"]) == GOLDEN[dev]


def test_golden_overall(golden):
    assert golden["overall_score"] == 54.3
    assert sum(d["earned"] for d in golden["devices"]) == 163
    assert sum(d["total"] for d in golden["devices"]) == 300
    assert sum(d["n_violations"] for d in golden["devices"]) == 41


def test_after_all_pass(after):
    assert after["overall_score"] == 100.0
    assert all(d["n_violations"] == 0 for d in after["devices"])


def test_rules_per_os(golden):
    n = {d["device"]: d["n_rules"] for d in golden["devices"]}
    assert n["edge1"] == n["leaf3"] == 18
    assert n["spine1"] == n["spine2"] == n["leaf1"] == n["leaf2"] == 15


def test_weighted_not_mean(golden):
    mean = sum(d["score"] for d in golden["devices"]) / 6
    assert abs(mean - 53.25) < 1e-9 and golden["overall_score"] == 54.3


def test_missing_config_is_skipped(tmp_path):
    for n in ("edge1", "spine1"):
        shutil.copy(CFG / "golden" / f"{n}.cfg", tmp_path)
    rep = run_scoring(SOT, POL, tmp_path)
    assert [d["device"] for d in rep["devices"]] == ["edge1", "spine1"]


def test_compare_cli(tmp_path):
    r = subprocess.run([sys.executable, str(REPO / "compliance/tools/score.py"), "--compare",
                        str(CFG / "golden"), str(CFG / "after"), "--out", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    cmp = json.loads((tmp_path / "comparison.json").read_text(encoding="utf-8"))
    assert cmp["improvement"] == 45.7
    assert (tmp_path / "comparison.html").exists()


@pytest.mark.parametrize("n,before", [(3, 52.0), (9, 53.6), (12, 54.3)])
def test_scale_scenarios(n, before):
    sot = REPO / f"sot/scenarios/devices_{n}.yaml"
    b = run_scoring(sot, POL, CFG / "scale_before")
    a = run_scoring(sot, POL, CFG / "scale_after")
    assert len(b["devices"]) == n
    assert b["overall_score"] == before and a["overall_score"] == 100.0


def test_scoring_time_12_devices():
    sot = REPO / "sot/scenarios/devices_12.yaml"
    t0 = time.perf_counter()
    for _ in range(20):
        run_scoring(sot, POL, CFG / "scale_before")
    ms = (time.perf_counter() - t0) / 20 * 1000
    print(f"\n[TC-S-PERF] cham 12 thiet bi x 18 luat: {ms:.1f} ms/lan")
    assert ms < 1000
