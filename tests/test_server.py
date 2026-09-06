"""
End-to-end test: starts the REAL TerraLocator server on a throwaway
port and hits it with real HTTP requests over a real socket, exactly
like the browser frontend does. This is this project's equivalent of
a GUI smoke test — it proves the whole request/response path works,
not just each function in isolation.

Run with: python -m pytest tests/test_server.py -v
"""
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import terralocator.location as location_module
from terralocator.hazards import HazardLayer, HazardPoint
from terralocator.location import LocationFix
from terralocator.server import make_handler

PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"


@pytest.fixture
def running_server(tmp_path, monkeypatch):
    # Force a known, fake GPS fix so this test never depends on Termux
    # or real GPS hardware being present wherever it runs.
    fake_fix = LocationFix(lat=22.4327, lon=87.8697, provider="manual", accuracy_m=5.0)
    monkeypatch.setattr(location_module, "get_location", lambda: fake_fix)
    monkeypatch.setattr(location_module, "get_heading_deg", lambda: 42.0)

    layer = HazardLayer(tmp_path / "hazards.geojson")
    layer.add(HazardPoint.new(type="police", lat=22.4327, lon=87.8697, title="Test station"))

    server = ThreadingHTTPServer(("127.0.0.1", PORT), make_handler(layer))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield server
    server.shutdown()
    server.server_close()


def _get_json(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def _get_raw(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as resp:
        return resp.status, resp.read()


def test_index_page_served(running_server):
    status, body = _get_raw("/")
    assert status == 200
    assert b"TerraLocator" in body


def test_location_endpoint_returns_fake_fix(running_server):
    status, data = _get_json("/api/location")
    assert status == 200
    assert data["lat"] == 22.4327
    assert data["lon"] == 87.8697


def test_heading_endpoint(running_server):
    status, data = _get_json("/api/heading")
    assert status == 200
    assert data["heading_deg"] == 42.0


def test_hazards_endpoint_returns_geojson(running_server):
    status, data = _get_json("/api/hazards")
    assert status == 200
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["title"] == "Test station"


def test_navigate_endpoint(running_server):
    status, data = _get_json("/api/navigate?lat=22.4400&lon=87.8800")
    assert status == 200
    assert data["distance_m"] > 0
    assert "compass" in data


def test_navigate_requires_lat_lon(running_server):
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _get_json("/api/navigate")
    assert exc_info.value.code == 400


def test_post_new_hazard_defaults_to_unverified(running_server):
    payload = json.dumps({"type": "danger", "lat": 1.0, "lon": 2.0, "title": "New hazard"}).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/api/hazards", data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        status, data = resp.status, json.loads(resp.read())
    assert status == 201
    assert data["properties"]["verified"] is False

    _, hazards = _get_json("/api/hazards")
    assert len(hazards["features"]) == 2  # the fixture's one + this new one


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
