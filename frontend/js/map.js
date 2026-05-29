/* map.js — Leaflet initialisation, network overlay, pick mode */

let map;
let networkLayer;
let routeLayer;
let startMarker = null;
let endMarker   = null;

let pickMode = null;   // 'start' | 'end' | null

function initMap() {
  map = L.map('map').setView(MAP_CENTER, MAP_ZOOM);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);

  map.on('click', onMapClick);

  loadNetwork();
}

async function loadNetwork() {
  try {
    const res  = await fetch(`${API_BASE}/api/network`);
    const data = await res.json();

    networkLayer = L.layerGroup().addTo(map);

    // Draw segments
    for (const seg of data.segments) {
      const color = LINE_COLORS[seg.line_id] || '#888';
      L.polyline(
        [[seg.from_lat, seg.from_lng], [seg.to_lat, seg.to_lng]],
        { color, weight: 3, opacity: 0.7 }
      ).addTo(networkLayer);
    }

    // Draw station markers
    for (const st of data.stations) {
      const colors = st.lines.map(l => LINE_COLORS[l] || '#888');
      const color  = colors[0] || '#888';
      L.circleMarker([st.lat, st.lng], {
        radius: 5,
        color: '#fff',
        fillColor: color,
        fillOpacity: 1,
        weight: 2,
      })
        .bindTooltip(st.name, { direction: 'top', offset: [0, -6] })
        .on('click', function (e) {
          L.DomEvent.stopPropagation(e);
          onStationClick(st);
        })
        .addTo(networkLayer);
    }

    // Populate dropdowns
    populateDropdowns(data.stations);
  } catch (err) {
    console.error('Failed to load network:', err);
  }
}

function onMapClick(e) {
  if (!pickMode) return;
  const { lat, lng } = e.latlng;
  setPoint(pickMode, lat, lng, null);
  setPickMode(null);
}

function onStationClick(station) {
  if (!pickMode) return;
  setPoint(pickMode, station.lat, station.lng, station.name);
  setPickMode(null);
}

function setPoint(which, lat, lng, stationName) {
  if (which === 'start') {
    if (startMarker) map.removeLayer(startMarker);
    startMarker = L.marker([lat, lng], { title: 'Start' })
      .bindPopup(stationName ? `Start: ${stationName}` : `Start: ${lat.toFixed(5)}, ${lng.toFixed(5)}`)
      .addTo(map);
    window._startPoint = { lat, lng };
    // Update dropdown to nearest station name or coordinates label
    syncDropdown('start', stationName, lat, lng);
  } else {
    if (endMarker) map.removeLayer(endMarker);
    endMarker = L.marker([lat, lng], { title: 'End' })
      .bindPopup(stationName ? `End: ${stationName}` : `End: ${lat.toFixed(5)}, ${lng.toFixed(5)}`)
      .addTo(map);
    window._endPoint = { lat, lng };
    syncDropdown('end', stationName, lat, lng);
  }
}

function setPickMode(mode) {
  pickMode = mode;
  map.getContainer().style.cursor = mode ? 'crosshair' : '';
  updatePickButtons(mode);
}

function drawRoute(steps) {
  if (routeLayer) map.removeLayer(routeLayer);
  routeLayer = L.layerGroup().addTo(map);

  const bounds = [];

  for (const step of steps) {
    if (!step.polyline || step.polyline.length < 2) continue;

    bounds.push(...step.polyline);

    if (step.kind === 'ride') {
      const color = LINE_COLORS[step.line_id] || '#999';
      L.polyline(step.polyline, { color, weight: 6, opacity: 0.9 }).addTo(routeLayer);
    } else if (step.kind === 'walk') {
      L.polyline(step.polyline, {
        color: WALK_COLOR, weight: 4, opacity: 0.7, dashArray: '6 8',
      }).addTo(routeLayer);
    } else {
      L.polyline(step.polyline, { color: '#aaa', weight: 3, opacity: 0.5 }).addTo(routeLayer);
    }
  }

  if (bounds.length) {
    map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40] });
  }
}

function clearRoute() {
  if (routeLayer) { map.removeLayer(routeLayer); routeLayer = null; }
  if (startMarker) { map.removeLayer(startMarker); startMarker = null; }
  if (endMarker)   { map.removeLayer(endMarker);   endMarker   = null; }
  window._startPoint = null;
  window._endPoint   = null;
  setPickMode(null);
}
