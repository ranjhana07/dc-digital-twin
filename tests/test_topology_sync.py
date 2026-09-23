from twin.common.topology import build_topology
from twin.db.topology_sync import hall_rows, site_rows


def test_site_and_hall_rows():
    topology = build_topology(sites=2, halls=2, racks_per_hall=1)
    assert site_rows(topology) == [("dc1", "DC1"), ("dc2", "DC2")]
    assert hall_rows(topology) == [("dc1", "hall-a"), ("dc1", "hall-b"), ("dc2", "hall-a"), ("dc2", "hall-b")]
