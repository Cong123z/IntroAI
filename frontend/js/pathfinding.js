/* pathfinding.js — route request, polyline drawing, itinerary rendering */

const STEP_ICONS = {
  walk:     '🚶',
  enter:    '⬇️',
  exit:     '⬆️',
  ride:     '🚇',
  transfer: '🔄',
};

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m === 0) return `${s} sec`;
  return s ? `${m} min ${s} sec` : `${m} min`;
}

function formatDistance(metres) {
  if (!metres || metres < 1) return '';
  return metres >= 1000
    ? `${(metres / 1000).toFixed(1)} km`
    : `${Math.round(metres)} m`;
}

async function findRoute() {
  const start = window._startPoint;
  const end   = window._endPoint;

  if (!start || !end) {
    alert('Please set both a start and end point.');
    return;
  }

  const banner = document.getElementById('result-banner');
  const stepsList = document.getElementById('result-steps');
  banner.textContent = '⏳ Finding route…';
  stepsList.innerHTML = '';

  try {
    const res = await fetch(`${API_BASE}/api/path`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lat_start: start.lat,
        lng_start: start.lng,
        lat_end:   end.lat,
        lng_end:   end.lng,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      banner.textContent = `❌ ${err.detail || 'No route found'}`;
      return;
    }

    const data = await res.json();

    // Draw the full coords polyline on the map, coloured by step kind
    drawRouteFromStepsAndCoords(data.steps, data.coords);

    // Update banner
    banner.textContent = `✅ Total: ${formatDuration(data.total_time_s)}`;

    // Render step list
    stepsList.innerHTML = '';
    data.steps.forEach((step) => {
      const li = document.createElement('li');
      li.className = `step step-${step.kind}`;

      const color = step.line_id ? LINE_COLORS[step.line_id] : null;
      if (color) li.style.borderLeftColor = color;

      const distStr = step.distance_m ? ` · ${formatDistance(step.distance_m)}` : '';
      li.innerHTML = `
        <span class="step-icon">${STEP_ICONS[step.kind] || '•'}</span>
        <span class="step-desc">${step.description}${distStr}</span>
        <span class="step-dur">${formatDuration(step.duration_s)}</span>
      `;
      stepsList.appendChild(li);
    });

  } catch (err) {
    banner.textContent = `❌ Error: ${err.message}`;
    console.error(err);
  }
}

/**
 * Draw the route using the authoritative coords array from PathResult,
 * coloured segment-by-segment based on each step's kind/line_id.
 * steps[i] covers coords[i] → coords[i+1].
 */
function drawRouteFromStepsAndCoords(steps, coords) {
  if (routeLayer) map.removeLayer(routeLayer);
  routeLayer = L.layerGroup().addTo(map);

  if (!coords || coords.length < 2) return;

  // Walk the steps; each step consumes one or more coord segments
  let coordIdx = 0;

  for (const step of steps) {
    // Estimate how many coord points this step spans.
    // Since coords is the full node list, each step = 1 edge = 2 consecutive coords.
    const from = coords[coordIdx];
    const to   = coords[Math.min(coordIdx + 1, coords.length - 1)];
    if (!from || !to) break;

    const poly = [from, to];

    if (step.kind === 'ride') {
      const color = LINE_COLORS[step.line_id] || '#888';
      L.polyline(poly, { color, weight: 6, opacity: 0.9 }).addTo(routeLayer);
    } else if (step.kind === 'walk') {
      L.polyline(poly, { color: WALK_COLOR, weight: 4, opacity: 0.7, dashArray: '6 8' }).addTo(routeLayer);
    } else {
      L.polyline(poly, { color: '#aaa', weight: 3, opacity: 0.5 }).addTo(routeLayer);
    }
    coordIdx++;
  }

  // Draw any remaining coords as grey
  if (coordIdx < coords.length - 1) {
    L.polyline(coords.slice(coordIdx), { color: '#bbb', weight: 2, opacity: 0.5 }).addTo(routeLayer);
  }

  // Fit bounds
  if (coords.length) {
    map.fitBounds(L.latLngBounds(coords), { padding: [40, 40] });
  }
}
