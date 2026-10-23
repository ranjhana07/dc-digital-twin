from datetime import datetime
from typing import Protocol

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
    TopologyGraph,
)
from twin.rca.engine import AlertRecord
from twin.rca.service import RcaRun


class Repository(Protocol):
    async def list_sites(self) -> list[SiteOut]: ...

    async def list_racks(self, hall: str | None = None) -> list[RackOut]: ...

    async def list_devices(self, rack_key: str | None = None, device_type: str | None = None) -> list[DeviceOut]: ...

    async def get_device(self, device_key: str) -> DeviceOut | None: ...

    async def topology(self) -> TopologyGraph: ...

    async def latest_readings(
        self, device_key: str | None = None, rack_key: str | None = None, metric: str | None = None
    ) -> list[ReadingOut]: ...

    async def readings_since(self, since: datetime, device_key: str | None = None) -> list[ReadingOut]: ...

    async def telemetry_range(
        self, device_key: str, metric: str, start: datetime, end: datetime, limit: int
    ) -> list[PointOut]: ...

    async def telemetry_series(
        self, device_key: str, metric: str, start: datetime, end: datetime, bucket_s: int
    ) -> list[SeriesPoint]: ...

    async def forecast(self, device_key: str, metric: str) -> list[PredictionOut]: ...

    async def risk_scores(self, min_risk: float, limit: int) -> list[RiskOut]: ...

    async def alerts(self, status: str | None, severity: str | None, limit: int) -> list[AlertOut]: ...

    async def set_alert_status(self, alert_id: int, status: str) -> AlertOut | None: ...

    async def open_alert_records(self) -> list[AlertRecord]: ...

    async def asset_edges(self) -> list[tuple[str, str, str]]: ...

    async def save_rca_runs(self, runs: list[RcaRun]) -> None: ...

    async def recent_rca(self, limit: int) -> list[RcaResultOut]: ...
