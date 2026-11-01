import { api } from "../api.js";
import { baseOptions, createChart, metricTitle, thresholdAnnotations } from "../charts.js";
import { COLORS, REFRESH_MS } from "../config.js";
import { escapeHtml, shortKey, titleCase } from "../format.js";
import { poll } from "../poll.js";
import { deviceTypeOf, loadDeviceOptions, renderDeviceSelect, renderMetricSelect } from "../selectors.js";

const FORECAST_TARGETS = {
  server: ["inlet_temp", "outlet_temp"],
  pdu: ["power_w", "load_pct"],
  transceiver: ["rx_power_dbm", "pre_fec_ber"],
};
const HISTORY_MINUTES = 60;

function riskTone(severity) {
  return severity === "critical" ? "crit" : severity === "warning" ? "warn" : "ok";
}

function riskPanel(risk) {
  if (!risk) {
    return `<div class="empty">No risk score for this series yet.</div>`;
  }
  const tone = riskTone(risk.severity);
  const breach = risk.breach_step ? `Expected to cross a limit in about ${risk.breach_step} min.` : "No limit crossing expected in the horizon.";
  return `<div class="risk-score ${tone}"><span class="mono">${(risk.risk * 100).toFixed(0)}</span><span class="muted">/ 100</span></div>
    <p class="muted">${breach}</p>
    <dl class="facts">
      <dt>P(warning)</dt><dd class="mono">${(risk.p_warn * 100).toFixed(0)}%</dd>
      <dt>P(critical)</dt><dd class="mono">${(risk.p_crit * 100).toFixed(0)}%</dd>
      <dt>Trend</dt><dd class="mono">${risk.rate_per_hour >= 0 ? "+" : ""}${risk.rate_per_hour.toFixed(2)} / h</dd>
      <dt>Residual z</dt><dd class="mono">${risk.z_score.toFixed(1)}</dd>
    </dl>`;
}

function riskRows(rows) {
  const top = rows.slice(0, 10);
  if (!top.length) {
    return `<div class="empty">Waiting for the inference service.</div>`;
  }
  return `<table class="table"><tbody>${top
    .map(
      (row) => `<tr class="pick" data-device="${escapeHtml(row.device_key)}" data-metric="${row.metric}">
        <td>${escapeHtml(shortKey(row.device_key))}</td>
        <td class="muted">${titleCase(row.metric)}</td>
        <td class="num">${(row.risk * 100).toFixed(0)}</td>
      </tr>`
    )
    .join("")}</tbody></table>`;
}

export async function mount(container, { meta }) {
  const groups = (await loadDeviceOptions()).filter((group) => FORECAST_TARGETS[group.type]);
  if (!groups.length) {
    container.innerHTML = `<div class="card empty">No forecastable devices registered yet.</div>`;
    return {};
  }
  const state = { deviceKey: groups[0].devices[0].device_key, metric: FORECAST_TARGETS[groups[0].type][0], chart: null };
  container.innerHTML = `
    <div class="controls"><select id="device" aria-label="Device"></select><select id="metric" aria-label="Metric"></select><span class="muted" id="model"></span></div>
    <div class="grid grid-two">
      <div class="card"><div class="card-head"><h2 id="chart-title"></h2><span class="muted">history and forecast with 95% band</span></div><div id="chart" class="chart"></div></div>
      <div class="grid">
        <div class="card"><div class="card-head"><h2>Risk</h2></div><div id="risk-panel"></div></div>
        <div class="card"><div class="card-head"><h2>Highest risk series</h2></div><div id="ranking"></div></div>
      </div>
    </div>`;
  const deviceSelect = container.querySelector("#device");
  const metricSelect = container.querySelector("#metric");

  async function refresh() {
    const type = deviceTypeOf(groups, state.deviceKey);
    const threshold = meta.thresholds.find((item) => item.device_type === type && item.metric === state.metric);
    const [history, forecast, risks] = await Promise.all([
      api.series(state.deviceKey, state.metric, HISTORY_MINUTES, 60),
      api.forecast(state.deviceKey, state.metric),
      api.risk(0, 200),
    ]);
    const actual = history.points.map((point) => [new Date(point.ts).getTime(), point.avg]);
    const predicted = forecast.map((point) => [new Date(point.target_ts).getTime(), point.predicted]);
    const band = forecast.map((point) => ({ x: new Date(point.target_ts).getTime(), y: [point.lower, point.upper] }));
    if (actual.length && predicted.length) {
      predicted.unshift(actual[actual.length - 1]);
    }
    const options = baseOptions(state.metric, 320);
    options.chart.type = "rangeArea";
    options.chart.animations = { enabled: false };
    options.series = [
      { type: "line", name: "Actual", data: actual },
      { type: "line", name: "Forecast", data: predicted },
      { type: "rangeArea", name: "95% band", data: band },
    ];
    options.colors = [COLORS.accent, COLORS.warn, COLORS.warn];
    options.stroke = { width: [2, 2, 0], dashArray: [0, 4, 0], curve: "smooth" };
    options.fill = { opacity: [1, 1, 0.22] };
    options.annotations = thresholdAnnotations(threshold);
    if (state.metric === "pre_fec_ber") {
      options.yaxis = { ...options.yaxis, logarithmic: true, forceNiceScale: false };
    }
    if (state.chart) {
      state.chart.destroy();
    }
    state.chart = createChart(container.querySelector("#chart"), options);
    container.querySelector("#chart-title").textContent = `${metricTitle(state.metric)} - ${shortKey(state.deviceKey)}`;
    container.querySelector("#model").textContent = forecast.length ? `model ${forecast[0].model_version}, horizon ${forecast.length} min` : "no forecast yet";
    const current = risks.find((row) => row.device_key === state.deviceKey && row.metric === state.metric);
    container.querySelector("#risk-panel").innerHTML = riskPanel(current);
    container.querySelector("#ranking").innerHTML = riskRows(risks);
  }

  function syncMetrics() {
    const type = deviceTypeOf(groups, state.deviceKey);
    const metrics = FORECAST_TARGETS[type];
    if (!metrics.includes(state.metric)) {
      state.metric = metrics[0];
    }
    renderMetricSelect(metricSelect, metrics, state.metric);
  }

  deviceSelect.addEventListener("change", () => {
    state.deviceKey = deviceSelect.value;
    syncMetrics();
    refresh();
  });
  metricSelect.addEventListener("change", () => {
    state.metric = metricSelect.value;
    refresh();
  });
  container.querySelector("#ranking").addEventListener("click", (event) => {
    const row = event.target.closest("tr.pick");
    if (!row) {
      return;
    }
    state.deviceKey = row.dataset.device;
    state.metric = row.dataset.metric;
    renderDeviceSelect(deviceSelect, groups, state.deviceKey);
    syncMetrics();
    refresh();
  });
  renderDeviceSelect(deviceSelect, groups, state.deviceKey);
  syncMetrics();
  const stop = poll(refresh, REFRESH_MS.forecasts);
  return {
    unmount() {
      stop();
      if (state.chart) {
        state.chart.destroy();
      }
    },
  };
}
