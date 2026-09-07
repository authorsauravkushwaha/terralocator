#!/usr/bin/env python3
"""
fetch_region.py — download REAL OpenStreetMap data for a bounding box
using the free public Overpass API, and save it as GeoJSON that
TerraLocator's map can render completely offline afterwards.

This needs internet ONCE, while you run it. After that, the saved file
works with zero network, forever — that's the whole offline-first
design. This scales to the entire planet exactly the way real offline
map apps (OsmAnd, Organic Maps) do it: you run this once per region you
care about, and your local `data/regions/` folder grows to cover as
much of the world as you actually need.

Usage:
    python3 fetch_region.py --name kolaghat --bbox 22.35,87.75,22.55,87.95

--bbox is "south,west,north,east" in decimal degrees. Get a bounding box
for anywhere on Earth at https://boundingbox.klokantech.com/ (pick the
"CSV" format, then reorder to south,west,north,east).

Pulls roads, a handful of useful POI categories (police, hospital,
drinking water, fuel), and named places, within the box.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REGIONS_DIR = Path(__file__).resolve().parent / "data" / "regions"

QUERY_TEMPLATE = """
[out:json][timeout:60];
(
  way["highway"]({bbox});
  node["amenity"~"^(police|hospital|drinking_water|fuel)$"]({bbox});
  node["place"~"^(city|town|village|hamlet)$"]({bbox});
);
out body;
>;
out skel qt;
"""


def build_query(bbox: str) -> str:
    parts = [p.strip() for p in bbox.split(",")]
    if len(parts) != 4:
        raise ValueError("--bbox must be 4 comma-separated numbers: south,west,north,east")
    for p in parts:
        float(p)  # raises ValueError if not numeric
    return QUERY_TEMPLATE.format(bbox=bbox)


def fetch_overpass(query: str, timeout_s: int = 90) -> dict:
    req = urllib.request.Request(OVERPASS_URL, data=query.encode("utf-8"), method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def overpass_to_geojson(osm_json: dict) -> dict:
    """Converts Overpass's flat node/way JSON into a GeoJSON
    FeatureCollection: points for tagged nodes, lines for roads. This is
    the entire "rendering pipeline" — no tile server, no map-rendering
    library needed, because Leaflet can draw GeoJSON lines and points
    directly."""
    nodes = {el["id"]: el for el in osm_json.get("elements", []) if el["type"] == "node"}
    features = []

    for el in osm_json.get("elements", []):
        if el["type"] == "node" and el.get("tags"):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]},
                "properties": el["tags"],
            })
        elif el["type"] == "way" and el.get("tags", {}).get("highway"):
            coords = [
                [nodes[nid]["lon"], nodes[nid]["lat"]]
                for nid in el.get("nodes", []) if nid in nodes
            ]
            if len(coords) >= 2:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": el["tags"],
                })

    return {"type": "FeatureCollection", "features": features}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--name", required=True, help="Short region name; used as the output filename")
    parser.add_argument("--bbox", required=True, help="south,west,north,east in decimal degrees")
    args = parser.parse_args(argv)

    try:
        query = build_query(args.bbox)
    except ValueError as exc:
        print(f"Invalid --bbox: {exc}", file=sys.stderr)
        return 1

    print(f"Querying Overpass API for bbox {args.bbox} ... (needs internet, once)")
    try:
        osm_json = fetch_overpass(query)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Could not reach Overpass API: {exc}", file=sys.stderr)
        print("Check your internet connection and try again.", file=sys.stderr)
        return 1

    geojson = overpass_to_geojson(osm_json)
    REGIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REGIONS_DIR / f"{args.name}.osm.geojson"
    out_path.write_text(json.dumps(geojson), encoding="utf-8")
    print(f"Saved {len(geojson['features'])} features to {out_path}")
    print("This file now works completely offline. Restart TerraLocator to see it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
