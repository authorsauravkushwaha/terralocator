#!/usr/bin/env python3
"""
fetch_country.py -- download and process REAL, whole-country (or
whole-state) OpenStreetMap data, producing separate GeoJSON layers:
roads, state-level boundaries, district-level boundaries, forest/jungle,
and water (lakes + rivers).

WHY THIS SCRIPT EXISTS INSTEAD OF fetch_region.py FOR THIS SCALE
------------------------------------------------------------------
fetch_region.py talks to the free public Overpass API, which is meant
for small, custom bounding boxes. Asking it for an entire country will
time out or get rejected -- and hammering a shared free service with
country-sized requests is inconsiderate of everyone else who relies on
it. For country/state-scale data, the right tool is a pre-built extract:
this script uses pyrosm (`pip install pyrosm`), which downloads the same
free Geofabrik/BBBike extracts that real offline-map apps like OsmAnd
use, and processes them into GeoJSON layers Leaflet can draw directly.

These extracts are refreshed regularly at the source, so re-running this
whenever you want an up-to-date map is exactly how you get "the current
map" -- there's no hardcoded year to chase; freshness just depends on
when you last ran this.

A REAL, HONEST WARNING ABOUT SIZE
------------------------------------------------------------------
Country-scale files are LARGE -- a full country can be several hundred
MB to download, and processing it needs real free RAM (more than a
typical phone comfortably has to spare). Run this on a PC, not on your
phone via Termux. The GeoJSON LAYERS this script produces are much
smaller than the raw download -- those are what you copy to your phone
afterwards, into TerraLocator's data/countries/<name>/ folder.

Usage
------------------------------------------------------------------
    python3 fetch_country.py --list                      # see what's available
    python3 fetch_country.py --state "West Bengal"        # a state (smaller, start here)
    python3 fetch_country.py --country India               # a whole country (large)
    python3 fetch_country.py --pbf ./already-downloaded.osm.pbf --name mycity

Admin levels for states/districts vary by country's own OSM mapping
conventions -- if the boundaries you get look wrong (e.g. "districts"
showing up as huge areas, or empty), pass different levels:
    python3 fetch_country.py --state "West Bengal" --district-admin-level 5
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

COUNTRIES_DIR = Path(__file__).resolve().parent / "data" / "countries"

# Common defaults (India, and many countries, use these) -- not
# universal. OSM mapping conventions genuinely differ by country and
# even by region within a country, because they're drawn by different
# volunteer mapping communities.
DEFAULT_STATE_ADMIN_LEVEL = "4"
DEFAULT_DISTRICT_ADMIN_LEVEL = "6"


def require_pyrosm():
    try:
        import pyrosm  # noqa: F401
    except ImportError:
        print("This script needs pyrosm and its dependencies:", file=sys.stderr)
        print("    pip install pyrosm", file=sys.stderr)
        print("(pyrosm pulls in geopandas/shapely automatically.)", file=sys.stderr)
        sys.exit(1)


def json_safe(value):
    """Convert a pandas/numpy scalar into something json.dumps can
    actually handle. This is not optional cleanup: numpy's int64 /
    uint32 / int32 / bool_ types raise TypeError from json.dumps, and a
    NaN float silently produces literal `NaN` in the output file --
    which is not valid JSON, and a browser's JSON.parse() will reject
    the entire file over one bad field if this isn't handled.
    """
    if value is None:
        return None
    if hasattr(value, "item"):  # numpy scalar -> native Python type
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def gdf_to_geojson_features(gdf) -> list:
    """Convert a GeoDataFrame into plain GeoJSON feature dicts."""
    if gdf is None or len(gdf) == 0:
        return []
    features = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        props = {}
        for col in gdf.columns:
            if col == "geometry":
                continue
            safe = json_safe(row[col])
            if safe is None:
                continue
            try:
                json.dumps(safe)
                props[col] = safe
            except (TypeError, ValueError):
                props[col] = str(safe)
        try:
            geometry = json.loads(json.dumps(dict(geom.__geo_interface__)))
        except (TypeError, ValueError):
            continue  # skip a feature whose geometry genuinely can't convert, don't crash the whole export
        features.append({"type": "Feature", "geometry": geometry, "properties": props})
    return features


def save_layer(features: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    collection = json.dumps({"type": "FeatureCollection", "features": features})
    json.loads(collection)  # sanity check: must be valid JSON before it ever reaches a browser
    path.write_text(collection, encoding="utf-8")
    print(f"  Saved {len(features)} features -> {path}")


def process_area(pbf_path: str, out_dir: Path, state_admin_level: str, district_admin_level: str) -> None:
    from pyrosm import OSM

    print(f"Loading {pbf_path} ... (this can take a while for a large area)")
    osm = OSM(pbf_path)

    print("Extracting roads...")
    save_layer(gdf_to_geojson_features(osm.get_network(network_type="driving")), out_dir / "roads.geojson")

    print(f"Extracting state-level boundaries (admin_level={state_admin_level})...")
    states = osm.get_boundaries(boundary_type="administrative", custom_filter={"admin_level": [state_admin_level]})
    save_layer(gdf_to_geojson_features(states), out_dir / "states.geojson")

    print(f"Extracting district-level boundaries (admin_level={district_admin_level})...")
    districts = osm.get_boundaries(boundary_type="administrative", custom_filter={"admin_level": [district_admin_level]})
    save_layer(gdf_to_geojson_features(districts), out_dir / "districts.geojson")

    print("Extracting forest / jungle areas...")
    forest = osm.get_landuse(custom_filter={"landuse": ["forest"]})
    wood = osm.get_natural(custom_filter={"natural": ["wood"]})
    save_layer(gdf_to_geojson_features(forest) + gdf_to_geojson_features(wood), out_dir / "forest.geojson")

    print("Extracting water (lakes, ponds, rivers)...")
    water_areas = osm.get_natural(custom_filter={"natural": ["water"]})
    rivers = osm.get_data_by_custom_criteria(
        custom_filter={"waterway": ["river", "stream", "canal"]}, osm_keys_to_keep="waterway",
    )
    save_layer(gdf_to_geojson_features(water_areas) + gdf_to_geojson_features(rivers), out_dir / "water.geojson")

    print(f"\nDone. All layers saved under {out_dir}")
    print("These files now work completely offline. Restart TerraLocator to see them.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--country", help="Country name matching a pyrosm/Geofabrik dataset, e.g. India")
    parser.add_argument("--state", help="A specific state/sub-region instead of the whole country, where available")
    parser.add_argument("--pbf", help="Path to an already-downloaded .osm.pbf file, instead of --country/--state")
    parser.add_argument("--name", help="Output folder name when using --pbf (required with --pbf)")
    parser.add_argument("--state-admin-level", default=DEFAULT_STATE_ADMIN_LEVEL)
    parser.add_argument("--district-admin-level", default=DEFAULT_DISTRICT_ADMIN_LEVEL)
    parser.add_argument("--list", action="store_true", help="List countries/regions pyrosm can download and exit")
    args = parser.parse_args(argv)

    require_pyrosm()

    if args.list:
        from pyrosm.data import sources
        print("Categories:", list(sources.available.keys()))
        print("\nCountries in Asia (India's continent):", sources.asia.available)
        print("\nUse the exact name shown above with --country or --state.")
        return 0

    if args.pbf:
        if not args.name:
            parser.error("--pbf requires --name (used as the output folder name)")
        pbf_path, out_name = args.pbf, args.name
    elif args.state:
        from pyrosm import get_data
        pbf_path, out_name = get_data(args.state), args.state.lower().replace(" ", "_")
    elif args.country:
        from pyrosm import get_data
        pbf_path, out_name = get_data(args.country), args.country.lower().replace(" ", "_")
    else:
        parser.error("Provide --country, --state, or --pbf (or --list to see options)")
        return 1

    process_area(pbf_path, COUNTRIES_DIR / out_name, args.state_admin_level, args.district_admin_level)
    return 0


if __name__ == "__main__":
    sys.exit(main())
