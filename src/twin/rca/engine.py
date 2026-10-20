from dataclasses import dataclass, field
from datetime import datetime

from twin.common.metrics import DeviceType
from twin.common.topology import device_type_of
from twin.rca.graph import AssetGraph

SEVERITY_WEIGHT = {"critical": 1.0, "warning": 0.6}


@dataclass(frozen=True)
class AlertRecord:
    id: int
    device_key: str
    metric: str
    severity: str
    raised_at: datetime


@dataclass
class Candidate:
    node: str
    score: float
    fault_kind: str | None
    explained_alert_ids: list[int]
    evidence: dict = field(default_factory=dict)


def cluster_alerts(alerts: list[AlertRecord], window_s: float = 1800.0) -> list[list[AlertRecord]]:
    ordered = sorted(alerts, key=lambda alert: alert.raised_at)
    clusters: list[list[AlertRecord]] = []
    for alert in ordered:
        if clusters and (alert.raised_at - clusters[-1][-1].raised_at).total_seconds() <= window_s:
            clusters[-1].append(alert)
        else:
            clusters.append([alert])
    return clusters


def infer_fault_kind(node: str, own_alerts: list[AlertRecord]) -> str | None:
    node_type = device_type_of(node)
    metrics = {alert.metric for alert in own_alerts}
    if node_type is DeviceType.CRAC:
        return "cooling_failure"
    if node_type is DeviceType.PDU:
        return "pdu_overload"
    if node_type is DeviceType.TRANSCEIVER:
        return "dirty_optics"
    if node_type in (DeviceType.SERVER, DeviceType.SWITCH) and "fan_rpm" in metrics:
        return "fan_degradation"
    return None


def _precedence(own: list[AlertRecord], others: list[AlertRecord]) -> float:
    if not own:
        return 0.5
    if not others:
        return 1.0
    first_own = min(alert.raised_at for alert in own)
    later = sum(1 for alert in others if alert.raised_at >= first_own)
    return later / len(others)


def rank_root_causes(alerts: list[AlertRecord], graph: AssetGraph, top_n: int = 5) -> list[Candidate]:
    if not alerts:
        return []
    by_device: dict[str, list[AlertRecord]] = {}
    for alert in alerts:
        by_device.setdefault(alert.device_key, []).append(alert)
    nodes: set[str] = set(by_device)
    for device_key in by_device:
        nodes |= {node for node in graph.upstream(device_key) if device_type_of(node) is not None}
    candidates: list[Candidate] = []
    for node in nodes:
        footprint = graph.downstream(node) | {node}
        explained = [alert for alert in alerts if alert.device_key in footprint]
        if not explained:
            continue
        own = by_device.get(node, [])
        others = [alert for alert in explained if alert.device_key != node]
        coverage = len(explained) / len(alerts)
        precedence = _precedence(own, others)
        monitored_footprint = {key for key in footprint if device_type_of(key) is not None}
        affected = {alert.device_key for alert in explained}
        precision = len(affected) / max(len(monitored_footprint), 1)
        severity = max((SEVERITY_WEIGHT.get(alert.severity, 0.3) for alert in own), default=0.0)
        score = 0.45 * coverage + 0.25 * precedence + 0.15 * min(precision * 2.0, 1.0) + 0.15 * severity
        candidates.append(
            Candidate(
                node=node,
                score=round(score, 4),
                fault_kind=infer_fault_kind(node, own),
                explained_alert_ids=sorted(alert.id for alert in explained),
                evidence={
                    "coverage": round(coverage, 3),
                    "precedence": round(precedence, 3),
                    "precision": round(precision, 3),
                    "severity": severity,
                    "own_alerts": len(own),
                    "explained_devices": len(affected),
                },
            )
        )
    candidates.sort(key=lambda candidate: (-candidate.score, len(graph.downstream(candidate.node)), candidate.node))
    return candidates[:top_n]
