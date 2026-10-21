from datetime import datetime, timedelta, timezone

from twin.common.topology import build_topology
from twin.rca.engine import AlertRecord
from twin.rca.graph import AssetGraph
from twin.rca.service import analyze, describe

T0 = datetime(2026, 5, 1, tzinfo=timezone.utc)


def test_separate_incidents_get_separate_runs():
    graph = AssetGraph(build_topology(halls=1, racks_per_hall=2).edges)
    alerts = [
        AlertRecord(1, "dc1/hall-a/r01/pdu-a", "load_pct", "critical", T0),
        AlertRecord(2, "dc1/hall-a/r01/srv-01", "outlet_temp", "warning", T0 + timedelta(minutes=5)),
        AlertRecord(3, "dc1/hall-a/r02/xcvr-1", "pre_fec_ber", "critical", T0 + timedelta(hours=5)),
    ]
    runs = analyze(alerts, graph)
    assert len(runs) == 2
    assert runs[0].candidates[0].node == "dc1/hall-a/r01/pdu-a"
    assert runs[1].candidates[0].node == "dc1/hall-a/r02/xcvr-1"
    assert runs[0].run_id != runs[1].run_id
    assert runs[0].alert_ids == [1, 2]


def test_describe_mentions_kind_and_counts():
    graph = AssetGraph(build_topology(halls=1, racks_per_hall=1).edges)
    runs = analyze([AlertRecord(1, "dc1/hall-a/r01/xcvr-1", "pre_fec_ber", "critical", T0)], graph)
    text = describe(runs[0].candidates[0])
    assert "dirty optics" in text
    assert "1 alert on 1 device" in text
