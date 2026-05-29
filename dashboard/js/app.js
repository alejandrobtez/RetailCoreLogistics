/* ============================================================
   RetailCore Logistics · Dashboard App JS
   ============================================================ */

const API_BASE = '/api/v1';

// ── STATE ─────────────────────────────────────────────────
let state = {
  predictions: [],    // Last BatchResponse from API
  queue: [],          // Deliveries pending prediction
  smsSent: new Set(), // delivery_ids with SMS simulated
  counter: 1,
};

// ── INIT ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  setupForm();
  setupButtons();
  checkHealth();
  setDateBadge();
});

function setDateBadge() {
  const el = document.getElementById('panel-date');
  if (el) el.textContent = new Date().toLocaleDateString('es-ES', { weekday:'long', year:'numeric', month:'long', day:'numeric' });
}

// ── HEALTH CHECK ──────────────────────────────────────────
async function checkHealth() {
  const badge    = document.getElementById('api-status');
  const textEl   = document.getElementById('status-text');
  const modelBadge = document.getElementById('model-name-badge');
  try {
    const res  = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    if (data.model_loaded) {
      badge.className   = 'status-badge status-ok';
      textEl.textContent = '✓ API y modelo activos';
      modelBadge.textContent = data.model_name ? `Modelo: ${data.model_name}` : '';
    } else {
      badge.className   = 'status-badge status-error';
      textEl.textContent = '⚠ Modelo no cargado';
    }
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) refreshBtn.disabled = !data.model_loaded;
  } catch (_) {
    badge.className   = 'status-badge status-error';
    textEl.textContent = '✗ API no disponible';
  }
}

// ── TABS ──────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
      btn.classList.add('active');
      const tab = document.getElementById(`tab-${btn.dataset.tab}`);
      if (tab) tab.classList.add('active');
      if (btn.dataset.tab === 'mapa') {
        setTimeout(() => {
          initMap();
          if (state.predictions.length) refreshMap();
        }, 100);
      }
    });
  });
}

// ── BUTTONS ───────────────────────────────────────────────
function setupButtons() {
  document.getElementById('btn-demo').addEventListener('click', loadDemoData);
  document.getElementById('btn-refresh').addEventListener('click', () => {
    if (state.predictions.length) renderPanel(state.predictions);
  });
  document.getElementById('btn-predict').addEventListener('click', runPrediction);
  document.getElementById('btn-clear-queue').addEventListener('click', clearQueue);
  document.getElementById('btn-add-demo-form').addEventListener('click', addDemoToQueue);
}

// ── DEMO DATA ─────────────────────────────────────────────
function generateDemoDeliveries() {
  const scenarios = [
    // HIGH risk: lluvia + reintento + centro histórico + baja calidad conductor
    { zone:'madrid',    zone_type:'historic_center', weather_rain:1, is_retry:1, driver_quality_score:0.35, recipient_failure_rate:0.65, hour:18, num_previous_attempts:2, product_type:'fragile', is_fragile:1, weight_kg:3.2 },
    { zone:'barcelona', zone_type:'historic_center', weather_rain:1, is_retry:1, driver_quality_score:0.40, recipient_failure_rate:0.72, hour:19, num_previous_attempts:3, product_type:'high_value', is_fragile:0, weight_kg:1.5 },
    { zone:'sevilla',   zone_type:'residential',     weather_rain:1, is_retry:1, driver_quality_score:0.30, recipient_failure_rate:0.58, hour:20, num_previous_attempts:2, product_type:'signature_required', requires_signature:1, weight_kg:5.0 },
    // MEDIUM risk
    { zone:'madrid',    zone_type:'offices',         weather_rain:0, is_retry:1, driver_quality_score:0.65, recipient_failure_rate:0.40, hour:14, num_previous_attempts:1, product_type:'standard', weight_kg:2.0 },
    { zone:'valencia',  zone_type:'residential',     weather_rain:1, is_retry:0, driver_quality_score:0.60, recipient_failure_rate:0.35, hour:11, num_previous_attempts:0, product_type:'bulky', is_bulky:1, weight_kg:12.0 },
    { zone:'barcelona', zone_type:'industrial',      weather_rain:0, is_retry:1, driver_quality_score:0.70, recipient_failure_rate:0.30, hour:16, num_previous_attempts:1, product_type:'fragile', is_fragile:1, weight_kg:4.5 },
    { zone:'sevilla',   zone_type:'offices',         weather_rain:1, is_retry:0, driver_quality_score:0.55, recipient_failure_rate:0.45, hour:10, num_previous_attempts:0, product_type:'standard', weight_kg:1.2 },
    // LOW risk
    { zone:'madrid',    zone_type:'industrial',      weather_rain:0, is_retry:0, driver_quality_score:0.92, recipient_failure_rate:0.10, hour:9,  num_previous_attempts:0, product_type:'standard', weight_kg:8.0 },
    { zone:'barcelona', zone_type:'residential',     weather_rain:0, is_retry:0, driver_quality_score:0.88, recipient_failure_rate:0.08, hour:10, num_previous_attempts:0, product_type:'standard', weight_kg:1.8 },
    { zone:'valencia',  zone_type:'industrial',      weather_rain:0, is_retry:0, driver_quality_score:0.95, recipient_failure_rate:0.05, hour:8,  num_previous_attempts:0, product_type:'bulky', is_bulky:1, weight_kg:22.0 },
    { zone:'madrid',    zone_type:'residential',     weather_rain:0, is_retry:0, driver_quality_score:0.85, recipient_failure_rate:0.12, hour:11, num_previous_attempts:0, product_type:'high_value', weight_kg:0.5 },
    { zone:'sevilla',   zone_type:'industrial',      weather_rain:0, is_retry:0, driver_quality_score:0.90, recipient_failure_rate:0.07, hour:7,  num_previous_attempts:0, product_type:'standard', weight_kg:15.0 },
  ];

  return scenarios.map((s, i) => ({
    delivery_id: `DLV-${String(i + 1).padStart(5, '0')}`,
    date: new Date().toISOString().split('T')[0],
    hour: s.hour || 10,
    day_of_week: new Date().getDay() === 0 ? 6 : new Date().getDay() - 1,
    is_holiday: 0,
    zone: s.zone,
    zone_type: s.zone_type,
    recipient_failure_rate: s.recipient_failure_rate ?? 0.2,
    num_previous_attempts:  s.num_previous_attempts  ?? 0,
    driver_quality_score:   s.driver_quality_score   ?? 0.75,
    driver_delivery_load: 20,
    product_type: s.product_type || 'standard',
    requires_signature: s.requires_signature || 0,
    is_fragile: s.is_fragile || 0,
    is_bulky:   s.is_bulky   || 0,
    weight_kg: s.weight_kg || 2.0,
    weather_rain: s.weather_rain || 0,
    weather_wind_speed: s.weather_rain ? 4.5 : 2.0,
    weather_temperature: 16,
    is_retry: s.is_retry || 0,
  }));
}

async function loadDemoData() {
  const deliveries = generateDemoDeliveries();
  await sendAndRender(deliveries, 'madrid', false);
}

// ── PREDICTION QUEUE ──────────────────────────────────────
function setupForm() {
  document.getElementById('delivery-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const d  = buildDeliveryFromForm(fd);
    addToQueue(d);
    e.target.reset();
    document.getElementById('rfr-val').textContent = '0.20';
    document.getElementById('dqs-val').textContent = '0.75';
  });
}

function buildDeliveryFromForm(fd) {
  return {
    delivery_id: `DLV-CUSTOM-${String(state.counter++).padStart(3,'0')}`,
    date: new Date().toISOString().split('T')[0],
    hour: parseInt(fd.get('hour') || 10),
    day_of_week: parseInt(fd.get('day_of_week') || 0),
    is_holiday: fd.get('is_holiday') ? 1 : 0,
    zone: fd.get('zone'),
    zone_type: fd.get('zone_type'),
    recipient_failure_rate: parseFloat(fd.get('recipient_failure_rate') || 0.2),
    num_previous_attempts: parseInt(fd.get('num_previous_attempts') || 0),
    driver_quality_score: parseFloat(fd.get('driver_quality_score') || 0.75),
    driver_delivery_load: parseInt(fd.get('driver_delivery_load') || 20),
    product_type: fd.get('product_type'),
    requires_signature: fd.get('requires_signature') ? 1 : 0,
    is_fragile: fd.get('is_fragile') ? 1 : 0,
    is_bulky: fd.get('is_bulky') ? 1 : 0,
    weight_kg: parseFloat(fd.get('weight_kg') || 2.0),
    weather_rain: fd.get('weather_rain') ? 1 : 0,
    weather_wind_speed: parseFloat(fd.get('weather_wind_speed') || 5),
    weather_temperature: parseFloat(fd.get('weather_temperature') || 18),
    is_retry: fd.get('is_retry') ? 1 : 0,
  };
}

function addToQueue(delivery) {
  state.queue.push(delivery);
  renderQueue();
}

function clearQueue() {
  state.queue = [];
  renderQueue();
}

function renderQueue() {
  const list     = document.getElementById('queue-list');
  const countEl  = document.getElementById('queue-count');
  const predictBtn = document.getElementById('btn-predict');
  const clearBtn   = document.getElementById('btn-clear-queue');

  countEl.textContent = `${state.queue.length} entrega${state.queue.length !== 1 ? 's' : ''}`;
  predictBtn.disabled = state.queue.length === 0;
  clearBtn.disabled   = state.queue.length === 0;

  if (state.queue.length === 0) {
    list.innerHTML = `<div class="empty-state small"><span>📋</span><p>Añade entregas al formulario</p></div>`;
    return;
  }

  list.innerHTML = state.queue.map((d, i) => `
    <div class="queue-item">
      <div class="queue-item-info">
        <span class="queue-item-id">${d.delivery_id}</span>
        <span class="queue-item-meta">${capitalize(d.zone)} · ${humanZoneType(d.zone_type)} · ${capitalize(d.product_type)}</span>
      </div>
      <button class="queue-item-remove" data-idx="${i}" title="Quitar">✕</button>
    </div>
  `).join('');

  list.querySelectorAll('.queue-item-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      state.queue.splice(parseInt(btn.dataset.idx), 1);
      renderQueue();
    });
  });
}

function addDemoToQueue() {
  const demos = generateDemoDeliveries().slice(0, 5);
  demos.forEach(d => state.queue.push(d));
  renderQueue();
}

async function runPrediction() {
  if (state.queue.length === 0) return;
  const loading = document.getElementById('pred-loading');
  loading.classList.remove('hidden');
  const deliveries = [...state.queue];
  const city = deliveries[0]?.zone || 'madrid';
  await sendAndRender(deliveries, city, false);
  state.queue = [];
  renderQueue();
  loading.classList.add('hidden');
  // Switch to panel tab
  document.querySelector('[data-tab="panel"]').click();
}

// ── API CALL ──────────────────────────────────────────────
async function sendAndRender(deliveries, city, useAemet) {
  try {
    const res = await fetch(`${API_BASE}/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ city, use_aemet: useAemet, deliveries }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`Error de la API: ${err.detail || res.statusText}`);
      return;
    }
    const data = await res.json();
    // Merge with original delivery details
    const enriched = data.predictions.map(p => {
      const original = deliveries.find(d => d.delivery_id === p.delivery_id) || {};
      return { ...p, ...original, prob_fallo: p.prob_fallo, risk_level: p.risk_level, action: p.action, shap_reason: p.shap_reason };
    });
    state.predictions = enriched;
    renderPanel(enriched);
    updateStats(data);
    refreshMap();
  } catch (err) {
    alert(`No se pudo conectar con la API.\n\n${err.message}\n\n¿Está corriendo? uvicorn api.main:app --reload --port 8000`);
  }
}

// ── RENDER PANEL ──────────────────────────────────────────
function renderPanel(enriched) {
  const sorted = [...enriched].sort((a, b) => b.prob_fallo - a.prob_fallo);
  const tbody  = document.getElementById('table-body');
  tbody.innerHTML = '';

  sorted.forEach((row, i) => {
    const level   = row.risk_level || 'LOW';
    const rowClass = level === 'HIGH' ? 'row-high' : level === 'MEDIUM' ? 'row-medium' : '';
    const badge    = riskBadge(level);
    const pct      = (row.prob_fallo * 100).toFixed(1);
    const barColor = level === 'HIGH' ? 'var(--high)' : level === 'MEDIUM' ? 'var(--medium)' : 'var(--low)';
    const reason   = row.shap_reason || buildReasonText(row);
    const smsCellHtml = level === 'HIGH' ? smsCell(row.delivery_id) : '<span style="color:var(--text-muted);font-size:.7rem">—</span>';

    tbody.insertAdjacentHTML('beforeend', `
      <tr class="${rowClass}" data-id="${escHtml(row.delivery_id)}">
        <td style="color:var(--text-muted);font-size:.75rem">${i + 1}</td>
        <td><strong>${escHtml(row.delivery_id)}</strong></td>
        <td>${capitalize(row.zone || '—')}<br><small style="color:var(--text-muted)">${humanZoneType(row.zone_type)}</small></td>
        <td>${humanProduct(row.product_type)}</td>
        <td>${badge}</td>
        <td>
          <div class="prob-bar-wrap">
            <strong>${pct}%</strong>
            <div class="prob-bar"><div class="prob-bar-fill" style="width:${pct}%;background:${barColor}"></div></div>
          </div>
        </td>
        <td style="font-size:.75rem;max-width:200px">${reason}</td>
        <td><span class="action-chip">${humanAction(row.action)}</span></td>
        <td>${smsCellHtml}</td>
      </tr>
    `);
  });

  // Wire SMS buttons
  tbody.querySelectorAll('.sms-btn').forEach(btn => {
    btn.addEventListener('click', () => simulateSms(btn.dataset.id));
  });
}

function smsCell(id) {
  if (state.smsSent.has(id)) {
    return `<span class="sms-sent">✓ SMS enviado</span>`;
  }
  return `<button class="sms-btn" data-id="${escHtml(id)}">📱 Enviar SMS</button>`;
}

async function simulateSms(deliveryId) {
  const btn = document.querySelector(`.sms-btn[data-id="${deliveryId}"]`);
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }

  const row = state.predictions.find(p => p.delivery_id === deliveryId);
  try {
    const res = await fetch(`${API_BASE}/alerts/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        city: row?.zone || 'madrid',
        predictions: [{ delivery_id: deliveryId, prob_fallo: row?.prob_fallo || 0.9, risk_level: 'HIGH', action: 'REAGENDAR_SMS', shap_reason: null }],
      }),
    });
    const data = await res.json();
    const alert = data.alerts?.[0];
    state.smsSent.add(deliveryId);
    if (btn) btn.parentElement.innerHTML = `<span class="sms-sent">✓ SMS ${alert?.simulated ? 'simulado' : 'enviado'}</span>`;
    appendSmsLog(alert, row);
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = '📱 Enviar SMS'; }
    console.error('Error enviando alerta:', e);
  }
  updateSmsCount();
}

function appendSmsLog(alert, row) {
  const log = document.getElementById('sms-log');
  const logList = document.getElementById('sms-log-list');
  log.classList.remove('hidden');
  const time = new Date().toLocaleTimeString('es-ES', { hour:'2-digit', minute:'2-digit' });
  const tag = alert?.simulated
    ? '<span style="background:#ddd6fe;color:#5b21b6;padding:1px 6px;border-radius:4px;font-size:.7rem">SIMULADO</span>'
    : '<span style="background:#dcfce7;color:#166534;padding:1px 6px;border-radius:4px;font-size:.7rem">REAL · Logic Apps</span>';
  logList.insertAdjacentHTML('afterbegin', `
    <div class="sms-log-item">
      📱 <strong>${time}</strong> ${tag} · ${alert?.delivery_id} · ${capitalize(row?.zone || '—')} ·
      Prob: ${((row?.prob_fallo||0)*100).toFixed(1)}% ·
      <em>"${alert?.message || 'Le proponemos cambiar la franja horaria.'}"</em>
    </div>
  `);
}

function updateSmsCount() {
  document.getElementById('stat-sms').textContent = state.smsSent.size;
}

// ── STATS ─────────────────────────────────────────────────
function updateStats(data) {
  document.getElementById('stat-total').textContent  = data.total  ?? 0;
  document.getElementById('stat-high').textContent   = data.high   ?? 0;
  document.getElementById('stat-medium').textContent = data.medium ?? 0;
  document.getElementById('stat-low').textContent    = data.low    ?? 0;
  updateSmsCount();
  const mb = document.getElementById('model-name-badge');
  if (data.model_name) mb.textContent = `Modelo: ${data.model_name}`;
  document.getElementById('last-update').textContent = `Última actualización: ${new Date().toLocaleTimeString('es-ES')}`;
  document.getElementById('btn-refresh').disabled = false;
}

// ── MAP REFRESH ───────────────────────────────────────────
function refreshMap() {
  const cityStats = {};
  state.predictions.forEach(p => {
    const city = p.zone || 'madrid';
    if (!cityStats[city]) cityStats[city] = { total: 0, high: 0, medium: 0, low: 0 };
    cityStats[city].total++;
    if (p.risk_level === 'HIGH')   cityStats[city].high++;
    if (p.risk_level === 'MEDIUM') cityStats[city].medium++;
    if (p.risk_level === 'LOW')    cityStats[city].low++;
  });
  if (typeof updateMapRisk === 'function') updateMapRisk(cityStats);
}

// ── HELPERS ───────────────────────────────────────────────
function riskBadge(level) {
  const map = {
    HIGH:   ['risk-high',   '🔴 ALTO'],
    MEDIUM: ['risk-medium', '🟡 MEDIO'],
    LOW:    ['risk-low',    '🟢 BAJO'],
  };
  const [cls, label] = map[level] || map.LOW;
  return `<span class="risk-badge ${cls}">${label}</span>`;
}

function humanAction(action) {
  const map = {
    REAGENDAR_SMS:  '📱 Reagendar SMS',
    CAMBIAR_FRANJA: '🕐 Cambiar franja',
    ENTREGA_NORMAL: '✅ Normal',
  };
  return map[action] || action || '—';
}

function humanZoneType(zt) {
  const map = {
    residential:    'Residencial',
    offices:        'Oficinas',
    historic_center:'Centro histórico',
    industrial:     'Industrial',
  };
  return map[zt] || zt || '—';
}

function humanProduct(pt) {
  const map = {
    standard:           '📦 Estándar',
    fragile:            '⚠️ Frágil',
    bulky:              '🏗️ Voluminoso',
    high_value:         '💎 Alto valor',
    signature_required: '✍️ Firma requerida',
  };
  return map[pt] || pt || '—';
}

function buildReasonText(row) {
  const factors = [];
  if (row.weather_rain)             factors.push('🌧️ Lluvia');
  if (row.is_retry)                 factors.push('🔁 Reintento');
  if (row.zone_type === 'historic_center') factors.push('🏛️ Centro histórico');
  if (row.driver_quality_score < 0.5) factors.push('👷 Conductor bajo');
  if (row.recipient_failure_rate > 0.5) factors.push('📬 Dest. problemático');
  if (row.num_previous_attempts > 1) factors.push(`🔄 ${row.num_previous_attempts} intentos`);
  if (row.is_fragile)               factors.push('⚠️ Frágil');
  return factors.length ? factors.join(' · ') : '<span style="color:var(--text-muted)">—</span>';
}

function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''; }

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
