"""
Tests for fetch_country.py.

These need `pyrosm` installed (a heavier, optional dependency only
needed for country/state-scale extraction, not for running the app
itself) — they're skipped automatically if it isn't present. They run
against pyrosm's own tiny bundled sample PBF file, so no network access
or huge country download is needed to verify the pipeline actually
works end to end.

Run with: python -m pytest tests/test_fetch_country.py -v
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

pyrosm = pytest.importorskip("pyrosm", reason="pyrosm not installed — only needed for country-scale extraction")

import fetch_country


def test_json_safe_handles_numpy_and_nan():
    import numpy as np
    assert fetch_country.json_safe(np.int64(42)) == 42
    assert isinstance(fetch_country.json_safe(np.int64(42)), int)
    assert fetch_country.json_safe(np.uint32(7)) == 7
    assert fetch_country.json_safe(float("nan")) is None
    assert fetch_country.json_safe(float("inf")) is None
    assert fetch_country.json_safe(None) is None
    assert fetch_country.json_safe("plain string") == "plain string"
    assert fetch_country.json_safe(3.14) == 3.14


def test_gdf_to_geojson_features_produces_valid_json():
    from pyrosm import OSM, get_data
    osm = OSM(get_data("test_pbf"))
    roads = osm.get_network(network_type="driving")

    features = fetch_country.gdf_to_geojson_features(roads)
    assert len(features) > 0

    # The real point of this test: the whole thing must round-trip
    # through actual json.dumps/json.loads without error or literal
    # NaN, because that's exactly what breaks in a browser.
    encoded = json.dumps({"type": "FeatureCollection", "features": features})
    assert "NaN" not in encoded
    decoded = json.loads(encoded)
    assert decoded["features"][0]["geometry"]["type"] in {"LineString", "MultiLineString"}


def test_full_pipeline_end_to_end(tmp_path):
    from pyrosm import get_data
    pbf_path = get_data("test_pbf")

    fetch_country.process_area(
        pbf_path, tmp_path, state_admin_level="4", district_admin_level="6",
    )

    expected_files = ["roads.geojson", "states.geojson", "districts.geojson", "forest.geojson", "water.geojson"]
    for name in expected_files:
        path = tmp_path / name
        assert path.exists(), f"{name} was not created"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["type"] == "FeatureCollection"

    roads_data = json.loads((tmp_path / "roads.geojson").read_text(encoding="utf-8"))
    assert len(roads_data["features"]) > 0, "the test area should have at least some real roads"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
