import { api } from "../api.js";
import { REFRESH_MS } from "../config.js";
import { escapeHtml, relativeTime, shortKey, titleCase } from "../format.js";
import { poll } from "../poll.js";

function alertRows(alerts) {
  if (!alerts.length) {
    return `<tr><td colspan="7" class="empty">No alerts match the current filter.</td></tr>`;
  }
  return alerts
    .map((alert) => {
      const actions =
        alert.status === "resolved"
          ? ""
          : `${alert.status === "open" ? `<button class="small" data-ack="${alert.id}">Ack</button> ` : ""}<button class="small" data-resolve="${alert.id}">Resolve</button>`;
      return `<tr>
        <td><span class="badge badge-${alert.severity}">${alert.severity}</span></td>
        <td>${escapeHtml(shortKey(alert.device_key))}<div class="muted">${escapeHtml(alert.rack_key.split("/").slice(1).join(" / "))}</div></td>
        <td>${titleCase(alert.metric)}<div class="muted">${alert.kind}</div></td>
        <td>${escapeHtml(alert.message)}</td>
        <td class="muted">${relativeTime(alert.raised_at)}</td>
        <td><span class="badge badge-${alert.status}">${alert.status}</span></td>
        <td class="actions">${actions}</td>
      </tr>`;
    })
    .join("");
}

function rcaCards(results) {
  if (!results.length) {
    return `<div class="empty">No analysis yet. Run it against the open alerts.</div>`;
  }
  const runs = new Map();
  results.forEach((row) => {
    if (!runs.has(row.run_id)) {
      runs.set(row.run_id, []);
    }
    runs.get(row.run_id).push(row);
  });
  return [...runs.values()]
    .slice(0, 4)
    .map((rows) => {
      const top = rows[0];
      const others = rows
        .slice(1)
        .map((row) => `<li><span>${escapeHtml(shortKey(row.root_cause_key) || row.root_cause_key)}</span><span class="mono muted">${row.score.toFixed(2)}</span></li>`)
        .join("");
      return `<div class="rca-card">
        <div class="rca-top">
          <span class="badge badge-critical">${top.fault_kind ? titleCase(top.fault_kind) : "Unclassified"}</span>
          <span class="mono muted">${relativeTime(top.created_at)}</span>
        </div>
        <h3>${escapeHtml(top.root_cause_key)}</h3>
        <p class="muted">${escapeHtml(top.summary || "")}</p>
        <div class="bar"><span style="width:${Math.round(top.score * 100)}%;background:var(--accent)"></span></div>
        <div class="rca-meta mono muted"><span>confidence ${top.score.toFixed(2)}</span><span>alerts ${top.alert_ids.length}</span></div>
        ${others ? `<ul class="rca-others">${others}</ul>` : ""}
      </div>`;
    })
    .join("");
}

export async function mount(container, { toast }) {
  const filters = { status: "", severity: "" };
  container.innerHTML = `
    <div class="grid grid-two">
      <div class="card">
        <div class="card-head"><h2>Alerts</h2>
          <div class="controls" style="margin:0">
            <select id="status"><option value="">Any status</option><option value="open">Open</option><option value="acknowledged">Acknowledged</option><option value="resolved">Resolved</option></select>
            <select id="severity"><option value="">Any severity</option><option value="critical">Critical</option><option value="warning">Warning</option></select>
          </div>
        </div>
        <table class="table"><thead><tr><th>Severity</th><th>Device</th><th>Metric</th><th>Message</th><th>Raised</th><th>Status</th><th></th></tr></thead><tbody id="alert-rows"></tbody></table>
      </div>
      <div class="card">
        <div class="card-head"><h2>Root cause analysis</h2><button class="primary small" id="analyze">Run analysis</button></div>
        <div id="rca"></div>
      </div>
    </div>`;
  const rows = container.querySelector("#alert-rows");

  async function refreshAlerts() {
    const params = {};
    if (filters.status) {
      params.status = filters.status;
    }
    if (filters.severity) {
      params.severity = filters.severity;
    }
    rows.innerHTML = alertRows(await api.alerts({ ...params, limit: 100 }));
  }

  async function refreshRca() {
    container.querySelector("#rca").innerHTML = rcaCards(await api.rca());
  }

  container.querySelector("#status").addEventListener("change", (event) => {
    filters.status = event.target.value;
    refreshAlerts();
  });
  container.querySelector("#severity").addEventListener("change", (event) => {
    filters.severity = event.target.value;
    refreshAlerts();
  });
  rows.addEventListener("click", async (event) => {
    const ack = event.target.dataset.ack;
    const resolve = event.target.dataset.resolve;
    if (!ack && !resolve) {
      return;
    }
    try {
      await (ack ? api.acknowledge(ack) : api.resolve(resolve));
      await refreshAlerts();
    } catch (error) {
      toast(`Update failed: ${error.message}`);
    }
  });
  container.querySelector("#analyze").addEventListener("click", async (event) => {
    event.target.disabled = true;
    try {
      const results = await api.analyze();
      toast(results.length ? `Analysis found ${new Set(results.map((row) => row.run_id)).size} incident(s)` : "No open alerts to analyse");
      await refreshRca();
    } catch (error) {
      toast(`Analysis failed: ${error.message}`);
    } finally {
      event.target.disabled = false;
    }
  });

  const stopAlerts = poll(refreshAlerts, REFRESH_MS.alerts);
  const stopRca = poll(refreshRca, REFRESH_MS.alerts * 2);
  return {
    unmount() {
      stopAlerts();
      stopRca();
    },
  };
}
