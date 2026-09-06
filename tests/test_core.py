"""
Unit tests for TerraLocator's core logic: geometry math, the hazard
layer, GPS/sensor parsing, and the Overpass-to-GeoJSON converter. None
of these need a phone, a display, or a live internet connection — they
test the actual logic using saved/synthetic data shaped exactly like
the real thing.

Run with: python -m pytest tests/ -v
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import fetch_region
from terralocator.geomath import (
    Coordinate, bearing_to_compass, format_distance, haversine_distance_m,
    initial_bearing_deg, navigate,
)
from terralocator.hazards import HazardLayer, HazardPoint
from terralocator.location import _parse_termux_location, _parse_termux_sensor_orientation

COMPASS_POINTS = {
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
}


# ---------------------------------------------------------------------
# geomath.py
# ---------------------------------------------------------------------

def test_coordinate_validates_range():
    Coordinate(lat=90, lon=180)
    Coordinate(lat=-90, lon=-180)
    with pytest.raises(ValueError):
        Coordinate(lat=91, lon=0)
    with pytest.raises(ValueError):
        Coordinate(lat=0, lon=181)


def test_haversine_known_distance():
    # New Delhi to Mumbai is well documented as roughly 1140-1160 km great-circle.
    delhi = Coordinate(lat=28.6139, lon=77.2090)
    mumbai = Coordinate(lat=19.0760, lon=72.8777)
    dist_km = haversine_distance_m(delhi, mumbai) / 1000
    assert 1130 < dist_km < 1170


def test_haversine_zero_for_identical_points():
    p = Coordinate(lat=22.43, lon=87.87)
    assert haversine_distance_m(p, p) == pytest.approx(0.0, abs=1e-6)


def test_bearing_due_north_and_east():
    a = Coordinate(lat=0, lon=0)
    assert initial_bearing_deg(a, Coordinate(lat=1, lon=0)) == pytest.approx(0.0, abs=0.01)
    assert initial_bearing_deg(a, Coordinate(lat=0, lon=1)) == pytest.approx(90.0, abs=0.01)


def test_bearing_to_compass_labels():
    assert bearing_to_compass(0) == "N"
    assert bearing_to_compass(90) == "E"
    assert bearing_to_compass(180) == "S"
    assert bearing_to_compass(270) == "W"
    assert bearing_to_compass(359) == "N"


def test_format_distance():
    assert format_distance(500) == "500 m"
    assert format_distance(1500) == "1.50 km"


def test_navigate_end_to_end():
    here = Coordinate(lat=22.4327, lon=87.8697)
    target = Coordinate(lat=22.4400, lon=87.8800)
    info = navigate(here, target)
    assert info.distance_m > 0
    assert 0 <= info.bearing_deg < 360
    assert info.compass in COMPASS_POINTS


# ---------------------------------------------------------------------
# hazards.py
# ---------------------------------------------------------------------

def test_hazard_point_rejects_unknown_type():
    with pytest.raises(ValueError):
        HazardPoint.new(type="dragons", lat=0, lon=0, title="nope")


def test_hazard_layer_save_and_reload(tmp_path):
    path = tmp_path / "hazards.geojson"
    layer = HazardLayer(path)
    layer.add(HazardPoint.new(type="police", lat=22.43, lon=87.87, title="Test station"))
    layer.add(HazardPoint.new(type="danger", lat=22.44, lon=87.88, title="Test hazard", verified=True))

    reloaded = HazardLayer(path)
    assert len(reloaded.points) == 2
    assert {p.title for p in reloaded.points} == {"Test station", "Test hazard"}


def test_hazard_layer_defaults_to_unverified(tmp_path):
    layer = HazardLayer(tmp_path / "h.geojson")
    layer.add(HazardPoint.new(type="poi", lat=0, lon=0, title="x"))
    assert layer.unverified_count() == 1


def test_hazard_near_query(tmp_path):
    layer = HazardLayer(tmp_path / "h.geojson")
    center = Coordinate(lat=22.4327, lon=87.8697)
    layer.add(HazardPoint.new(type="poi", lat=22.4327, lon=87.8697, title="Right here"))
    layer.add(HazardPoint.new(type="poi", lat=10.0, lon=10.0, title="Far away"))
    nearby = layer.near(center, radius_m=1000)
    assert len(nearby) == 1
    assert nearby[0].title == "Right here"


def test_hazard_remove(tmp_path):
    layer = HazardLayer(tmp_path / "h.geojson")
    point = HazardPoint.new(type="poi", lat=0, lon=0, title="temp")
    layer.add(point)
    assert layer.remove(point.id) is True
    assert layer.remove(point.id) is False
    assert len(layer.points) == 0


def test_shipped_demo_dataset_is_all_unverified():
    demo_path = Path(__file__).resolve().parent.parent / "data" / "regions" / "demo.hazards.geojson"
    layer = HazardLayer(demo_path)
    assert len(layer.points) > 0
    assert all(not p.verified for p in layer.points), (
        "Demo dataset must never ship pre-verified — it's example data only."
    )


# ---------------------------------------------------------------------
# location.py — parsing logic against saved sample outputs
# ---------------------------------------------------------------------

SAMPLE_TERMUX_LOCATION = json.dumps({
    "latitude": 22.4327, "longitude": 87.8697, "altitude": 12.5,
    "accuracy": 8.2, "bearing": 0.0, "speed": 0.0, "provider": "gps",
})

SAMPLE_TERMUX_SENSOR = json.dumps({
    "Android Orientation Sensor": {"values": [123.4, 1.2, -0.5]},
})


def test_parse_termux_location_success():
    fix = _parse_termux_location(SAMPLE_TERMUX_LOCATION)
    assert fix is not None
    assert fix.lat == 22.4327
    assert fix.lon == 87.8697
    assert fix.provider == "gps"
    assert fix.accuracy_m == 8.2


def test_parse_termux_location_handles_garbage():
    assert _parse_termux_location("not json") is None
    assert _parse_termux_location(json.dumps({"foo": "bar"})) is None


def test_parse_termux_sensor_orientation():
    assert _parse_termux_sensor_orientation(SAMPLE_TERMUX_SENSOR) == pytest.approx(123.4)


def test_manual_location_roundtrip(tmp_path, monkeypatch):
    import terralocator.location as loc
    monkeypatch.setattr(loc, "MANUAL_OVERRIDE_PATH", tmp_path / "manual_location.json")
    loc.set_manual_location(lat=1.5, lon=2.5)
    fix = loc._read_manual_override()
    assert fix.lat == 1.5 and fix.lon == 2.5
    assert fix.provider == "manual"


# ---------------------------------------------------------------------
# fetch_region.py — Overpass response -> GeoJSON conversion
# ---------------------------------------------------------------------

SAMPLE_OVERPASS_RESPONSE = {
    "elements": [
        {"type": "node", "id": 1, "lat": 22.43, "lon": 87.87, "tags": {"amenity": "police"}},
        {"type": "node", "id": 2, "lat": 22.44, "lon": 87.88},  # untagged -> not its own feature
        {"type": "node", "id": 3, "lat": 22.45, "lon": 87.89},
        {"type": "node", "id": 4, "lat": 22.46, "lon": 87.90},
        {"type": "way", "id": 100, "nodes": [3, 4], "tags": {"highway": "residential", "name": "Test Road"}},
    ],
}


def test_build_query_validates_bbox():
    query = fetch_region.build_query("22.0,87.0,23.0,88.0")
    assert "22.0,87.0,23.0,88.0" in query
    with pytest.raises(ValueError):
        fetch_region.build_query("not,a,valid,bbox")
    with pytest.raises(ValueError):
        fetch_region.build_query("only,three,values")


def test_overpass_to_geojson_converts_nodes_and_ways():
    geojson = fetch_region.overpass_to_geojson(SAMPLE_OVERPASS_RESPONSE)
    types = [f["geometry"]["type"] for f in geojson["features"]]
    assert types.count("Point") == 1
    assert types.count("LineString") == 1

    road = next(f for f in geojson["features"] if f["geometry"]["type"] == "LineString")
    assert road["geometry"]["coordinates"] == [[87.89, 22.45], [87.90, 22.46]]
    assert road["properties"]["name"] == "Test Road"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
