/* ui.js — dropdown population, pick buttons, form state management */

let _stations = [];

function populateDropdowns(stations) {
  _stations = [...stations].sort((a, b) => a.name.localeCompare(b.name));

  const startSel = document.getElementById('sel-start');
  const endSel   = document.getElementById('sel-end');

  const blank = () => {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '— select station —';
    return opt;
  };

  startSel.innerHTML = '';
  endSel.innerHTML   = '';
  startSel.appendChild(blank());
  endSel.appendChild(blank());

  for (const st of _stations) {
    const makeOpt = () => {
      const opt = document.createElement('option');
      opt.value = JSON.stringify({ lat: st.lat, lng: st.lng, name: st.name });
      opt.textContent = `${st.name} (${st.lines.join(', ')})`;
      return opt;
    };
    startSel.appendChild(makeOpt());
    endSel.appendChild(makeOpt());
  }

  startSel.addEventListener('change', () => {
    if (!startSel.value) return;
    const pt = JSON.parse(startSel.value);
    setPoint('start', pt.lat, pt.lng, pt.name);
  });

  endSel.addEventListener('change', () => {
    if (!endSel.value) return;
    const pt = JSON.parse(endSel.value);
    setPoint('end', pt.lat, pt.lng, pt.name);
  });
}

function syncDropdown(which, stationName, lat, lng) {
  const sel = document.getElementById(which === 'start' ? 'sel-start' : 'sel-end');
  if (!sel) return;

  if (stationName) {
    // Try to match by name
    for (const opt of sel.options) {
      if (opt.value) {
        const pt = JSON.parse(opt.value);
        if (pt.name === stationName) {
          sel.value = opt.value;
          return;
        }
      }
    }
  }

  // Add a custom "map click" option
  const existing = sel.querySelector('option[data-custom]');
  if (existing) existing.remove();
  const opt = document.createElement('option');
  opt.setAttribute('data-custom', '1');
  opt.value = JSON.stringify({ lat, lng, name: null });
  opt.textContent = `📍 ${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  sel.appendChild(opt);
  sel.value = opt.value;
}

function updatePickButtons(mode) {
  document.getElementById('btn-pick-start').classList.toggle('active', mode === 'start');
  document.getElementById('btn-pick-end').classList.toggle('active', mode === 'end');
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btn-pick-start').addEventListener('click', () => {
    setPickMode(pickMode === 'start' ? null : 'start');
  });
  document.getElementById('btn-pick-end').addEventListener('click', () => {
    setPickMode(pickMode === 'end' ? null : 'end');
  });

  document.getElementById('btn-find').addEventListener('click', findRoute);

  document.getElementById('btn-reset').addEventListener('click', () => {
    clearRoute();
    document.getElementById('sel-start').value = '';
    document.getElementById('sel-end').value   = '';
    document.getElementById('result-banner').textContent = '';
    document.getElementById('result-steps').innerHTML    = '';
  });
});
