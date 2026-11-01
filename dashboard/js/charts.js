import { COLORS } from "./config.js";
import { formatValue, titleCase } from "./format.js";

export function thresholdAnnotations(threshold) {
  if (!threshold) {
    return { yaxis: [] };
  }
  const line = (value, color, label) => ({
    y: value,
    borderColor: color,
    strokeDashArray: 4,
    label: {
      text: label,
      position: "left",
      textAnchor: "start",
      style: { color: "#0a0e13", background: color, fontSize: "10px", padding: { left: 4, right: 4, top: 1, bottom: 1 } },
    },
  });
  return { yaxis: [line(threshold.warn, COLORS.warn, "warn"), line(threshold.crit, COLORS.crit, "crit")] };
}

export function baseOptions(metric, height = 300) {
  return {
    chart: {
      height,
      type: "line",
      background: "transparent",
      foreColor: COLORS.muted,
      toolbar: { show: false },
      zoom: { enabled: false },
      animations: { enabled: true, easing: "linear", dynamicAnimation: { speed: 600 } },
      fontFamily: "inherit",
    },
    theme: { mode: "dark" },
    stroke: { width: 2, curve: "smooth" },
    grid: { borderColor: COLORS.grid, strokeDashArray: 3 },
    dataLabels: { enabled: false },
    legend: { show: true, position: "top", horizontalAlign: "right", labels: { colors: COLORS.muted } },
    xaxis: { type: "datetime", labels: { datetimeUTC: true, style: { colors: COLORS.muted } }, axisBorder: { show: false } },
    yaxis: {
      labels: {
        style: { colors: COLORS.muted },
        formatter: (value) => (value === undefined || value === null ? "" : formatValue(metric, value)),
      },
    },
    tooltip: { theme: "dark", x: { format: "HH:mm:ss" }, y: { formatter: (value) => formatValue(metric, value) } },
    noData: { text: "Waiting for data", style: { color: COLORS.muted } },
  };
}

export function createChart(element, options) {
  const chart = new ApexCharts(element, options);
  chart.render();
  return chart;
}

export function metricTitle(metric) {
  return titleCase(metric);
}
