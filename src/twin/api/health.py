from collections import defaultdict
from collections.abc import Iterable

from twin.api.schemas import AlertOut, DeviceHealth, DeviceOut, HealthSummary, Offender, RackHealth, ReadingOut
from twin.common.metrics import DeviceType, threshold_for

ALERT_PENALTY = 5.0
MAX_ALERT_PENALTY = 20.0


def metric_penalty(device_type: DeviceType, metric: str, value: float) -> float:
    threshold = threshold_for(device_type, metric)
    if threshold is None or threshold.breached(value) is None:
        return 0.0
    return 0.35 + 0.65 * min(threshold.severity_fraction(value), 1.0)


def device_health(device_key: str, device_type: DeviceType, readings: dict[str, float]) -> DeviceHealth:
    worst_penalty, worst_metric, worst_value = 0.0, None, None
    for metric, value in readings.items():
        penalty = metric_penalty(device_type, metric, value)
        if penalty > worst_penalty:
            worst_penalty, worst_metric, worst_value = penalty, metric, value
    return DeviceHealth(
        device_key=device_key,
        device_type=device_type.value,
        score=round(100.0 * (1.0 - worst_penalty), 1),
        worst_metric=worst_metric,
        worst_value=worst_value,
    )


def status_for(score: float) -> str:
    if score >= 85.0:
        return "healthy"
    if score >= 60.0:
        return "degraded"
    return "critical"


def rack_health(rack_key: str, devices: list[DeviceHealth], open_alerts: int) -> RackHealth:
    if devices:
        scores = [device.score for device in devices]
        base = 0.6 * min(scores) + 0.4 * (sum(scores) / len(scores))
    else:
        base = 100.0
    score = max(base - min(open_alerts * ALERT_PENALTY, MAX_ALERT_PENALTY), 0.0)
    worst = min(devices, key=lambda device: device.score) if devices else None
    flagged = worst is not None and worst.score < 100.0
    return RackHealth(
        rack_key=rack_key,
        score=round(score, 1),
        status=status_for(score),
        device_count=len(devices),
        open_alerts=open_alerts,
        worst_device=worst.device_key if flagged else None,
        worst_metric=worst.worst_metric if flagged else None,
    )


class FleetHealth:
    def __init__(self, devices: Iterable[DeviceOut], readings: Iterable[ReadingOut], alerts: Iterable[AlertOut]) -> None:
        by_device: dict[str, dict[str, float]] = defaultdict(dict)
        for reading in readings:
            by_device[reading.device_key][reading.metric] = reading.value
        self.alert_counts: dict[str, int] = defaultdict(int)
        self.rack_alert_counts: dict[str, int] = defaultdict(int)
        self.severity_counts: dict[str, int] = defaultdict(int)
        for alert in alerts:
            if alert.status == "resolved":
                continue
            self.alert_counts[alert.device_key] += 1
            self.rack_alert_counts[alert.rack_key] += 1
            self.severity_counts[alert.severity] += 1
        self.devices: list[DeviceHealth] = []
        self.by_rack: dict[str, list[DeviceHealth]] = defaultdict(list)
        self.types: dict[str, DeviceType] = {}
        self.readings = by_device
        for device in devices:
            device_type = DeviceType(device.device_type)
            self.types[device.device_key] = device_type
            health = device_health(device.device_key, device_type, by_device.get(device.device_key, {}))
            self.devices.append(health)
            if device.rack_key:
                self.by_rack[device.rack_key].append(health)

    def racks(self) -> list[RackHealth]:
        return sorted(
            (rack_health(key, items, self.rack_alert_counts.get(key, 0)) for key, items in self.by_rack.items()),
            key=lambda rack: (rack.score, rack.rack_key),
        )

    def offenders(self, limit: int = 10) -> list[Offender]:
        flagged = [device for device in self.devices if device.worst_metric is not None]
        flagged.sort(key=lambda device: (device.score, device.device_key))
        return [
            Offender(
                device_key=device.device_key,
                device_type=device.device_type,
                metric=device.worst_metric,
                value=device.worst_value,
                score=device.score,
                open_alerts=self.alert_counts.get(device.device_key, 0),
            )
            for device in flagged[:limit]
        ]

    def summary(self) -> HealthSummary:
        racks = self.racks()
        counts = {"healthy": 0, "degraded": 0, "critical": 0}
        for rack in racks:
            counts[rack.status] += 1
        average = sum(rack.score for rack in racks) / len(racks) if racks else 100.0
        return HealthSummary(
            racks=len(racks),
            healthy=counts["healthy"],
            degraded=counts["degraded"],
            critical=counts["critical"],
            average_score=round(average, 1),
            open_alerts=dict(self.severity_counts),
        )
