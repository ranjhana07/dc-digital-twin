import { api } from "../api.js";
import { REFRESH_MS } from "../config.js";
import { escapeHtml, formatValue, relativeTime, scoreColor, shortKey, titleCase } from "../format.js";
import { poll } from "../poll.js";

function kpi(label, value, sub, tone) {
  return `<div class="card kpi ${tone ? `is-${tone}` : ""}">
    <div class="kpi-label">${label}</div>
    <div class="kpi-value">${value}</div>
    <div class="kpi-sub">${sub}</div>
  </div>`;
}

function renderKpis(summary, risks) {
  const critical = summary.open_alerts.critical || 0;
  const warning = summary.open_alerts.warning || 0;
  const atRisk = risks.filter((row) => row.severity !== "ok").length;
  const tone = summary.critical ? "crit" : summary.degraded ? "warn" : "ok";
  return [
    kpi("Fleet health", summary.average_score.toFixed(0), `${summary.racks} racks monitored`, tone),
    kpi("Healthy racks", summary.healthy, `${summary.degraded} degraded, ${summary.critical} critical`, summary.critical ? "crit" : "ok"),
    kpi("Open alerts", critical + warning, `${critical} critical, ${warning} warning`, critical ? "crit" : warning ? "warn" : "ok"),
    kpi("Forecast risk", atRisk, "series predicted to cross a limit", atRisk ? "warn" : "ok"),
  ].join("");
}

function renderRacks(racks) {
  if (!racks.length) {
    return `<div class="empty">No rack data yet. Start the simulator and ingest worker.</div>`;
  }
  return racks
    .map((rack) => {
      const hint = rack.worst_metric ? `${shortKey(rack.worst_device)} ${titleCase(rack.worst_metric)}` : "all clear";
      return `<div class="rack-row">
        <a class="rack-name" href="#topology">${escapeHtml(rack.rack_key.split("/").slice(1).join(" / "))}</a>
        <div class="bar"><span style="width:${rack.score}%;background:${scoreColor(rack.score)}"></span></div>
        <span class="mono rack-score">${rack.score.toFixed(0)}</span>
        <span class="muted rack-hint">${escapeHtml(hint)}</span>
      </div>`;
    })
    .join("");
}

function renderOffenders(rows) {
  if (!rows.length) {
    return `<div class="empty">Nothing outside its limits.</div>`;
  }
  const body = rows
    .map(
      (row) => `<tr>
        <td>${escapeHtml(shortKey(row.device_key))}</td>
        <td class="muted">${titleCase(row.metric)}</td>
        <td class="num">${formatValue(row.metric, row.value)}</td>
        <td class="num" style="color:${scoreColor(row.score)}">${row.score.toFixed(0)}</td>
      </tr>`
    )
    .join("");
  return `<table class="table"><thead><tr><th>Device</th><th>Metric</th><th class="num">Value</th><th class="num">Score</th></tr></thead><tbody>${body}</tbody></table>`;
}

function renderRisk(rows) {
  const flagged = rows.filter((row) => row.risk >= 0.3).slice(0, 8);
  if (!flagged.length) {
    return `<div class="empty">No forecast breaches expected.</div>`;
  }
  const body = flagged
    .map(
      (row) => `<tr>
        <td>${escapeHtml(shortKey(row.device_key))}</td>
        <td class="muted">${titleCase(row.metric)}</td>
        <td class="num">${(row.risk * 100).toFixed(0)}%</td>
        <td class="num">${row.breach_step ? `${row.breach_step} min` : "-"}</td>
        <td><span class="badge badge-${row.severity}">${row.severity}</span></td>
      </tr>`
    )
    .join("");
  return `<table class="table"><thead><tr><th>Device</th><th>Metric</th><th class="num">Risk</th><th class="num">Breach in</th><th></th></tr></thead><tbody>${body}</tbody></table>`;
}

export async function mount(container) {
  container.innerHTML = `
    <div class="grid grid-kpi" id="kpis"></div>
    <div class="grid grid-two">
      <div class="card"><div class="card-head"><h2>Rack health</h2><span class="muted" id="racks-count"></span></div><div id="racks" class="rack-list"></div></div>
      <div class="grid">
        <div class="card"><div class="card-head"><h2>Top offenders</h2></div><div id="offenders"></div></div>
        <div class="card"><div class="card-head"><h2>Forecast risk</h2><span class="muted" id="risk-time"></span></div><div id="risk"></div></div>
      </div>
    </div>`;
  const stop = poll(async () => {
    const [summary, racks, offenders, risks] = await Promise.all([
      api.healthSummary(),
      api.healthRacks(),
      api.offenders(8),
      api.risk(0, 50),
    ]);
    container.querySelector("#kpis").innerHTML = renderKpis(summary, risks);
    container.querySelector("#racks").innerHTML = renderRacks(racks);
    container.querySelector("#racks-count").textContent = `${racks.length} racks`;
    container.querySelector("#offenders").innerHTML = renderOffenders(offenders);
    container.querySelector("#risk").innerHTML = renderRisk(risks);
    container.querySelector("#risk-time").textContent = risks.length ? `updated ${relativeTime(risks[0].computed_at)}` : "";
  }, REFRESH_MS.overview);
  return { unmount: stop };
}
