/* TerraLocator frontend.
 *
 * A light world-outline layer (real public-domain country boundaries
 * from Natural Earth) is always drawn first, so the map is never a
 * pure black void even before any GPS fix or region data exists. On
 * top of that, real vector data (roads/places from fetch_region.py)
 * and your own live position get drawn. That's enough to navigate by,
 * the same way a handheld GPS unit with no map subscription still
 * shows a track and a position dot on a bare grid.
 */

const map = L.map('map', {
  zoomControl: true,
  attributionControl: false,
  center: [20.0, 0.0],
  zoom: 3,
});

let youAreHereMarker = null;
let accuracyCircle = null;
let targetMarker = null;
let hasCenteredOnGps = false;
let hasFitHazardsOnce = false;
let emptyStateDismissed = false;
const worldLayerGroup = L.layerGroup().addTo(map);
const hazardLayerGroup = L.layerGroup().addTo(map);
const regionLayerGroup = L.layerGroup().addTo(map);

const fixStatusEl = document.getElementById('fix-status');
const navPanelEl = document.getElementById('nav-panel');
const disclaimerEl = document.getElementById('disclaimer');
const emptyStateEl = document.getElementById('empty-state');

async function loadWorldOutline() {
  try {
    const res = await fetch('/world_countries.geojson');
    if (!res.ok) return;
    const geojson = await res.json();
    L.geoJSON(geojson, {
      style: { color: '#3a4260', weight: 1, fillColor: '#1c2136', fillOpacity: 1 },
      onEachFeature: (feature, layer) => {
        if (feature.properties && feature.properties.name) {
          layer.bindPopup(feature.properties.name);
        }
      },
    }).addTo(worldLayerGroup);
  } catch (e) {
    // If this fails for any reason, the app still works — it just
    // falls back to a plain dark background instead of an outlined one.
  }
}

function iconFor(type) {
  const colors = { police: '#6ea8ff', danger: '#ff6b6b', safe_zone: '#66d17a', poi: '#ffca28', water: '#4dd0e1', shelter: '#c084fc' };
  const color = colors[type] || '#ffffff';
  return L.divIcon({
    className: '',
    html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #10121a;"></div>`,
    iconSize: [14, 14],
  });
}

async function refreshLocation() {
  try {
    const res = await fetch('/api/location');
    if (!res.ok) {
      fixStatusEl.textContent = 'No GPS fix (Android + Termux:API only — see the note below on a PC)';
      fixStatusEl.className = 'bad';
      showEmptyStateIfNeeded();
      return;
    }
    const fix = await res.json();
    const latlng = [fix.lat, fix.lon];
    emptyStateEl.classList.remove('visible');

    if (!youAreHereMarker) {
      youAreHereMarker = L.circleMarker(latlng, { radius: 8, color: '#3d5afe', fillColor: '#3d5afe', fillOpacity: 1 }).addTo(map);
    } else {
      youAreHereMarker.setLatLng(latlng);
    }

    if (fix.accuracy_m) {
      if (!accuracyCircle) {
        accuracyCircle = L.circle(latlng, { radius: fix.accuracy_m, color: '#3d5afe', weight: 1, fillOpacity: 0.08 }).addTo(map);
      } else {
        accuracyCircle.setLatLng(latlng).setRadius(fix.accuracy_m);
      }
    }

    if (!hasCenteredOnGps) {
      map.setView(latlng, 15);
      hasCenteredOnGps = true;
    }

    const acc = fix.accuracy_m ? ` (±${Math.round(fix.accuracy_m)} m)` : '';
    fixStatusEl.textContent = `${fix.provider.toUpperCase()} fix: ${fix.lat.toFixed(5)}, ${fix.lon.toFixed(5)}${acc}`;
    fixStatusEl.className = 'ok';

    if (targetMarker) updateNavigation(targetMarker.getLatLng());
  } catch (e) {
    fixStatusEl.textContent = 'Location server unreachable';
    fixStatusEl.className = 'bad';
  }
}

function showEmptyStateIfNeeded() {
  if (hasCenteredOnGps || emptyStateDismissed || emptyStateEl.classList.contains('visible')) return;
  emptyStateEl.innerHTML =
    '<strong>No GPS fix yet.</strong> On a phone, this needs Termux + Termux:API with ' +
    'location permission granted. On a plain PC (no GPS chip), this is expected — ' +
    "you're looking at offline demo data only. <br><br>" +
    '<button id="btn-dismiss-empty">Got it</button>';
  emptyStateEl.classList.add('visible');
  document.getElementById('btn-dismiss-empty').addEventListener('click', () => {
    emptyStateEl.classList.remove('visible');
    emptyStateDismissed = true;
  });
}

async function updateNavigation(latlng) {
  try {
    const res = await fetch(`/api/navigate?lat=${latlng.lat}&lon=${latlng.lng}`);
    if (!res.ok) { navPanelEl.classList.remove('visible'); return; }
    const info = await res.json();
    navPanelEl.innerHTML = `<strong>To destination</strong><br>${info.summary}<br>` +
      `<span style="color:#9aa">Straight-line distance and compass bearing — this app never routes you along roads.</span>`;
    navPanelEl.classList.add('visible');
  } catch (e) {
    navPanelEl.classList.remove('visible');
  }
}

async function loadHazards() {
  const res = await fetch('/api/hazards');
  const geojson = await res.json();
  hazardLayerGroup.clearLayers();
  let unverifiedCount = 0;

  for (const feature of geojson.features) {
    const [lon, lat] = feature.geometry.coordinates;
    const props = feature.properties;
    if (!props.verified) unverifiedCount += 1;
    const marker = L.marker([lat, lon], { icon: iconFor(props.type) });
    const verifiedLabel = props.verified
      ? '<span style="color:#66d17a">verified</span>'
      : '<span style="color:#ffb703">NOT independently verified</span>';
    marker.bindPopup(
      `<strong>${escapeHtml(props.title)}</strong><br>` +
      `${escapeHtml(props.description || '')}<br>` +
      `<small>type: ${escapeHtml(props.type)} · source: ${escapeHtml(props.source)} · ${verifiedLabel}</small>`
    );
    marker.addTo(hazardLayerGroup);
  }

  if (unverifiedCount > 0) {
    disclaimerEl.textContent =
      `⚠ ${unverifiedCount} marker(s) on this map are user-added and NOT independently verified. ` +
      `Do not treat them as a guarantee of safety.`;
    disclaimerEl.classList.add('visible');
  } else {
    disclaimerEl.classList.remove('visible');
  }

  // If real GPS hasn't centered the map yet, zoom to whatever hazard
  // points exist instead of leaving them as an invisible speck on a
  // whole-world view. A real GPS fix always takes priority over this
  // the moment it arrives (see refreshLocation).
  if (!hasFitHazardsOnce && !hasCenteredOnGps && hazardLayerGroup.getLayers().length > 0) {
    map.fitBounds(hazardLayerGroup.getBounds(), { maxZoom: 14, padding: [50, 50] });
    hasFitHazardsOnce = true;
  }
}

async function loadRegionData() {
  const res = await fetch('/api/regions');
  const { regions } = await res.json();
  if (!regions || regions.length === 0) return;

  for (const name of regions) {
    const regionRes = await fetch(`/api/region?name=${encodeURIComponent(name)}`);
    if (!regionRes.ok) continue;
    const geojson = await regionRes.json();
    L.geoJSON(geojson, {
      style: { color: '#5a6b8c', weight: 2 },
      pointToLayer: (feature, latlng) => L.circleMarker(latlng, { radius: 4, color: '#8d8fa3', fillOpacity: 0.8 })
        .bindPopup(describeOsmFeature(feature.properties)),
    }).addTo(regionLayerGroup);
  }
}

// Styling per country-scale layer -- distinct enough to read at a
// glance: forest and water get a filled look (they're areas), roads
// are thin lines, state borders are bold and district borders subtle,
// so the administrative hierarchy is visually obvious.
const COUNTRY_LAYER_STYLES = {
  forest: { color: '#2f6b3f', weight: 1, fillColor: '#2f6b3f', fillOpacity: 0.35 },
  water: { color: '#2d6ca8', weight: 1, fillColor: '#2d6ca8', fillOpacity: 0.45 },
  roads: { color: '#8d8fa3', weight: 1 },
  states: { color: '#e0a030', weight: 2.5, fillOpacity: 0 },
  districts: { color: '#6a7a99', weight: 1, dashArray: '4,3', fillOpacity: 0 },
};

async function loadCountryData() {
  const res = await fetch('/api/countries');
  const { countries } = await res.json();
  if (!countries || countries.length === 0) return;

  for (const name of countries) {
    for (const layer of ['forest', 'water', 'districts', 'states', 'roads']) {
      try {
        const layerRes = await fetch(`/api/country?name=${encodeURIComponent(name)}&layer=${layer}`);
        if (!layerRes.ok) continue;
        const geojson = await layerRes.json();
        L.geoJSON(geojson, {
          style: COUNTRY_LAYER_STYLES[layer],
          onEachFeature: (feature, lyr) => {
            const label = feature.properties && (feature.properties.name || feature.properties.highway);
            if (label) lyr.bindPopup(escapeHtml(label));
          },
        }).addTo(regionLayerGroup);
      } catch (e) {
        // One missing/bad layer file shouldn't take down the rest of the map.
      }
    }
  }
}

function describeOsmFeature(props) {
  const name = props.name || props.highway || props.amenity || props.place || 'Unnamed feature';
  return escapeHtml(name);
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s == null ? '' : String(s);
  return div.innerHTML;
}

map.on('click', (e) => {
  if (targetMarker) {
    targetMarker.setLatLng(e.latlng);
  } else {
    targetMarker = L.marker(e.latlng, {
      icon: L.divIcon({ className: '', html: '<div style="font-size:22px">🎯</div>', iconSize: [22, 22] }),
    }).addTo(map);
  }
  updateNavigation(e.latlng);
});

document.getElementById('btn-refresh').addEventListener('click', refreshLocation);
document.getElementById('btn-clear-target').addEventListener('click', () => {
  if (targetMarker) { map.removeLayer(targetMarker); targetMarker = null; }
  navPanelEl.classList.remove('visible');
});

loadWorldOutline();
loadHazards();
loadRegionData();
loadCountryData();
refreshLocation();
setInterval(refreshLocation, 5000);
