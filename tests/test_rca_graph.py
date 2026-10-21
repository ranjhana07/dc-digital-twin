from twin.common.topology import build_topology
from twin.rca.graph import AssetGraph


def graph():
    return AssetGraph(build_topology(halls=1, racks_per_hall=2, servers_per_rack=2, xcvrs_per_switch=1).edges)


def test_upstream_of_server_includes_rack_cooling_power_and_switch():
    upstream = graph().upstream("dc1/hall-a/r01/srv-01")
    assert {
        "dc1/hall-a/r01",
        "dc1/hall-a/hall/crac-1",
        "dc1/hall-a/r01/pdu-a",
        "dc1/hall-a/r01/sw-01",
    } <= upstream
    assert "dc1/hall-a/r02/pdu-a" not in upstream


def test_downstream_of_crac_covers_served_rack_devices_only():
    downstream = graph().downstream("dc1/hall-a/hall/crac-1")
    assert "dc1/hall-a/r01/srv-02" in downstream
    assert "dc1/hall-a/r01/xcvr-1" in downstream
    assert "dc1/hall-a/r02/srv-01" not in downstream


def test_downstream_of_switch_includes_transceivers_and_uplinked_servers():
    downstream = graph().downstream("dc1/hall-a/r01/sw-01")
    assert {"dc1/hall-a/r01/xcvr-1", "dc1/hall-a/r01/srv-01"} <= downstream


def test_cycles_do_not_loop_forever():
    from twin.common.topology import Edge

    cyclic = AssetGraph([Edge("a", "b", "x"), Edge("b", "a", "x")])
    assert cyclic.upstream("a") == {"a", "b"}
