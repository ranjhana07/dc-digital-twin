import { api } from "../api.js";
import { createChart, baseOptions, metricTitle, thresholdAnnotations } from "../charts.js";
import { COLORS } from "../config.js";
import { formatValue, titleCase } from "../format.js";
import { deviceTypeOf, loadDeviceOptions, renderDeviceSelect, renderMetricSelect } from "../selectors.js";

const WINDOW_MINUTES = 30;
const MAX_POINTS = 360;

function thresholdFor(meta, type, metric) {
  return meta.thresholds.find((item) => item.device_type === type && item.metric === metric);
}

export async function mount(container, { live, meta }) {
  const groups = await loadDeviceOptions();
  if (!groups.length) {
    container.innerHTML = `<div class="card empty">No devices registered yet.</div>`;
    return {};
  }
  const state = { deviceKey: groups[0].devices[0].device_key, metric: null, points: [], chart: null, loadId: 0 };
  container.innerHTML = `
    <div class="controls">
      <select id="device" aria-label="Device"></select>
      <select id="metric" aria-label="Metric"></select>
      <span class="muted" id="latest"></span>
    </div>
    <div class="card"><div class="card-head"><h2 id="chart-title"></h2><span class="muted">last ${WINDOW_MINUTES} min, streaming</span></div><div id="chart" class="chart"></div></div>
    <div class="grid grid-kpi" id="tiles" style="margin-top:16px"></div>`;
  const deviceSelect = container.querySelector("#device");
  const metricSelect = container.querySelector("#metric");
  const tiles = container.querySelector("#tiles");
  const latestNode = container.querySelector("#latest");
  const latestByMetric = {};

  function renderTiles(type) {
    tiles.innerHTML = meta.device_types[type]
      .map(
        (metric) => `<div class="card kpi"><div class="kpi-label">${titleCase(metric)}</div>
          <div class="kpi-value" data-tile="${metric}">${latestByMetric[metric] === undefined ? "-" : formatValue(metric, latestByMetric[metric])}</div></div>`
      )
      .join("");
  }

  async function load() {
    const loadId = ++state.loadId;
    const type = deviceTypeOf(groups, state.deviceKey);
    const metrics = meta.device_types[type];
    if (!metrics.includes(state.metric)) {
      state.metric = metrics[0];
    }
    renderMetricSelect(metricSelect, metrics, state.metric);
    Object.keys(latestByMetric).forEach((key) => delete latestByMetric[key]);
    renderTiles(type);
    container.querySelector("#chart-title").textContent = `${metricTitle(state.metric)} - ${state.deviceKey}`;
    const [series, latest] = await Promise.all([
      api.series(state.deviceKey, state.metric, WINDOW_MINUTES, 15),
      api.latest({ device_key: state.deviceKey }),
    ]);
    if (loadId !== state.loadId) {
      return;
    }
    latest.forEach((row) => {
      latestByMetric[row.metric] = row.value;
    });
    renderTiles(type);
    state.points = series.points.map((point) => [new Date(point.ts).getTime(), point.avg]);
    if (state.chart) {
      state.chart.destroy();
    }
    const options = baseOptions(state.metric);
    options.series = [{ name: metricTitle(state.metric), data: state.points }];
    options.colors = [COLORS.accent];
    options.annotations = thresholdAnnotations(thresholdFor(meta, type, state.metric));
    state.chart = createChart(container.querySelector("#chart"), options);
    live.setFilter({ device_key: state.deviceKey });
  }

  const unsubscribe = live.subscribe((message) => {
    if (message.type !== "telemetry") {
      return;
    }
    message.points.forEach((point) => {
      if (point.device_key !== state.deviceKey) {
        return;
      }
      latestByMetric[point.metric] = point.value;
      const tile = tiles.querySelector(`[data-tile="${point.metric}"]`);
      if (tile) {
        tile.textContent = formatValue(point.metric, point.value);
      }
      if (point.metric === state.metric) {
        state.points.push([new Date(point.ts).getTime(), point.value]);
      }
    });
    if (state.points.length > MAX_POINTS) {
      state.points = state.points.slice(-MAX_POINTS);
    }
    if (state.chart) {
      state.chart.updateSeries([{ data: state.points }], false);
    }
    latestNode.textContent = `updated ${new Date().toISOString().slice(11, 19)}`;
  });

  deviceSelect.addEventListener("change", () => {
    state.deviceKey = deviceSelect.value;
    load();
  });
  metricSelect.addEventListener("change", () => {
    state.metric = metricSelect.value;
    load();
  });
  renderDeviceSelect(deviceSelect, groups, state.deviceKey);
  await load();
  return {
    unmount() {
      unsubscribe();
      live.setFilter({});
      if (state.chart) {
        state.chart.destroy();
      }
    },
  };
}
