/* map.js — Leaflet initialisation, network overlay, pick mode */

let map;
let networkLayer;
let routeLayer;
let walkBoundsLayer = null;   // bounding box of walk nodes (admin toggle)
let networkStations = [];
let startMarker = null;
let endMarker   = null;

let networkVisible = true;    // subway lines toggle state
let walkBoundsVisible = true; // walk node bbox toggle state

let pickMode = null;   // 'start' | 'end' | null

const selectedPointIcon = L.divIcon({
  className: 'selected-point-marker',
  iconSize: [22, 30],
  iconAnchor: [11, 30],
  popupAnchor: [0, -30],
});

function _readAdminPrefs() {
  try {
    const nv = localStorage.getItem('admin_network_visible');
    const wb = localStorage.getItem('admin_walk_bounds_visible');
    if (nv !== null) networkVisible     = nv === '1';
    if (wb !== null) walkBoundsVisible  = wb === '1';
  } catch (_) {}
}

function initMap() {
  _readAdminPrefs();   // apply saved admin overlay prefs before rendering

  map = L.map('map').setView(MAP_CENTER, MAP_ZOOM);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);

  // React to admin-panel toggle changes in other tabs
  window.addEventListener('storage', async (e) => {
    if (e.key === 'admin_network_visible') {
      const want = e.newValue === '1';
      if (want !== networkVisible) toggleNetwork();
    }
    if (e.key === 'admin_walk_bounds_visible') {
      const want = e.newValue === '1';
      if (want !== walkBoundsVisible) await toggleWalkBounds();
    }
  });
// 1. Base Satellite Layer
  // L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
  //   attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
  //   maxZoom: 19
  // }).addTo(map);

  // // 2. Transparent Labels Overlay (Optional but recommended)
  // L.tileLayer('https://stamen-tiles-{s}.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}{r}.png', {
  //   attribution: 'Map tiles by Stamen Design, CC BY 3.0 &mdash; Map data &copy; OpenStreetMap',
  //   subdomains: 'abcd',
  //   maxZoom: 19
  // }).addTo(map);
  map.on('click', onMapClick);

  loadNetwork();
}

async function loadNetwork() {
  try {
    const res  = await fetch(`${API_BASE}/api/network`);
    const data = await res.json();

    networkStations = data.stations;
    networkLayer = L.layerGroup();

    // Populate dropdowns
    populateDropdowns(data.stations);
    for (const seg of data.segments) {
      const color = LINE_COLORS[seg.line_id] || '#888';
      L.polyline(
        [[seg.from_lat, seg.from_lng], [seg.to_lat, seg.to_lng]],
        { color, weight: 3, opacity: 0.7 }
      ).addTo(networkLayer);
    }

    // Add to map only if visible state is on
    if (networkVisible) networkLayer.addTo(map);

    // If walk bounds were toggled on before page load, draw them now
    if (walkBoundsVisible) {
      walkBoundsVisible = false;   // toggleWalkBounds flips the flag internally
      await toggleWalkBounds();
    }
  } catch (err) {
    console.error('Failed to load network:', err);
  }
}

// ── Admin toggles ────────────────────────────────────────────────────────────

/**
 * Toggle subway network lines on/off.
 * Returns the new visibility state.
 */
function toggleNetwork() {
  if (!networkLayer) return networkVisible;
  networkVisible = !networkVisible;
  if (networkVisible) {
    networkLayer.addTo(map);
  } else {
    map.removeLayer(networkLayer);
  }
  return networkVisible;
}

/**
 * Toggle the bounding-box rectangle that covers all walk nodes.
 * Fetches /api/network/walk-bounds on first call, caches the layer.
 * Returns a Promise<boolean> with the new visibility state.
 */
async function toggleWalkBounds() {
  walkBoundsVisible = !walkBoundsVisible;

  if (!walkBoundsVisible) {
    if (walkBoundsLayer) map.removeLayer(walkBoundsLayer);
    walkBoundsLayer = null;
    return false;
  }

  // Fetch bounds from backend
  try {
    const res  = await fetch(`${API_BASE}/api/network/walk-bounds`);
    const data = await res.json();
    const { min_lat, max_lat, min_lng, max_lng } = data;

    walkBoundsLayer = L.rectangle(
      [[min_lat, min_lng], [max_lat, max_lng]],
      {
        color:       '#e67e22',
        weight:      2,
        opacity:     0.85,
        fillColor:   '#e67e22',
        fillOpacity: 0.07,
        dashArray:   '6 5',
      }
    ).bindTooltip(
      `Walk node bounding box<br>${min_lat.toFixed(4)},${min_lng.toFixed(4)} → ${max_lat.toFixed(4)},${max_lng.toFixed(4)}`,
      { sticky: true }
    );
    walkBoundsLayer.addTo(map);
  } catch (err) {
    console.error('Failed to load walk bounds:', err);
    walkBoundsVisible = false;
  }
  return walkBoundsVisible;
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
    startMarker = L.marker([lat, lng], { title: 'Start', icon: selectedPointIcon })
      .bindPopup(stationName ? `Start: ${stationName}` : `Start: ${lat.toFixed(5)}, ${lng.toFixed(5)}`)
      .addTo(map);
    window._startPoint = { lat, lng };
    // Update dropdown to nearest station name or coordinates label
    syncDropdown('start', stationName, lat, lng);
  } else {
    if (endMarker) map.removeLayer(endMarker);
    endMarker = L.marker([lat, lng], { title: 'End', icon: selectedPointIcon })
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
  const visitedStations = findVisitedStations(steps);

  for (const step of steps) {
    if (!step.polyline || step.polyline.length < 2) continue;

    bounds.push(...step.polyline);

    if (step.kind === 'walk') {
      L.polyline(step.polyline, {
        color: WALK_COLOR, weight: 6, opacity: 1, dashArray: '6 8', lineCap: 'round',
      }).addTo(routeLayer);
    } else {
      L.polyline(step.polyline, {
        color: LINE_COLORS[step.line_id] || ROUTE_COLOR,
        weight: 7,
        opacity: 1,
        lineCap: 'round',
        lineJoin: 'round',
      }).addTo(routeLayer);
    }
  }

  drawVisitedStations(visitedStations);

  if (bounds.length) {
    map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40] });
  }
}

function findVisitedStations(steps) {
  const visited = new Map();
  const ridePoints = steps
    .filter(step => step.kind === 'ride' && step.polyline)
    .flatMap(step => step.polyline.map(point => ({ point, lineId: step.line_id })));

  for (const { point, lineId } of ridePoints) {
    const station = findStationAt(point, lineId);
    if (!station) continue;
    const key = `${station.name}|${station.lat.toFixed(6)}|${station.lng.toFixed(6)}`;
    if (!visited.has(key)) {
      visited.set(key, { ...station, routeLineId: lineId });
    }
  }

  return [...visited.values()];
}

function findStationAt(point, lineId) {
  const [lat, lng] = point;
  const closeStations = networkStations
    .filter(st => !lineId || st.lines.includes(lineId))
    .map(st => ({
      station: st,
      distance: map.distance([lat, lng], [st.lat, st.lng]),
    }))
    .filter(match => match.distance <= 45)
    .sort((a, b) => a.distance - b.distance);

  return closeStations[0]?.station || null;
}

function drawVisitedStations(stations) {
  for (const st of stations) {
    const color = LINE_COLORS[st.routeLineId] || LINE_COLORS[st.lines[0]] || '#888';
    L.circleMarker([st.lat, st.lng], {
      radius: 6,
      color: '#fff',
      fillColor: color,
      fillOpacity: 1,
      weight: 3,
      pane: 'markerPane',
    })
      .bindTooltip(st.name, { direction: 'top', offset: [0, -8] })
      .addTo(routeLayer);
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
