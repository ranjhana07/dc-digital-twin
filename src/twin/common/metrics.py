import math
from dataclasses import dataclass
from enum import StrEnum


class DeviceType(StrEnum):
    SERVER = "server"
    SWITCH = "switch"
    TRANSCEIVER = "transceiver"
    PDU = "pdu"
    CRAC = "crac"


DEVICE_METRICS: dict[DeviceType, tuple[str, ...]] = {
    DeviceType.SERVER: ("cpu_load", "power_w", "fan_rpm", "inlet_temp", "outlet_temp"),
    DeviceType.SWITCH: ("power_w", "fan_rpm", "inlet_temp"),
    DeviceType.TRANSCEIVER: ("rx_power_dbm", "tx_power_dbm", "module_temp", "pre_fec_ber"),
    DeviceType.PDU: ("power_w", "current_a", "load_pct"),
    DeviceType.CRAC: ("supply_temp", "return_temp", "fan_rpm", "power_w", "cooling_pct"),
}

UNITS: dict[str, str] = {
    "cpu_load": "ratio",
    "power_w": "W",
    "fan_rpm": "rpm",
    "inlet_temp": "C",
    "outlet_temp": "C",
    "module_temp": "C",
    "supply_temp": "C",
    "return_temp": "C",
    "rx_power_dbm": "dBm",
    "tx_power_dbm": "dBm",
    "pre_fec_ber": "ratio",
    "current_a": "A",
    "load_pct": "%",
    "cooling_pct": "%",
}

ALL_METRICS: frozenset[str] = frozenset(m for metrics in DEVICE_METRICS.values() for m in metrics)


@dataclass(frozen=True)
class Threshold:
    warn: float
    crit: float
    direction: str = "high"
    log_scale: bool = False

    def breached(self, value: float) -> str | None:
        if self.direction == "high":
            if value >= self.crit:
                return "critical"
            if value >= self.warn:
                return "warning"
        else:
            if value <= self.crit:
                return "critical"
            if value <= self.warn:
                return "warning"
        return None

    def severity_fraction(self, value: float) -> float:
        warn, crit, current = self.warn, self.crit, value
        if self.log_scale:
            warn, crit = math.log10(warn), math.log10(crit)
            current = math.log10(max(value, 1e-15))
        span = crit - warn
        if span == 0:
            return 0.0
        return min(max((current - warn) / span, 0.0), 1.5)


THRESHOLDS: dict[tuple[DeviceType, str], Threshold] = {
    (DeviceType.SERVER, "inlet_temp"): Threshold(27.0, 32.0),
    (DeviceType.SERVER, "outlet_temp"): Threshold(40.0, 48.0),
    (DeviceType.SERVER, "fan_rpm"): Threshold(3200.0, 2500.0, direction="low"),
    (DeviceType.SWITCH, "inlet_temp"): Threshold(27.0, 32.0),
    (DeviceType.TRANSCEIVER, "rx_power_dbm"): Threshold(-7.0, -9.5, direction="low"),
    (DeviceType.TRANSCEIVER, "module_temp"): Threshold(65.0, 75.0),
    (DeviceType.TRANSCEIVER, "pre_fec_ber"): Threshold(1e-6, 1e-4, log_scale=True),
    (DeviceType.PDU, "load_pct"): Threshold(80.0, 95.0),
    (DeviceType.CRAC, "supply_temp"): Threshold(22.0, 26.0),
    (DeviceType.CRAC, "return_temp"): Threshold(34.0, 40.0),
}


def threshold_for(device_type: DeviceType, metric: str) -> Threshold | None:
    return THRESHOLDS.get((device_type, metric))
