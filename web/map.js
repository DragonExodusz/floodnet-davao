const map = L.map("map", { minZoom: 8 }).setView([7.07, 125.61], 14);
const statusElement = document.getElementById("status");
const scenarioSelect = document.getElementById("scenario");
let roadsLayer = null;
let requestController = null;
let refreshTimer = null;
const roadsRenderer = L.canvas({ padding: 0.5 });

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

function riskColor(probability) {
  if (probability >= 0.75) return "#d84a4a";
  if (probability >= 0.5) return "#ed8b36";
  if (probability >= 0.25) return "#e8c547";
  return "#2e9d72";
}

function showStatus(message) {
  statusElement.textContent = message;
  statusElement.hidden = !message;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

async function loadRoads() {
  const zoom = map.getZoom();
  if (zoom < 10) {
    if (roadsLayer) map.removeLayer(roadsLayer);
    roadsLayer = null;
    showStatus("Zoom in to level 13 or closer to see road-level estimates.");
    return;
  }

  if (requestController) requestController.abort();
  requestController = new AbortController();
  const bounds = map.getBounds();
  const bbox = [
    bounds.getWest(),
    bounds.getSouth(),
    bounds.getEast(),
    bounds.getNorth(),
  ].join(",");
  const scenario = scenarioSelect.value;
  showStatus("Loading model estimates…");

  try {
    const response = await fetch(
      `/api/roads?bbox=${encodeURIComponent(bbox)}&scenario=${scenario}&zoom=${zoom}`,
      { signal: requestController.signal },
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load this map view.");

    if (roadsLayer) map.removeLayer(roadsLayer);
    roadsLayer = L.geoJSON(data, {
      renderer: roadsRenderer,
      style: (feature) => ({
        color: riskColor(feature.properties.risk),
        weight: 3,
        opacity: 0.88,
      }),
      onEachFeature: (feature, layer) => {
        const properties = feature.properties;
        const risk = (100 * properties.risk).toFixed(1);
        layer.bindPopup(
          `<div class="road-popup"><strong>${escapeHtml(properties.highway || "Road")}</strong>` +
          `<span>Estimated flood exposure: ${risk}%</span>` +
          `<span>Segment length: ${Number(properties.length_m).toFixed(0)} m</span></div>`,
        );
      },
    }).addTo(map);
    showStatus(`${data.count.toLocaleString()} road segments shown | ${scenarioSelect.options[scenarioSelect.selectedIndex].text}`);
  } catch (error) {
    if (error.name === "AbortError") return;
    showStatus(error.message);
  }
}

function scheduleRefresh() {
  window.clearTimeout(refreshTimer);
  refreshTimer = window.setTimeout(loadRoads, 180);
}

map.on("moveend", scheduleRefresh);
scenarioSelect.addEventListener("change", scheduleRefresh);
loadRoads();
