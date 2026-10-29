from datetime import datetime, timedelta, timezone

from twin.api.schemas import (
    AlertOut,
    DeviceOut,
    PointOut,
    PredictionOut,
    RackOut,
    RcaResultOut,
    ReadingOut,
    RiskOut,
    SeriesPoint,
    SiteOut,
    TopologyEdge,
    TopologyGraph,
    TopologyNode,
)
from twin.common.topology import Topology, build_topology
from twin.rca.engine import AlertRecord
from twin.rca.service import RcaRun, describe

NOW = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self, topology: Topology | None = None) -> None:
        self.topology_model = topology or build_topology(halls=1, racks_per_hall=4, servers_per_rack=2, xcvrs_per_switch=1)
        self.readings: dict[tuple[str, str], float] = {}
        self.history: dict[tuple[str, str], list[tuple[datetime, float]]] = {}
        self.alert_rows: list[AlertOut] = []
        self.prediction_rows: list[PredictionOut] = []
        self.risk_rows: list[RiskOut] = []
        self.rca_rows: list[RcaResultOut] = []
        self.live_batches: list[list[ReadingOut]] = []

    def set_reading(self, device_key: str, metric: str, value: float) -> None:
        self.readings[(device_key, metric)] = value

    def add_alert(self, alert_id: int, device_key: str, metric: str, severity: str, status: str = "open", minutes: int = 0) -> AlertOut:
        rack_key = device_key.rsplit("/", 1)[0]
        alert = AlertOut(
            id=alert_id,
            device_key=device_key,
            rack_key=rack_key,
            metric=metric,
            kind="threshold",
            severity=severity,
            status=status,
            message=f"{metric} out of range",
            risk_score=0.9,
            raised_at=NOW + timedelta(minutes=minutes),
        )
        self.alert_rows.append(alert)
        return alert

    async def list_sites(self) -> list[SiteOut]:
        halls = {(rack.site, rack.hall) for rack in self.topology_model.racks.values()}
        return [SiteOut(code="dc1", name="DC1", halls=len(halls), racks=len(self.topology_model.racks))]

    async def list_racks(self, hall: str | None = None) -> list[RackOut]:
        racks = []
        for rack in self.topology_model.racks.values():
            if hall and rack.hall != hall:
                continue
            racks.append(
                RackOut(
                    rack_key=rack.key,
                    site=rack.site,
                    hall=rack.hall,
                    code=rack.code,
                    grid_row=rack.grid_row,
                    grid_col=rack.grid_col,
                    device_count=len(self.topology_model.devices_in_rack(rack.key)),
                )
            )
        return racks

    def _device_out(self, device) -> DeviceOut:
        in_rack = device.rack != "hall"
        return DeviceOut(
            device_key=device.key,
            site=device.site,
            hall=device.hall,
            rack_key=device.rack_key if in_rack else None,
            code=device.code,
            device_type=device.type.value,
        )

    async def list_devices(self, rack_key: str | None = None, device_type: str | None = None) -> list[DeviceOut]:
        devices = [self._device_out(device) for device in self.topology_model.devices.values()]
        if rack_key:
            devices = [device for device in devices if device.rack_key == rack_key]
        if device_type:
            devices = [device for device in devices if device.device_type == device_type]
        return devices

    async def get_device(self, device_key: str) -> DeviceOut | None:
        device = self.topology_model.devices.get(device_key)
        return self._device_out(device) if device else None

    async def topology(self) -> TopologyGraph:
        nodes = [
            TopologyNode(
                id=rack.key, kind="rack", label=rack.code, type="rack", hall_key=f"{rack.site}/{rack.hall}",
                grid_row=rack.grid_row, grid_col=rack.grid_col,
            )
            for rack in self.topology_model.racks.values()
        ]
        nodes += [
            TopologyNode(id=device.key, kind="device", label=device.code, type=device.type.value, hall_key=device.hall_key)
            for device in self.topology_model.devices.values()
        ]
        edges = [TopologyEdge(src=edge.src, dst=edge.dst, relation=edge.relation) for edge in self.topology_model.edges]
        return TopologyGraph(nodes=nodes, edges=edges)

    async def latest_readings(
        self, device_key: str | None = None, rack_key: str | None = None, metric: str | None = None
    ) -> list[ReadingOut]:
        rows = []
        for (key, name), value in self.readings.items():
            if device_key and key != device_key:
                continue
            if rack_key and key.rsplit("/", 1)[0] != rack_key:
                continue
            if metric and name != metric:
                continue
            rows.append(ReadingOut(device_key=key, metric=name, value=value, ts=NOW))
        return rows

    async def readings_since(self, since: datetime, device_key: str | None = None) -> list[ReadingOut]:
        if self.live_batches:
            return self.live_batches.pop(0)
        return []

    async def telemetry_range(self, device_key: str, metric: str, start: datetime, end: datetime, limit: int) -> list[PointOut]:
        points = [PointOut(ts=ts, value=value) for ts, value in self.history.get((device_key, metric), []) if start <= ts < end]
        return points[:limit]

    async def telemetry_series(
        self, device_key: str, metric: str, start: datetime, end: datetime, bucket_s: int
    ) -> list[SeriesPoint]:
        buckets: dict[int, list[float]] = {}
        for ts, value in self.history.get((device_key, metric), []):
            if start <= ts < end:
                buckets.setdefault(int(ts.timestamp() // bucket_s), []).append(value)
        return [
            SeriesPoint(ts=datetime.fromtimestamp(index * bucket_s, tz=timezone.utc), avg=sum(v) / len(v), min=min(v), max=max(v))
            for index, v in sorted(buckets.items())
        ]

    async def forecast(self, device_key: str, metric: str) -> list[PredictionOut]:
        return [row for row in self.prediction_rows if row.device_key == device_key and row.metric == metric]

    async def risk_scores(self, min_risk: float, limit: int) -> list[RiskOut]:
        rows = sorted((row for row in self.risk_rows if row.risk >= min_risk), key=lambda row: -row.risk)
        return rows[:limit]

    async def alerts(self, status: str | None, severity: str | None, limit: int) -> list[AlertOut]:
        rows = [row for row in self.alert_rows if (not status or row.status == status) and (not severity or row.severity == severity)]
        return sorted(rows, key=lambda row: row.raised_at, reverse=True)[:limit]

    async def set_alert_status(self, alert_id: int, status: str) -> AlertOut | None:
        for index, row in enumerate(self.alert_rows):
            if row.id == alert_id:
                self.alert_rows[index] = row.model_copy(update={"status": status})
                return self.alert_rows[index]
        return None

    async def open_alert_records(self) -> list[AlertRecord]:
        return [
            AlertRecord(row.id, row.device_key, row.metric, row.severity, row.raised_at)
            for row in self.alert_rows
            if row.status != "resolved"
        ]

    async def asset_edges(self) -> list[tuple[str, str, str]]:
        return [(edge.src, edge.dst, edge.relation) for edge in self.topology_model.edges]

    async def save_rca_runs(self, runs: list[RcaRun]) -> None:
        for run in runs:
            for rank, candidate in enumerate(run.candidates, start=1):
                self.rca_rows.append(
                    RcaResultOut(
                        run_id=run.run_id,
                        created_at=NOW,
                        rank=rank,
                        root_cause_key=candidate.node,
                        fault_kind=candidate.fault_kind,
                        score=candidate.score,
                        alert_ids=candidate.explained_alert_ids,
                        evidence=candidate.evidence,
                        summary=describe(candidate),
                    )
                )

    async def recent_rca(self, limit: int) -> list[RcaResultOut]:
        return self.rca_rows[:limit]
