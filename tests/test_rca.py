from datetime import datetime, timedelta, timezone

import pytest

from twin.common.topology import build_topology
from twin.rca.engine import AlertRecord, cluster_alerts, infer_fault_kind, rank_root_causes
from twin.rca.graph import AssetGraph

T0 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
CRAC1 = "dc1/hall-a/hall/crac-1"


@pytest.fixture(scope="module")
def graph():
    topology = build_topology(halls=1, racks_per_hall=4, servers_per_rack=4, cracs_per_hall=2)
    return AssetGraph(topology.edges)


def alert(alert_id, device, metric, minutes, severity="warning"):
    return AlertRecord(alert_id, device, metric, severity, T0 + timedelta(minutes=minutes))


def test_cooling_failure_points_to_shared_crac(graph):
    alerts = [alert(1, CRAC1, "supply_temp", 0, "critical")]
    for index, rack in enumerate(("r01", "r03")):
        for server in ("srv-01", "srv-02", "srv-03"):
            alerts.append(alert(10 + index * 10 + int(server[-1]), f"dc1/hall-a/{rack}/{server}", "inlet_temp", 5 + index))
    ranking = rank_root_causes(alerts, graph)
    assert ranking[0].node == CRAC1
    assert ranking[0].fault_kind == "cooling_failure"
    assert len(ranking[0].explained_alert_ids) == len(alerts)


def test_cooling_failure_wins_even_without_its_own_alert(graph):
    alerts = [alert(i, f"dc1/hall-a/{rack}/srv-0{i % 4 + 1}", "inlet_temp", i) for i, rack in enumerate(("r01", "r03", "r01", "r03"))]
    ranking = rank_root_causes(alerts, graph)
    assert ranking[0].node == CRAC1


def test_pdu_overload_beats_individual_servers(graph):
    pdu = "dc1/hall-a/r02/pdu-a"
    alerts = [alert(1, pdu, "load_pct", 0, "critical")]
    alerts += [alert(2 + i, f"dc1/hall-a/r02/srv-0{i + 1}", "outlet_temp", 6 + i) for i in range(3)]
    ranking = rank_root_causes(alerts, graph)
    assert ranking[0].node == pdu
    assert ranking[0].fault_kind == "pdu_overload"


def test_single_fan_fault_stays_on_the_server(graph):
    server = "dc1/hall-a/r04/srv-03"
    alerts = [alert(1, server, "fan_rpm", 0, "critical"), alert(2, server, "outlet_temp", 8)]
    ranking = rank_root_causes(alerts, graph)
    assert ranking[0].node == server
    assert ranking[0].fault_kind == "fan_degradation"


def test_dirty_optics_on_transceiver(graph):
    xcvr = "dc1/hall-a/r01/xcvr-1"
    ranking = rank_root_causes([alert(1, xcvr, "pre_fec_ber", 0, "critical"), alert(2, xcvr, "rx_power_dbm", 1)], graph)
    assert ranking[0].node == xcvr
    assert ranking[0].fault_kind == "dirty_optics"


def test_empty_alert_list(graph):
    assert rank_root_causes([], graph) == []


def test_top_n_limit_and_sorted_scores(graph):
    alerts = [alert(i, f"dc1/hall-a/r01/srv-0{i}", "inlet_temp", i) for i in range(1, 5)]
    ranking = rank_root_causes(alerts, graph, top_n=3)
    assert len(ranking) == 3
    assert [candidate.score for candidate in ranking] == sorted((c.score for c in ranking), reverse=True)


def test_cluster_alerts_by_gap():
    alerts = [alert(1, "a", "m", 0), alert(2, "b", "m", 10), alert(3, "c", "m", 120), alert(4, "d", "m", 125)]
    clusters = cluster_alerts(alerts, window_s=1800)
    assert [[a.id for a in cluster] for cluster in clusters] == [[1, 2], [3, 4]]


def test_infer_fault_kind_defaults_to_none():
    assert infer_fault_kind("dc1/hall-a/r01/srv-01", [alert(1, "x", "inlet_temp", 0)]) is None
