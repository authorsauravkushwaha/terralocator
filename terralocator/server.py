"""
Local web server for TerraLocator.

Serves a small Leaflet-based map page and a handful of JSON API
endpoints, entirely from Python's standard library (http.server) — no
Flask, no Django, nothing to pip install. Runs identically whether it's
under Termux on your phone (open http://127.0.0.1:8765 in the phone's
own browser — no data connection needed, it's talking to itself) or on
a PC.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import location as location_module
from .geomath import Coordinate, navigate
from .hazards import HazardLayer, HazardPoint

STATIC_DIR = Path(__file__).resolve().parent / "static"
REGIONS_DIR = Path(__file__).resolve().parent.parent / "data" / "regions"
COUNTRIES_DIR = Path(__file__).resolve().parent.parent / "data" / "countries"
DEFAULT_HAZARDS_PATH = Path.home() / ".terralocator" / "hazards.geojson"
DEMO_HAZARDS_PATH = REGIONS_DIR / "demo.hazards.geojson"

COUNTRY_LAYERS = {"roads", "states", "districts", "forest", "water"}

CONTENT_TYPES = {
    ".html": "text/html", ".js": "application/javascript",
    ".css": "text/css", ".json": "application/json", ".png": "image/png",
}


def _list_region_files():
    if not REGIONS_DIR.exists():
        return []
    return sorted(p.name[: -len(".osm.geojson")] for p in REGIONS_DIR.glob("*.osm.geojson"))


def _list_country_folders():
    if not COUNTRIES_DIR.exists():
        return []
    return sorted(p.name for p in COUNTRIES_DIR.iterdir() if p.is_dir())


def make_handler(hazard_layer: HazardLayer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # keep the terminal quiet during normal use

        def _send_json(self, payload, status=200):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path):
            if not path.exists():
                self.send_error(404)
                return
            content_type = CONTENT_TYPES.get(path.suffix, "application/octet-stream")
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            # This app is actively being developed/updated locally --
            # a browser silently serving a stale cached copy of the UI
            # after a real fix has already landed is exactly the kind
            # of confusing "still broken" report that wastes everyone's
            # time. Never cache anything from this local dev server.
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            route, params = parsed.path, parse_qs(parsed.query)

            if route in ("/", "/index.html"):
                self._send_file(STATIC_DIR / "index.html")
            elif route.startswith("/leaflet/"):
                self._send_file(STATIC_DIR / route.lstrip("/"))
            elif route == "/map.js":
                self._send_file(STATIC_DIR / "map.js")
            elif route == "/world_countries.geojson":
                self._send_file(STATIC_DIR / "world_countries.geojson")
            elif route == "/api/location":
                fix = location_module.get_location()
                self._send_json(fix.to_dict() if fix else {"error": "no_fix"}, 200 if fix else 503)
            elif route == "/api/heading":
                self._send_json({"heading_deg": location_module.get_heading_deg()})
            elif route == "/api/hazards":
                self._send_json({
                    "type": "FeatureCollection",
                    "features": [p.to_feature() for p in hazard_layer.points],
                })
            elif route == "/api/regions":
                self._send_json({"regions": _list_region_files()})
            elif route == "/api/region":
                name = params.get("name", [None])[0]
                path = REGIONS_DIR / f"{name}.osm.geojson" if name else None
                if not name or not path.exists():
                    self._send_json({"error": "not_found"}, 404)
                    return
                self._send_json(json.loads(path.read_text(encoding="utf-8")))
            elif route == "/api/countries":
                self._send_json({"countries": _list_country_folders(), "layers": sorted(COUNTRY_LAYERS)})
            elif route == "/api/country":
                name = params.get("name", [None])[0]
                layer = params.get("layer", [None])[0]
                if not name or layer not in COUNTRY_LAYERS:
                    self._send_json({"error": f"name required, layer must be one of {sorted(COUNTRY_LAYERS)}"}, 400)
                    return
                path = COUNTRIES_DIR / name / f"{layer}.geojson"
                if not path.exists():
                    self._send_json({"error": "not_found"}, 404)
                    return
                self._send_json(json.loads(path.read_text(encoding="utf-8")))
            elif route == "/api/navigate":
                try:
                    lat = float(params["lat"][0])
                    lon = float(params["lon"][0])
                except (KeyError, ValueError, IndexError):
                    self._send_json({"error": "lat and lon query params required"}, 400)
                    return
                fix = location_module.get_location()
                if fix is None:
                    self._send_json({"error": "no_fix"}, 503)
                    return
                info = navigate(fix.coordinate(), Coordinate(lat=lat, lon=lon))
                self._send_json({
                    "distance_m": info.distance_m, "bearing_deg": info.bearing_deg,
                    "compass": info.compass, "summary": info.summary(),
                })
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != "/api/hazards":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
                point = HazardPoint.new(
                    type=body["type"], lat=float(body["lat"]), lon=float(body["lon"]),
                    title=body["title"], description=body.get("description", ""),
                    source=body.get("source", "user"), verified=False,
                )
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, 400)
                return
            hazard_layer.add(point)
            self._send_json(point.to_feature(), 201)

    return Handler


def run_server(host: str = "127.0.0.1", port: int = 8765, hazards_path: Path = None):
    hazards_path = hazards_path or (
        DEMO_HAZARDS_PATH if DEMO_HAZARDS_PATH.exists() and not DEFAULT_HAZARDS_PATH.exists()
        else DEFAULT_HAZARDS_PATH
    )
    layer = HazardLayer(hazards_path)
    handler_cls = make_handler(layer)
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"TerraLocator running at http://{host}:{port}")
    print("Open that address in your browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
