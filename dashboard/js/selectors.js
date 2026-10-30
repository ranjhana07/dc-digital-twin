import { api } from "./api.js";
import { escapeHtml, shortKey, titleCase } from "./format.js";

const TYPE_ORDER = ["server", "pdu", "transceiver", "switch", "crac"];

export async function loadDeviceOptions() {
  const devices = await api.devices();
  const grouped = {};
  devices.forEach((device) => {
    (grouped[device.device_type] = grouped[device.device_type] || []).push(device);
  });
  return TYPE_ORDER.filter((type) => grouped[type]).map((type) => ({ type, devices: grouped[type] }));
}

export function renderDeviceSelect(select, groups, selected) {
  select.innerHTML = groups
    .map(
      (group) =>
        `<optgroup label="${titleCase(group.type)}s">${group.devices
          .map(
            (device) =>
              `<option value="${escapeHtml(device.device_key)}" ${device.device_key === selected ? "selected" : ""}>${escapeHtml(
                shortKey(device.device_key) || device.device_key
              )} (${escapeHtml(device.hall)})</option>`
          )
          .join("")}</optgroup>`
    )
    .join("");
}

export function renderMetricSelect(select, metrics, selected) {
  select.innerHTML = metrics
    .map((metric) => `<option value="${metric}" ${metric === selected ? "selected" : ""}>${titleCase(metric)}</option>`)
    .join("");
}

export function deviceTypeOf(groups, deviceKey) {
  const group = groups.find((entry) => entry.devices.some((device) => device.device_key === deviceKey));
  return group ? group.type : null;
}
