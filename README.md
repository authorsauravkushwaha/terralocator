# TerraLocator

I built this to answer exactly one question, with zero network:
**"where am I, right now?"**

No pip installs beyond one optional dev tool (`pytest`), no map server,
no account, no routing. Just your real position, on real map data,
whether or not you have signal.

## The app takes your location automatically

Once it's running, TerraLocator pulls your phone's real GPS position by
itself — you never type coordinates in by hand. It grabs a fix the
moment you start it (you'll see it printed right in the terminal), and
the page in your browser keeps refreshing your position every few
seconds on its own after that. There's a "Refresh fix" button too, but
you don't need to press it for the app to work — it's already doing it
for you in the background.

## Why this exists, and what it actually is (please read this part)

I wanted an app that still tells you where you are even somewhere like
deep jungle or open water, where there's no signal at all. It does
**not** give you turn-by-turn directions. In a place with no road
network, that's not a missing feature — it's how real wilderness and
marine navigation has always worked: you know where you are, you know
where you want to go, and you get a straight-line distance and compass
bearing. A map plus a compass.

### The one thing that makes "no network" actually possible

GPS satellites broadcast your position to any GPS chip directly. Your
phone's GPS does **not** need mobile data, WiFi, or cell signal to get a
fix — that's the entire design of satellite positioning. What actually
breaks without signal is maps, search, and directions, because those
need a server. Knowing *where you are* was never the part that needed
the internet — this app just stops pretending it does. (Two honest
physical limits are still real, though: a first fix is slower without a
data connection to speed it up, and thick jungle canopy or canyon walls
can weaken the signal, because GPS still needs a clear view of the sky.
Bluetooth doesn't help with any of this, for what it's worth — it's only
good for very short-range things like indoor beacons.)

### Why it isn't "the whole Earth, every street, every hazard" on day one

I'm not going to pretend I can hand-build a complete, worldwide,
house-number-accurate, hazard-annotated map by myself — that's what
OpenStreetMap's global volunteer community has built over 20+ years, not
a one-person project. And I'm not going to invent "danger zone" data to
fill the gaps, either: if someone trusted a made-up hazard marker in an
actual remote area, that's how people get hurt. **This app will never
ship invented safety data.**

What it does instead, and what actually can grow to cover the whole
planet over time:

- **Real map data, one region at a time.** `fetch_region.py` pulls real
  OpenStreetMap roads, place names, and key POIs (police, hospital,
  water, fuel) for any bounding box on Earth, using the free public
  Overpass API. I run it once per region with real internet, and the
  saved file works offline forever after that. This is the same way
  real offline-map apps (OsmAnd, Organic Maps) reach global coverage —
  one downloaded region at a time, not one giant file.
- **An open, extensible hazard/safe-zone layer**, stored as plain
  GeoJSON (a real GIS standard — readable in QGIS or a text editor). It
  ships with **zero real safety claims**, only clearly labeled demo
  points that show the schema. Every point has a `verified` flag and a
  `source`. If this is ever going to genuinely help people long-term,
  it's because the format stays open enough for people to responsibly
  add to it — not because I guessed at what's dangerous where.

## Features

- Real GPS position via Termux:API on Android — automatic, zero network required
- A real world map outline (public-domain Natural Earth country boundaries, bundled — so the map is never a blank void, even before any GPS fix or region data exists)
- Straight-line distance + compass bearing to a tapped destination (no routing)
- Offline vector map rendering (roads + named places + POIs) from data fetched once
- Extensible hazard/police/safe-zone layer with a built-in disclaimer for anything unverified
- Automatically zooms to show whatever data you actually have — your real GPS position if there's a fix, otherwise the hazard points that exist, instead of leaving them invisible on a whole-world view
- A tiny local web server — Python's own `http.server`, no Flask, no Django
- Leaflet.js is vendored locally in this repo — the map UI itself needs zero CDN/network at runtime
- Runs the same way on my Android phone (via Termux) or a plain PC

## Setting it up on my phone

1. Install **Termux** and **Termux:API** — both from
   [F-Droid](https://f-droid.org). This matters: mixing an F-Droid
   Termux with a Play Store Termux:API (or the other way around) is the
   single most common reason the location piece silently fails.
2. Inside Termux:
   ```bash
   pkg install python termux-api git
   termux-setup-storage
   ```
3. The first time it asks, grant the location permission.

On a PC, all I need is Python 3.8+. The app still runs and the map UI
still works without a GPS chip — it just waits for a manual coordinate
instead (see below).

## Running it

```bash
git clone https://github.com/authorsauravkushwaha/terralocator.git
cd terralocator
python3 main.py
```

It prints something like this right away — this is the automatic GPS
fetch happening, before I've even opened a browser:

```
TerraLocator -- checking your phone's GPS...
  Got a real GPS fix: 22.43270, 87.86970 (+/-8 m)
  Compass heading: 42 degrees
```

Then I open the printed address (`http://127.0.0.1:8765`) in a browser
on the same phone. It's talking to itself on localhost — no data
connection is used by the app itself.

On a PC with no GPS chip, I set a starting point for testing like this:

```python
from terralocator.location import set_manual_location
set_manual_location(lat=22.4327, lon=87.8697)
```

## If the GPS part doesn't seem to work

The startup message above will tell you what's missing, but the
checklist is:

1. **Termux and Termux:API from the same source** (both F-Droid).
2. **Run `termux-location` by itself first**, straight in Termux,
   before blaming the app:
   ```bash
   termux-location -p gps -r once
   ```
   If that alone doesn't print coordinates, the problem is Termux/Android
   permissions, not this code — and Android may be showing a location
   permission prompt that's easy to miss the first time.
3. Make sure `pkg install termux-api` was actually run (it's a separate
   package from the Termux:API *app*).
4. Indoors or under heavy cover, GPS can take a while, or fail outright
   — that's the phone's hardware, not something software can fix.

## Downloading real map data for a region

```bash
python3 fetch_region.py --name kolaghat --bbox 22.35,87.75,22.55,87.95
```

`--bbox` is `south,west,north,east` in decimal degrees — I get one for
anywhere on Earth at
[boundingbox.klokantech.com](https://boundingbox.klokantech.com/). This
needs internet once, while it runs. I can run it again for another
town, another state, another country — coverage grows however far I
actually go.

## Adding real hazard data

I edit (or replace) `~/.terralocator/hazards.geojson`, or add points
through the map UI, which always saves them as `"verified": false`.
Promoting a point to `verified: true` is something I do myself, on
purpose, after actually checking it locally — the app will never do
that automatically, and neither should anyone else without real,
sourced confidence.

## How it's built

```
terralocator/
├── main.py                    # entry point: python3 main.py
├── fetch_region.py            # I run this with real internet, once per region
├── terralocator/
│   ├── geomath.py             # distance/bearing math -- the entire "navigation" feature
│   ├── location.py            # real GPS via Termux:API, manual fallback for PC dev
│   ├── hazards.py             # the extensible, safety-conscious POI/hazard layer
│   ├── server.py              # stdlib http.server: serves the UI + JSON API
│   └── static/                # the Leaflet-based map page (Leaflet vendored locally)
└── data/regions/               # fetched regions + the labeled demo hazard set live here
```

No frontend build step, no bundler, no framework beyond one vendored JS
library. If you can read Python and a bit of vanilla JavaScript, you
can read all of it.

## Data sources

- Roads, places, and POIs come from [OpenStreetMap](https://www.openstreetmap.org)
  via the Overpass API, fetched by `fetch_region.py`
- The always-visible world outline (`terralocator/static/world_countries.geojson`)
  is [Natural Earth](https://www.naturalearthdata.com) 1:110m country
  boundaries — public domain, no attribution legally required, credited
  here anyway because it's the right thing to do

## Testing

```bash
pip install pytest
python -m pytest tests/ -v
```

28 tests: geometry math checked against a real known distance
(Delhi–Mumbai), the hazard layer's save/reload/query logic, GPS-JSON
parsing against saved sample Termux output (including messy output with
stray whitespace or extra text around it), the Overpass→GeoJSON
converter against a synthetic OSM response, and an end-to-end test that
starts the real server and hits every API route with real HTTP requests
over a real socket.

## Roadmap

- Dead-reckoning (accelerometer + compass) to keep estimating position
  through short GPS dropouts under heavy canopy
- A packaged Termux widget/shortcut so it launches with one tap
- Reviewed, community-contributed regional hazard packs — the actual
  long-term path to wide, trustworthy coverage

## License

MIT — see [LICENSE](LICENSE).

## Author

**Saurav Kushwaha** — [github.com/authorsauravkushwaha](https://github.com/authorsauravkushwaha)
