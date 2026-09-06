# TerraLocator

An offline-first "know where you are" map. No pip installs beyond one
optional dev tool (`pytest`), no map server, no account, no routing.

## What this actually is (read this first)

This app answers exactly one question: **"where am I, right now, with
zero network?"** — and then shows you that position on real map data
you downloaded once, plus a straight-line distance and compass bearing
to anywhere you tap. It does **not** do turn-by-turn directions. In a
place with no road network — deep jungle, open water, desert — that's
not a missing feature. It's how real wilderness and marine navigation
has always worked: you know where you are, you know where you want to
be, you walk the bearing.

### The one thing that makes "no network" possible: GPS was never a network technology

GPS satellites broadcast your position to any GPS chip directly. Your
phone's GPS does **not** need mobile data, WiFi, or cell signal to get a
fix — that's the entire design of satellite positioning. What actually
fails without signal is *maps, search, and directions* (because those
need a server) — not *knowing where you are*. That's the gap this app
fills. (Two honest physical limits remain: a first fix is slower without
a data connection to speed it up, and thick jungle canopy or canyon
walls can weaken the signal, because GPS still needs line-of-sight to
the sky. Bluetooth, for what it's worth, doesn't help with any of this —
it's only useful for very short-range things like indoor beacons.)

### Why it isn't "the whole Earth, every street, every hazard" on day one — and how it actually gets there

A complete, worldwide, house-number-accurate, hazard-annotated map is
not a one-person, one-app achievement — it's what OpenStreetMap's global
volunteer community has built over 20+ years. Trying to hand-author that
alone doesn't scale, and inventing "danger zone" data to fill the gaps
would be actively dangerous: if someone trusted a fabricated hazard
marker in an actual remote area, that's how people get hurt. **This app
never ships invented safety data.**

What it does instead, and what genuinely does scale to the whole planet:

- **Real map data, one region at a time.** `fetch_region.py` pulls real
  OpenStreetMap roads, place names, and key POIs (police, hospital,
  water, fuel) for any bounding box on Earth, using the free public
  Overpass API. Run it once per region with real internet; the saved
  file then works offline forever. This is exactly how real offline-map
  apps (OsmAnd, Organic Maps) scale to global coverage — one downloaded
  region at a time, not one giant file.
- **An open, extensible hazard/safe-zone layer**, stored as plain
  GeoJSON (a real GIS standard, readable in QGIS or any text editor).
  It ships with **zero real safety claims** — only clearly labeled demo
  points showing the schema. Every point has a `verified` flag and a
  `source`. This is the actual path to "helps people for a long time":
  an open format a community can responsibly grow, not a static
  database one person filled in from guesses.

## Features

- Real GPS position via Termux:API on Android — zero network required
- Straight-line distance + compass bearing to a tapped destination (no routing)
- Offline vector map rendering (roads + named places + POIs) from data you fetch once
- Extensible hazard/police/safe-zone layer with a hard-coded safety disclaimer for anything unverified
- A tiny local web server (Python's own `http.server` — no Flask, no Django)
- Leaflet.js is **vendored locally** in this repo — the map UI itself needs zero CDN/network at runtime
- Works identically on your Android phone (via Termux) or a plain PC

## Requirements

**On your Android phone:**
1. Install **Termux** and **Termux:API** — both from
   [F-Droid](https://f-droid.org) (the Play Store builds are outdated
   and can't install add-on packages properly)
2. Inside Termux:
   ```bash
   pkg install python termux-api git
   termux-setup-storage
   ```
3. Grant location permission the first time it's requested

**On a PC:** just Python 3.8+. Nothing else to install to run the app
(the map still works — it falls back to a manual coordinate you set,
so you can test the whole UI without a GPS chip).

## Run it

```bash
git clone https://github.com/authorsauravkushwaha/terralocator.git
cd terralocator
python3 main.py
```

Then open the printed address (`http://127.0.0.1:8765`) in a browser —
on your phone, that's Termux's own browser access or Chrome/Firefox on
the same device. It's talking to itself on localhost; no data connection
is used by the app itself.

On a PC with no GPS chip, set a starting point for testing:

```python
from terralocator.location import set_manual_location
set_manual_location(lat=22.4327, lon=87.8697)
```

## Downloading real map data for a region

```bash
python3 fetch_region.py --name kolaghat --bbox 22.35,87.75,22.55,87.95
```

`--bbox` is `south,west,north,east` in decimal degrees — get one for
anywhere on Earth at
[boundingbox.klokantech.com](https://boundingbox.klokantech.com/). This
needs internet **once**, while it runs. Run it again for another town,
another country, another continent — coverage grows however far you
actually go, exactly like a real offline-map app builds up its cache.

## Adding real hazard data

Edit (or replace) `~/.terralocator/hazards.geojson` — or add points
through the map UI, which always saves them with `"verified": false`.
**Promoting a point to `verified: true` is a deliberate, manual edit you
make yourself, on purpose, after actually checking it locally.** The
app will never do that automatically, and neither should a future
contributor without real, sourced confidence.

## How it's built (for anyone reading the code)

```
terralocator/
├── main.py                    # entry point: python3 main.py
├── fetch_region.py            # you run this with real internet, once per region
├── terralocator/
│   ├── geomath.py             # distance/bearing math — the entire "navigation" feature
│   ├── location.py            # real GPS via Termux:API, manual fallback for PC dev
│   ├── hazards.py             # the extensible, safety-conscious POI/hazard layer
│   ├── server.py              # stdlib http.server: serves the UI + JSON API
│   └── static/                # the Leaflet-based map page (Leaflet vendored locally)
└── data/regions/               # fetched regions + the labeled demo hazard set live here
```

No frontend build step, no bundler, no framework beyond one vendored
JS library. If you can read Python and a bit of vanilla JavaScript, you
can read this entire app.

## Testing

```bash
pip install pytest
python -m pytest tests/ -v
```

26 tests: geometry math checked against a real known distance
(Delhi–Mumbai), the hazard layer's save/reload/query logic, GPS-JSON
parsing against saved sample Termux output, the Overpass→GeoJSON
converter against a synthetic OSM response, and an end-to-end test that
starts the *real* server and hits every API route with real HTTP
requests over a real socket.

## Roadmap

- Dead-reckoning (accelerometer + compass) to keep estimating position
  through short GPS dropouts under heavy canopy
- A packaged Termux widget/shortcut so it launches with one tap
- Community-contributed regional hazard packs, reviewed before merge —
  the actual long-term path to wide, trustworthy coverage

## License

MIT — see [LICENSE](LICENSE).

## Author

**Saurav Kushwaha** — [github.com/authorsauravkushwaha](https://github.com/authorsauravkushwaha)
