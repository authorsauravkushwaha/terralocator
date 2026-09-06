/* TerraLocator frontend.
 *
 * No basemap imagery is loaded here on purpose — this app doesn't
 * assume you have internet for map tiles. What you get instead is
 * real vector data (roads/places you fetched with fetch_region.py) and
 * your own live position, drawn directly on a plain background. That is
 * enough to navigate by, the same way a handheld GPS unit with no map
 * subscription still shows you a track and a position dot.
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
let hasCenteredOnce = false;
const hazardLayerGroup = L.layerGroup().addTo(map);
const regionLayerGroup = L.layerGroup().addTo(map);

const fixStatusEl = document.getElementById('fix-status');
const navPanelEl = document.getElementById('nav-panel');
const disclaimerEl = document.getElementById('disclaimer');

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
      fixStatusEl.textContent = 'No GPS fix yet (check Termux:API + location permission)';
      fixStatusEl.className = 'bad';
      return;
    }
    const fix = await res.json();
    const latlng = [fix.lat, fix.lon];

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

    if (!hasCenteredOnce) {
      map.setView(latlng, 15);
      hasCenteredOnce = true;
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

loadHazards();
loadRegionData();
refreshLocation();
setInterval(refreshLocation, 5000);
