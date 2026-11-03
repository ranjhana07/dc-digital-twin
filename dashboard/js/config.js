const globals = typeof window === "undefined" ? {} : window;

export const API_BASE = globals.TWIN_API_BASE || "/api";

export function wsUrl(path) {
  const base = globals.TWIN_WS_BASE || `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;
  return `${base}${path}`;
}

export const REFRESH_MS = {
  overview: 5000,
  alerts: 7000,
  topology: 8000,
  forecasts: 15000,
};

export const COLORS = {
  accent: "#2dd4bf",
  ok: "#3ecf8e",
  warn: "#f5a524",
  crit: "#f2545b",
  info: "#6aa7ff",
  muted: "#7f8c9b",
  grid: "#212b38",
};
