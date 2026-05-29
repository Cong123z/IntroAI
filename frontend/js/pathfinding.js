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

async function findRoute() {
  const start = window._startPoint;
  const end   = window._endPoint;

  if (!start || !end) {
    alert('Hãy chọn điểm đi và điểm đến hợp lệ');
    return;
  }

  const banner = document.getElementById('result-banner');
  const steps  = document.getElementById('result-steps');
  banner.textContent = 'Đang tìm đường…';
  steps.innerHTML    = '';

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
      banner.textContent = `❌ ${err.detail || 'Không tìm thấy đường'}`;
      return;
    }

    const data = await res.json();

    // Draw colored polyline on map
    drawRoute(data.steps, data.coords);

    // Update banner
    banner.textContent = `✅ Tổng thời gian: ${formatDuration(data.total_time_s)}`;

    // Render step list
    steps.innerHTML = '';
    data.steps.forEach((step, i) => {
      const li = document.createElement('li');
      li.className = `step step-${step.kind}`;

      const icon  = STEP_ICONS[step.kind] || '•';
      const color = step.line_id ? LINE_COLORS[step.line_id] : null;

      li.innerHTML = `
        <span class="step-icon">${icon}</span>
        <span class="step-desc">${step.description}</span>
        <span class="step-dur">${formatDuration(step.duration_s)}</span>
      `;

      if (color) {
        li.style.borderLeftColor = color;
      }

      steps.appendChild(li);
    });
  } catch (err) {
    banner.textContent = `❌ Error: ${err.message}`;
    console.error(err);
  }
}
