/* admin.js — scenario CRUD + weather toggle + map overlay toggles */

const API_BASE = '';

// ── Helpers ──────────────────────────────────────────────────────────────────

function _setOverlayState(key, value) {
  try { localStorage.setItem(key, value ? '1' : '0'); } catch (_) {}
}

function _getOverlayState(key, defaultVal) {
  try {
    const v = localStorage.getItem(key);
    return v === null ? defaultVal : v === '1';
  } catch (_) { return defaultVal; }
}

function _setToggle(btnId, value) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.setAttribute('aria-checked', value ? 'true' : 'false');
}

// ── Map overlay toggles ───────────────────────────────────────────────────────

function handleToggleNetwork() {
  const btn  = document.getElementById('btn-toggle-network');
  const next = btn.getAttribute('aria-checked') !== 'true';
  _setToggle('btn-toggle-network', next);
  _setOverlayState('admin_network_visible', next);
  window.dispatchEvent(new StorageEvent('storage', {
    key: 'admin_network_visible', newValue: next ? '1' : '0',
  }));
}

function handleToggleWalkBounds() {
  const btn  = document.getElementById('btn-toggle-walk-bounds');
  const next = btn.getAttribute('aria-checked') !== 'true';
  _setToggle('btn-toggle-walk-bounds', next);
  _setOverlayState('admin_walk_bounds_visible', next);
  window.dispatchEvent(new StorageEvent('storage', {
    key: 'admin_walk_bounds_visible', newValue: next ? '1' : '0',
  }));
}

// ── Scenario management ───────────────────────────────────────────────────────

async function loadScenarios() {
  const res  = await fetch(`${API_BASE}/api/scenarios`);
  const list = await res.json();
  const ul   = document.getElementById('scenario-list');
  ul.innerHTML = '';

  if (list.length === 0) {
    ul.innerHTML = '<li class="empty-list">No active closures</li>';
    return;
  }

  for (const s of list) {
    const li = document.createElement('li');
    li.className = 'scenario-item';

    let label = '';
    if (s.type === 'station')      label = `Station — ${s.payload.station_id || s.payload.id}`;
    else if (s.type === 'line')    label = `Line — ${s.payload.line_id || s.payload.id}`;
    else if (s.type === 'segment') label = `Segment — ${s.payload.from_platform} → ${s.payload.to_platform}`;
    else                           label = `${s.type}: ${JSON.stringify(s.payload)}`;

    li.innerHTML = `<span>${label}</span><button onclick="deleteScenario(${s.id})" title="Remove">✕</button>`;
    ul.appendChild(li);
  }
}

async function addScenario() {
  const typeEl   = document.getElementById('sel-type');
  const targetEl = document.getElementById('sel-target');
  const type     = typeEl.value;
  const target   = targetEl.value;
  if (!target) { alert('Please select a target.'); return; }

  let payload = {};
  if (type === 'station') {
    payload = { station_id: target };
  } else if (type === 'line') {
    payload = { line_id: target };
  } else if (type === 'segment') {
    const [fp, tp]     = target.split('|');
    // FIX 2: parse with explicit radix and guard against NaN before the
    // value reaches JSON.stringify (where NaN silently becomes null).
    const fromPlatform = parseInt(fp, 10);
    const toPlatform   = parseInt(tp, 10);
    if (isNaN(fromPlatform) || isNaN(toPlatform)) {
      alert('Invalid segment selection — platform IDs are not integers.');
      return;
    }
    payload = { from_platform: fromPlatform, to_platform: toPlatform };
  }

  await fetch(`${API_BASE}/api/scenarios`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ type, payload }),
  });
  await loadScenarios();
}

async function deleteScenario(sid) {
  await fetch(`${API_BASE}/api/scenarios/${sid}`, { method: 'DELETE' });
  await loadScenarios();
}

async function clearAll() {
  if (!confirm('Remove all active closures?')) return;
  await fetch(`${API_BASE}/api/scenarios`, { method: 'DELETE' });
  await loadScenarios();
}

async function onTypeChange() {
  const typeEl   = document.getElementById('sel-type');
  const targetEl = document.getElementById('sel-target');
  const type     = typeEl.value;
  targetEl.innerHTML = '<option value="">— select —</option>';

  const res  = await fetch(`${API_BASE}/api/network`);
  const data = await res.json();

  if (type === 'station') {
    const stations = [...data.stations].sort((a, b) => a.name.localeCompare(b.name));
    for (const st of stations) {
      const opt = document.createElement('option');
      opt.value       = st.id;
      opt.textContent = st.name;
      targetEl.appendChild(opt);
    }
  } else if (type === 'line') {
    const lines = [...new Set(data.stations.flatMap(s => s.lines))].sort();
    for (const l of lines) {
      const opt = document.createElement('option');
      opt.value       = l;
      opt.textContent = l;
      targetEl.appendChild(opt);
    }
  } else if (type === 'segment') {
    for (const seg of data.segments) {
      const opt = document.createElement('option');
      // FIX 1: use integer platform IDs as the option value so that
      // parseInt() in addScenario() receives numeric strings ("12|34"),
      // not station-name strings ("central|north") which parse to NaN.
      opt.value       = `${seg.from_platform}|${seg.to_platform}`;
      // Human-readable label still uses station names + line for clarity.
      opt.textContent = `${seg.line_id}: ${seg.from_station} → ${seg.to_station}`;
      targetEl.appendChild(opt);
    }
  }
}

// ── Weather ───────────────────────────────────────────────────────────────────

const WEATHER_META = {
  clear: 'Walk speed 1.4 m/s — clear conditions',
  rain:  'Walk speed 1.1 m/s — wet surfaces',
  snow:  'Walk speed 0.8 m/s — heavy going',
};

async function loadWeather() {
  const res  = await fetch(`${API_BASE}/api/weather`);
  const data = await res.json();
  setWeatherUI(data.condition);
}

async function applyWeather(condition) {
  const res = await fetch(`${API_BASE}/api/weather`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ condition }),
  });
  if (!res.ok) { console.error('Weather update failed', await res.text()); return; }
  const data = await res.json();
  setWeatherUI(data.condition);
}

function setWeatherUI(condition) {
  document.querySelectorAll('.wtab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.condition === condition);
  });
  const label = document.getElementById('weather-speed-label');
  if (label) label.textContent = WEATHER_META[condition] ?? WEATHER_META.clear;
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Restore overlay toggle states
  _setToggle('btn-toggle-network',    _getOverlayState('admin_network_visible', true));
  _setToggle('btn-toggle-walk-bounds', _getOverlayState('admin_walk_bounds_visible', false));

  // Wire up controls
  document.getElementById('sel-type').addEventListener('change', onTypeChange);
  document.getElementById('btn-add').addEventListener('click', addScenario);
  document.getElementById('btn-clear-all').addEventListener('click', clearAll);

  document.querySelectorAll('.wtab').forEach(btn => {
    btn.addEventListener('click', () => applyWeather(btn.dataset.condition));
  });

  // Initial data load
  loadScenarios();
  loadWeather();
  onTypeChange();
});