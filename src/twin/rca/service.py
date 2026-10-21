import uuid
from dataclasses import dataclass

from twin.rca.engine import AlertRecord, Candidate, cluster_alerts, rank_root_causes
from twin.rca.graph import AssetGraph


@dataclass
class RcaRun:
    run_id: str
    candidates: list[Candidate]
    alert_ids: list[int]


def describe(candidate: Candidate) -> str:
    kind = candidate.fault_kind.replace("_", " ") if candidate.fault_kind else "unclassified fault"
    devices = candidate.evidence.get("explained_devices", 0)
    alert_count = len(candidate.explained_alert_ids)
    alert_noun = "alert" if alert_count == 1 else "alerts"
    device_noun = "device" if devices == 1 else "devices"
    return f"{candidate.node}: probable {kind}, explains {alert_count} {alert_noun} on {devices} {device_noun}"


def analyze(alerts: list[AlertRecord], graph: AssetGraph, window_s: float = 1800.0, top_n: int = 3) -> list[RcaRun]:
    runs = []
    for cluster in cluster_alerts(alerts, window_s):
        candidates = rank_root_causes(cluster, graph, top_n)
        if candidates:
            runs.append(RcaRun(str(uuid.uuid4()), candidates, [alert.id for alert in cluster]))
    return runs
