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

- **Real map data, one area at a time — a small custom region, a whole
  state, or a whole country**, using two different tools sized for the
  job: `fetch_region.py` for a city-sized custom bounding box, and
  `fetch_country.py` for a whole state or country at once, using real
  pre-built OpenStreetMap extracts (roads, admin boundaries, forest,
  water). I run either one once with real internet, and the saved
  files work offline forever after that. This is the same way real
  offline-map apps (OsmAnd, Organic Maps) reach global coverage — one
  downloaded area at a time, not one impossible giant file.
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
- Offline vector map rendering — roads, admin boundaries, forest, and water — from data fetched once, at either a custom small area or a whole state/country
- Extensible hazard/police/safe-zone layer with a built-in disclaimer for anything unverified
- Automatically zooms to show whatever data you actually have — your real GPS position if there's a fix, otherwise the hazard points that exist, instead of leaving them invisible on a whole-world view
- A tiny local web server — Python's own `http.server`, no Flask, no Django — that never lets your browser cache a stale copy of the UI
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

## If you update the code but the browser still shows the old version

This server now sends explicit no-cache headers, so this shouldn't
happen going forward — but if it ever does again:

1. Stop any old `python3 main.py` process completely (close that
   terminal, or `Ctrl+C` it) before starting a new one.
2. Hard-refresh the page: `Ctrl+Shift+R` (Windows/Linux) or
   `Cmd+Shift+R` (Mac), or just open it in a fresh incognito/private
   window.
3. Make sure you actually replaced the old project folder with the new
   files, rather than running an old copy from a different path.

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

This talks to the free public Overpass API, which is meant for small,
custom areas like this. For a whole state or country at once, see the
next section — Overpass will time out or reject a request that large,
and that's a real limit of a shared free service, not something to push
past.

## Getting a whole state or country

For anything bigger than a city — a whole state, a whole country — the
right tool isn't Overpass, it's a pre-built extract processed with
[pyrosm](https://pyrosm.readthedocs.io) (the same free Geofabrik/BBBike
data that real offline-map apps like OsmAnd use):

```bash
pip install pyrosm
python3 fetch_country.py --list                    # see what's available
python3 fetch_country.py --state "West Bengal"       # start smaller — recommended
python3 fetch_country.py --country India              # the whole country
```

This produces five separate layers under `data/countries/<name>/`:
`roads.geojson`, `states.geojson`, `districts.geojson`,
`forest.geojson` (jungle/wooded areas), and `water.geojson` (lakes,
ponds, rivers). TerraLocator picks up anything it finds there
automatically — no config needed, just restart the app.

**Read this before running it on a whole country:** these extracts are
large (a full country can be several hundred MB to download) and
processing one needs real free RAM. I do this on a PC, not on my phone
— the *output* GeoJSON layers are much smaller than the raw download,
and those are what I actually copy over to my phone afterwards. That's
also why I start with a state, not the whole country: West Bengal alone
is enough to test with, and it's a fraction of the size.

One more honest note: OSM's admin_level tagging for "state" vs.
"district" genuinely varies by country and even by region within a
country, because it's drawn by different volunteer communities. The
defaults here (4 for states, 6 for districts) are common, but if your
districts.geojson comes back looking wrong, check what you actually got
and adjust:
```bash
python3 fetch_country.py --state "West Bengal" --district-admin-level 5
```

There's no year-specific step here, either — Geofabrik's extracts are
refreshed regularly at the source, so running this whenever I want a
current map *is* how I get one.

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
├── fetch_region.py            # small custom area, via Overpass API
├── fetch_country.py           # whole state/country, via pyrosm + Geofabrik extracts
├── terralocator/
│   ├── geomath.py             # distance/bearing math -- the entire "navigation" feature
│   ├── location.py            # real GPS via Termux:API, manual fallback for PC dev
│   ├── hazards.py             # the extensible, safety-conscious POI/hazard layer
│   ├── server.py              # stdlib http.server: serves the UI + JSON API, never caches
│   └── static/                # the Leaflet-based map page (Leaflet vendored locally)
├── data/regions/                # fetched small-area regions + the labeled demo hazard set
└── data/countries/               # fetched whole state/country layers (gitignored, large)
```

No frontend build step, no bundler, no framework beyond one vendored JS
library. If you can read Python and a bit of vanilla JavaScript, you
can read all of it.

## Data sources

- Roads, places, and POIs for small custom areas come from
  [OpenStreetMap](https://www.openstreetmap.org) via the Overpass API
  (`fetch_region.py`)
- Whole state/country layers come from the same OpenStreetMap data via
  pre-built [Geofabrik](https://download.geofabrik.de)/BBBike extracts,
  processed with [pyrosm](https://pyrosm.readthedocs.io)
  (`fetch_country.py`) — the same free data real offline-map apps use
- The always-visible world outline (`terralocator/static/world_countries.geojson`)
  is [Natural Earth](https://www.naturalearthdata.com) 1:110m country
  boundaries — public domain, no attribution legally required, credited
  here anyway because it's the right thing to do

## Testing

```bash
pip install pytest
python -m pytest tests/ -v
```

37 tests: geometry math checked against a real known distance
(Delhi–Mumbai), the hazard layer's save/reload/query logic, GPS-JSON
parsing against saved sample Termux output (including messy output with
stray whitespace or extra text around it), the Overpass→GeoJSON
converter against a synthetic OSM response, an end-to-end test that
starts the real server and hits every API route with real HTTP
requests over a real socket (including confirming nothing is ever
cached), and the full country-extraction pipeline run against pyrosm's
own bundled real sample data — the tests that caught a genuine bug
during development (numpy integer types and `NaN` values silently
produce invalid JSON that a browser's `JSON.parse()` rejects; this is
now handled explicitly, with a test locking it in). Country-extraction
tests are skipped automatically if `pyrosm` isn't installed, since it's
a heavier optional dependency only needed for that one feature.

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
