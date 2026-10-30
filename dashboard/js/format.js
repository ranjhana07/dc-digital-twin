const UNIT_LABELS = {
  C: "°C",
  W: "W",
  rpm: "rpm",
  dBm: "dBm",
  A: "A",
  "%": "%",
  ratio: "",
};

export function titleCase(text) {
  return text.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function unitLabel(unit) {
  return unit in UNIT_LABELS ? UNIT_LABELS[unit] : unit;
}

export function formatValue(metric, value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  if (metric === "pre_fec_ber") {
    return value.toExponential(1);
  }
  if (metric === "fan_rpm" || metric === "power_w") {
    return Math.round(value).toLocaleString();
  }
  if (metric === "cpu_load") {
    return `${Math.round(value * 100)}%`;
  }
  return value.toFixed(1);
}

export function shortKey(deviceKey) {
  const parts = deviceKey.split("/");
  return parts.slice(2).join("/");
}

export function relativeTime(iso) {
  const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m ago`;
  }
  if (seconds < 86400) {
    return `${Math.floor(seconds / 3600)}h ago`;
  }
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function clockText(date = new Date()) {
  return date.toISOString().slice(11, 19) + " UTC";
}

export function scoreColor(score) {
  if (score >= 85) {
    return "var(--ok)";
  }
  if (score >= 60) {
    return "var(--warn)";
  }
  return "var(--crit)";
}

export function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
