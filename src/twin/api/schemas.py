from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["warning", "critical"]
AlertStatus = Literal["open", "acknowledged", "resolved"]
HealthStatus = Literal["healthy", "degraded", "critical"]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SiteOut(Schema):
    code: str
    name: str
    halls: int
    racks: int


class RackOut(Schema):
    rack_key: str
    site: str
    hall: str
    code: str
    grid_row: int
    grid_col: int
    device_count: int


class DeviceOut(Schema):
    device_key: str
    site: str
    hall: str
    rack_key: str | None
    code: str
    device_type: str


class TopologyNode(Schema):
    id: str
    kind: Literal["rack", "device"]
    label: str
    type: str
    hall_key: str
    grid_row: int | None = None
    grid_col: int | None = None


class TopologyEdge(Schema):
    src: str
    dst: str
    relation: str


class TopologyGraph(Schema):
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]


class ReadingOut(Schema):
    device_key: str
    metric: str
    value: float
    ts: datetime


class PointOut(Schema):
    ts: datetime
    value: float


class SeriesPoint(Schema):
    ts: datetime
    avg: float
    min: float
    max: float


class SeriesOut(Schema):
    device_key: str
    metric: str
    bucket_s: int
    points: list[SeriesPoint]


class DeviceHealth(Schema):
    device_key: str
    device_type: str
    score: float
    worst_metric: str | None
    worst_value: float | None


class RackHealth(Schema):
    rack_key: str
    score: float
    status: HealthStatus
    device_count: int
    open_alerts: int
    worst_device: str | None
    worst_metric: str | None


class Offender(Schema):
    device_key: str
    device_type: str
    metric: str
    value: float
    score: float
    open_alerts: int


class HealthSummary(Schema):
    racks: int
    healthy: int
    degraded: int
    critical: int
    average_score: float
    open_alerts: dict[str, int]


class PredictionOut(Schema):
    device_key: str
    metric: str
    task: str
    made_at: datetime
    target_ts: datetime
    horizon_step: int
    predicted: float
    lower: float
    upper: float
    model_version: str


class RiskOut(Schema):
    device_key: str
    metric: str
    task: str
    computed_at: datetime
    risk: float
    severity: str
    p_warn: float
    p_crit: float
    rate_per_hour: float
    z_score: float
    breach_step: int | None


class AlertOut(Schema):
    id: int
    device_key: str
    rack_key: str
    metric: str
    kind: str
    severity: Severity
    status: AlertStatus
    message: str
    risk_score: float | None
    raised_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class RcaResultOut(Schema):
    run_id: str
    created_at: datetime
    rank: int
    root_cause_key: str
    fault_kind: str | None
    score: float
    alert_ids: list[int]
    evidence: dict = Field(default_factory=dict)
    summary: str | None = None


class ThresholdOut(Schema):
    device_type: str
    metric: str
    warn: float
    crit: float
    direction: str
    unit: str


class MetaOut(Schema):
    device_types: dict[str, list[str]]
    thresholds: list[ThresholdOut]
