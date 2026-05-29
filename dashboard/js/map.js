/* ============================================================
   RetailCore Logistics · Mapa de Zonas de Riesgo (Leaflet)
   ============================================================ */

const CITIES = {
  madrid:    { lat: 40.4168, lng: -3.7038, label: 'Madrid' },
  barcelona: { lat: 41.3851, lng:  2.1734, label: 'Barcelona' },
  valencia:  { lat: 39.4699, lng: -0.3763, label: 'Valencia' },
  sevilla:   { lat: 37.3891, lng: -5.9845, label: 'Sevilla' },
};

let _map = null;
let _markers = {};

function initMap() {
  if (_map) return;

  _map = L.map('map-container', { zoomControl: true, scrollWheelZoom: false }).setView([39.9, -3.5], 6);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(_map);

  Object.entries(CITIES).forEach(([key, city]) => {
    const circle = L.circleMarker([city.lat, city.lng], {
      radius: 18,
      color: '#fff',
      weight: 2,
      fillColor: '#94a3b8',
      fillOpacity: 0.7,
    }).addTo(_map);

    const label = L.divIcon({
      className: '',
      html: `<div style="background:rgba(30,41,59,.8);color:#fff;padding:3px 8px;border-radius:6px;font-size:11px;font-weight:700;white-space:nowrap;margin-top:24px">${city.label}</div>`,
      iconAnchor: [0, 0],
    });
    L.marker([city.lat, city.lng], { icon: label, interactive: false }).addTo(_map);

    _markers[key] = circle;
  });
}

function updateMapRisk(cityStats) {
  if (!_map) initMap();

  const sidebar = document.getElementById('city-cards');
  sidebar.innerHTML = '';

  Object.entries(cityStats).forEach(([city, stats]) => {
    const coord = CITIES[city];
    if (!coord || !_markers[city]) return;

    const total  = stats.total || 0;
    const high   = stats.high  || 0;
    const medium = stats.medium|| 0;
    const low    = stats.low   || 0;
    const pct    = total > 0 ? high / total : 0;

    const color  = pct > 0.5 ? '#ef4444' : pct > 0.2 ? '#f59e0b' : '#22c55e';
    const radius = Math.max(12, Math.min(36, 12 + total * 0.6));

    _markers[city].setStyle({ fillColor: color, radius });
    _markers[city].setPopupContent(buildPopup(city, stats)).openPopup && _markers[city].unbindPopup().bindPopup(buildPopup(city, stats));

    // Sidebar card
    const cardClass = pct > 0.5 ? 'risk-high-card' : pct > 0.2 ? 'risk-medium-card' : 'risk-low-card';
    sidebar.insertAdjacentHTML('beforeend', `
      <div class="city-card ${cardClass}">
        <div class="city-card-name">${coord.label}</div>
        <div class="city-card-stats">
          <div class="city-card-stat"><strong>${total}</strong>Total</div>
          <div class="city-card-stat"><strong style="color:var(--high)">${high}</strong>Alto</div>
          <div class="city-card-stat"><strong>${(pct*100).toFixed(0)}%</strong>% riesgo</div>
        </div>
      </div>
    `);
  });
}

function buildPopup(city, stats) {
  const coord = CITIES[city];
  const total  = stats.total  || 0;
  const high   = stats.high   || 0;
  const medium = stats.medium || 0;
  const low    = stats.low    || 0;
  const pct    = total > 0 ? ((high / total) * 100).toFixed(0) : 0;
  return `
    <div style="min-width:170px">
      <strong style="font-size:1rem">${coord.label}</strong><br>
      <table style="font-size:.8rem;margin-top:.4rem;width:100%">
        <tr><td>🔴 Alto</td><td><b>${high}</b></td></tr>
        <tr><td>🟡 Medio</td><td><b>${medium}</b></td></tr>
        <tr><td>🟢 Bajo</td><td><b>${low}</b></td></tr>
        <tr><td>Total</td><td><b>${total}</b></td></tr>
        <tr><td>% riesgo</td><td><b>${pct}%</b></td></tr>
      </table>
    </div>
  `;
}
