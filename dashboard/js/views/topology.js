import { api } from "../api.js";
import { REFRESH_MS } from "../config.js";
import { escapeHtml, formatValue, scoreColor, titleCase } from "../format.js";
import { poll } from "../poll.js";

const RACK = { w: 104, h: 150, gap: 20 };
const CRAC = { w: 128, h: 36, gap: 20 };
const PAD = 24;
const HEADER = 78;

function groupByHall(nodes) {
  const halls = new Map();
  nodes.forEach((node) => {
    if (!halls.has(node.hall_key)) {
      halls.set(node.hall_key, { key: node.hall_key, racks: [], cracs: [] });
    }
    const hall = halls.get(node.hall_key);
    if (node.kind === "rack") {
      hall.racks.push(node);
    } else if (node.type === "crac") {
      hall.cracs.push(node);
    }
  });
  return [...halls.values()].sort((a, b) => a.key.localeCompare(b.key));
}

function rackPosition(rack) {
  return {
    x: PAD + rack.grid_col * (RACK.w + RACK.gap),
    y: HEADER + rack.grid_row * (RACK.h + RACK.gap),
  };
}

function cracPosition(index) {
  return { x: PAD + index * (CRAC.w + CRAC.gap), y: 14 };
}

function renderHall(hall, health, cooling) {
  const cols = Math.max(...hall.racks.map((rack) => rack.grid_col)) + 1;
  const rows = Math.max(...hall.racks.map((rack) => rack.grid_row)) + 1;
  const width = Math.max(cols * (RACK.w + RACK.gap), hall.cracs.length * (CRAC.w + CRAC.gap)) + PAD * 2 - RACK.gap;
  const height = HEADER + rows * (RACK.h + RACK.gap) + 4;
  const cracIndex = new Map(hall.cracs.map((crac, index) => [crac.id, index]));
  const rackById = new Map(hall.racks.map((rack) => [rack.id, rack]));

  const links = hall.racks
    .map((rack) => {
      const cracId = cooling.get(rack.id);
      if (!cracId || !cracIndex.has(cracId)) {
        return "";
      }
      const from = cracPosition(cracIndex.get(cracId));
      const to = rackPosition(rack);
      const x1 = from.x + CRAC.w / 2;
      const y1 = from.y + CRAC.h;
      const x2 = to.x + RACK.w / 2;
      return `<path class="link" data-crac="${escapeHtml(cracId)}" data-rack="${escapeHtml(rack.id)}" d="M${x1} ${y1} C ${x1} ${y1 + 26}, ${x2} ${to.y - 26}, ${x2} ${to.y}"/>`;
    })
    .join("");

  const cracs = hall.cracs
    .map((crac, index) => {
      const { x, y } = cracPosition(index);
      return `<g class="crac" data-crac="${escapeHtml(crac.id)}" transform="translate(${x} ${y})">
        <rect width="${CRAC.w}" height="${CRAC.h}" rx="8"/>
        <circle cx="18" cy="${CRAC.h / 2}" r="8" class="fan"/>
        <text x="36" y="${CRAC.h / 2 + 4}">${escapeHtml(crac.label.toUpperCase())}</text>
      </g>`;
    })
    .join("");

  const racks = hall.racks
    .map((rack) => {
      const { x, y } = rackPosition(rack);
      const item = health.get(rack.id) || { score: 100, status: "healthy", open_alerts: 0 };
      const color = scoreColor(item.score);
      const slots = Array.from({ length: 8 }, (_, slot) => `<rect x="12" y="${52 + slot * 11}" width="${RACK.w - 24}" height="6" rx="2" class="slot"/>`).join("");
      return `<g class="rack" data-rack="${escapeHtml(rack.id)}" data-crac="${escapeHtml(cooling.get(rack.id) || "")}" transform="translate(${x} ${y})" tabindex="0">
        <rect class="rack-body" width="${RACK.w}" height="${RACK.h}" rx="10" style="stroke:${color}"/>
        <rect class="rack-fill" width="${RACK.w}" height="${RACK.h}" rx="10" style="fill:${color}"/>
        <text class="rack-label" x="12" y="22">${escapeHtml(rack.label.toUpperCase())}</text>
        <text class="rack-score" x="12" y="44" style="fill:${color}">${item.score.toFixed(0)}</text>
        ${slots}
        ${item.open_alerts ? `<g transform="translate(${RACK.w - 18} 18)"><circle r="10" class="alert-dot"/><text class="alert-count" y="4">${item.open_alerts}</text></g>` : ""}
      </g>`;
    })
    .join("");

  return `<div class="card hall">
    <div class="card-head"><h2>${escapeHtml(hall.key)}</h2><span class="muted">${hall.racks.length} racks, ${hall.cracs.length} cooling units</span></div>
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Rack layout for ${escapeHtml(hall.key)}">${links}${cracs}${racks}</svg>
  </div>`;
}

function breachClass(meta, type, metric, value) {
  const threshold = meta.thresholds.find((item) => item.device_type === type && item.metric === metric);
  if (!threshold) {
    return "";
  }
  const past = (limit) => (threshold.direction === "high" ? value >= limit : value <= limit);
  if (past(threshold.crit)) {
    return "crit";
  }
  return past(threshold.warn) ? "warn" : "";
}

function renderDetail(rackKey, devices, readings, meta) {
  const byDevice = new Map();
  readings.forEach((reading) => {
    if (!byDevice.has(reading.device_key)) {
      byDevice.set(reading.device_key, []);
    }
    byDevice.get(reading.device_key).push(reading);
  });
  const body = devices
    .map((device) => {
      const cells = (byDevice.get(device.device_key) || [])
        .sort((a, b) => a.metric.localeCompare(b.metric))
        .map((reading) => `<span class="chip ${breachClass(meta, device.device_type, reading.metric, reading.value)}">${titleCase(reading.metric)} <b class="mono">${formatValue(reading.metric, reading.value)}</b></span>`)
        .join("");
      return `<tr><td class="mono">${escapeHtml(device.code)}</td><td class="muted">${device.device_type}</td><td class="chips">${cells || '<span class="muted">no recent data</span>'}</td></tr>`;
    })
    .join("");
  return `<div class="card-head"><h2>${escapeHtml(rackKey)}</h2><button class="small" id="close-detail">Close</button></div>
    <table class="table"><thead><tr><th>Device</th><th>Type</th><th>Latest readings</th></tr></thead><tbody>${body}</tbody></table>`;
}

export async function mount(container, { meta }) {
  container.innerHTML = `
    <div class="legend"><span><i style="background:var(--ok)"></i>Healthy 85+</span><span><i style="background:var(--warn)"></i>Degraded 60+</span><span><i style="background:var(--crit)"></i>Critical</span><span class="muted">Hover a rack or cooling unit to see what it depends on</span></div>
    <div id="halls" class="halls"></div>
    <div id="detail" class="card detail" hidden></div>`;
  const hallsNode = container.querySelector("#halls");
  let graph = null;

  async function refresh() {
    if (!graph) {
      graph = await api.topology();
    }
    const racks = await api.healthRacks();
    const health = new Map(racks.map((rack) => [rack.rack_key, rack]));
    const cooling = new Map(graph.edges.filter((edge) => edge.relation === "cooled_by").map((edge) => [edge.src, edge.dst]));
    const halls = groupByHall(graph.nodes).filter((hall) => hall.racks.length);
    hallsNode.innerHTML = halls.map((hall) => renderHall(hall, health, cooling)).join("");
  }

  function highlight(target) {
    const rackNode = target.closest(".rack");
    const cracNode = target.closest(".crac");
    const svg = target.closest("svg");
    if (!svg) {
      return;
    }
    svg.querySelectorAll(".link").forEach((link) => {
      const hit = (rackNode && link.dataset.rack === rackNode.dataset.rack) || (cracNode && link.dataset.crac === cracNode.dataset.crac);
      link.classList.toggle("on", Boolean(hit));
    });
    svg.querySelectorAll(".rack").forEach((rack) => {
      const dim = cracNode && rack.dataset.crac !== cracNode.dataset.crac;
      rack.classList.toggle("dim", Boolean(dim));
    });
  }

  hallsNode.addEventListener("mouseover", (event) => highlight(event.target));
  hallsNode.addEventListener("mouseout", (event) => {
    const svg = event.target.closest("svg");
    if (svg) {
      svg.querySelectorAll(".link.on").forEach((link) => link.classList.remove("on"));
      svg.querySelectorAll(".rack.dim").forEach((rack) => rack.classList.remove("dim"));
    }
  });
  const detailNode = container.querySelector("#detail");
  let selected = null;

  async function showDetail(rackKey) {
    selected = rackKey;
    const [devices, readings] = await Promise.all([api.devices({ rack: rackKey }), api.latest({ rack_key: rackKey })]);
    detailNode.innerHTML = renderDetail(rackKey, devices, readings, meta);
    detailNode.hidden = false;
    detailNode.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  hallsNode.addEventListener("click", (event) => {
    const rack = event.target.closest(".rack");
    if (rack) {
      showDetail(rack.dataset.rack);
    }
  });
  hallsNode.addEventListener("keydown", (event) => {
    const rack = event.target.closest(".rack");
    if (rack && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      showDetail(rack.dataset.rack);
    }
  });
  detailNode.addEventListener("click", (event) => {
    if (event.target.id === "close-detail") {
      selected = null;
      detailNode.hidden = true;
    }
  });
  const stop = poll(async () => {
    await refresh();
    if (selected) {
      await showDetail(selected);
    }
  }, REFRESH_MS.topology);
  return { unmount: stop };
}
