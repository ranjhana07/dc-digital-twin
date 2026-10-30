import { API_BASE } from "./config.js";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail || detail;
    } catch (error) {
      detail = response.statusText;
    }
    throw new ApiError(response.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json();
}

function query(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, value);
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  meta: () => request("/meta"),
  sites: () => request("/sites"),
  racks: (hall) => request(`/racks${query({ hall })}`),
  devices: (filters = {}) => request(`/devices${query(filters)}`),
  topology: () => request("/topology"),
  latest: (filters = {}) => request(`/telemetry/latest${query(filters)}`),
  series: (deviceKey, metric, minutes, bucketSeconds) => {
    const end = new Date();
    const start = new Date(end.getTime() - minutes * 60000);
    return request(
      `/telemetry/series${query({
        device_key: deviceKey,
        metric,
        start: start.toISOString(),
        end: end.toISOString(),
        bucket_s: bucketSeconds,
      })}`
    );
  },
  healthSummary: () => request("/health/summary"),
  healthRacks: () => request("/health/racks"),
  offenders: (limit = 8) => request(`/health/offenders${query({ limit })}`),
  forecast: (deviceKey, metric) => request(`/predictions${query({ device_key: deviceKey, metric })}`),
  risk: (minRisk = 0, limit = 50) => request(`/predictions/risk${query({ min_risk: minRisk, limit })}`),
  alerts: (filters = {}) => request(`/alerts${query(filters)}`),
  acknowledge: (id) => request(`/alerts/${id}/ack`, { method: "POST" }),
  resolve: (id) => request(`/alerts/${id}/resolve`, { method: "POST" }),
  rca: () => request("/rca"),
  analyze: () => request("/rca/analyze", { method: "POST" }),
};
