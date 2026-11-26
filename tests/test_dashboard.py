"""TC-W: kiem thu bang dieu khien Flask (route va API) voi CSDL tam."""
import pytest

import app as dash


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "DB_PATH", tmp_path / "test.db")
    dash.init_db()
    dash.app.config["TESTING"] = True
    with dash.app.test_client() as c:
        yield c


@pytest.mark.parametrize("url", ["/", "/devices", "/metrics", "/topology"])
def test_pages_ok(client, url):
    assert client.get(url).status_code == 200


def test_scan_golden(client):
    r = client.post("/api/scan", json={"config_dir": "golden"})
    assert r.status_code == 200
    assert r.get_json()["overall_score"] == 54.3 and r.get_json()["devices"] == 6


def test_scan_default_without_json(client):
    r = client.post("/api/scan", data="khong phai json", content_type="text/plain")
    assert r.status_code == 200 and r.get_json()["overall_score"] == 54.3


@pytest.mark.parametrize("bad", ["../../etc", "khong_ton_tai", "/etc"])
def test_scan_rejects_bad_dir(client, bad):
    r = client.post("/api/scan", json={"config_dir": bad})
    assert r.status_code == 400 and "error" in r.get_json()


def test_compare(client):
    r = client.post("/api/compare", json={"before": "golden", "after": "after"})
    j = r.get_json()
    assert r.status_code == 200 and j["improvement"] == 45.7
    assert j["before"]["score"] == 54.3 and j["after"]["score"] == 100.0


def test_history_and_detail(client):
    sid = client.post("/api/scan", json={"config_dir": "after"}).get_json()["scan_id"]
    hist = client.get("/api/history").get_json()
    assert len(hist) == 1
    det = client.get(f"/api/scan/{sid}").get_json()
    assert det["scan"]["config_source"] == "after" and len(det["devices"]) == 6
    assert client.get("/api/scan/99999").status_code == 404


def test_scan_saved_to_db(client):
    client.post("/api/scan", json={"config_dir": "golden"})
    conn = dash.get_db()
    n_scan = conn.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
    n_dev = conn.execute("SELECT COUNT(*) FROM device_scores").fetchone()[0]
    conn.close()
    assert (n_scan, n_dev) == (1, 6)


def test_topology_from_sot():
    topo = dash.build_topology(dash.load_sot())
    assert len(topo["nodes"]) == 6 and len(topo["links"]) == 6 and topo["unlinked"] == []
