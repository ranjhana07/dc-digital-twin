import { api } from "./api.js";
import { clockText } from "./format.js";
import { LiveStream } from "./live.js";
import * as overview from "./views/overview.js";
import * as alerts from "./views/alerts.js";
import * as forecasts from "./views/forecasts.js";
import * as telemetry from "./views/telemetry.js";

const VIEWS = {
  overview: { module: overview, title: "Overview", subtitle: "Fleet health across all halls" },
  telemetry: { module: telemetry, title: "Live telemetry", subtitle: "Streaming readings for a single device" },
  forecasts: { module: forecasts, title: "Forecasts", subtitle: "GRU forecasts, confidence bands and risk" },
  alerts: { module: alerts, title: "Alerts and root cause", subtitle: "Open alerts ranked into probable causes" },
};

const container = document.getElementById("view");
const titleNode = document.getElementById("view-title");
const subtitleNode = document.getElementById("view-subtitle");
const pill = document.getElementById("live-pill");
const apiDot = document.getElementById("api-state");
const apiLabel = document.getElementById("api-label");
const toastNode = document.getElementById("toast");

let current = null;
let toastTimer = null;

export function toast(message) {
  toastNode.textContent = message;
  toastNode.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastNode.hidden = true;
  }, 3500);
}

const live = new LiveStream((state) => {
  pill.textContent = state === "open" ? "streaming" : "stream offline";
  pill.className = `pill ${state === "open" ? "pill-live" : "pill-idle"}`;
});

const context = { live, toast, meta: null };

async function navigate() {
  const name = location.hash.replace("#", "") || "overview";
  const view = VIEWS[name] || VIEWS.overview;
  if (current && current.unmount) {
    current.unmount();
  }
  document.querySelectorAll(".rail a").forEach((link) => {
    link.classList.toggle("active", link.dataset.view === name);
  });
  titleNode.textContent = view.title;
  subtitleNode.textContent = view.subtitle;
  container.innerHTML = "";
  current = await view.module.mount(container, context);
}

async function checkApi() {
  try {
    context.meta = context.meta || (await api.meta());
    apiDot.className = "dot dot-ok";
    apiLabel.textContent = "api online";
  } catch (error) {
    apiDot.className = "dot dot-bad";
    apiLabel.textContent = "api offline";
  }
}

function tickClock() {
  document.getElementById("clock").textContent = clockText();
}

window.addEventListener("hashchange", navigate);
setInterval(tickClock, 1000);
setInterval(checkApi, 10000);
tickClock();
checkApi().then(navigate);
