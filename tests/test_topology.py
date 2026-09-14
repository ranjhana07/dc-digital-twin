from twin.common.metrics import DeviceType
from twin.common.topology import build_topology


def test_default_counts():
    topology = build_topology(sites=1, halls=2, racks_per_hall=4, servers_per_rack=3, cracs_per_hall=2)
    assert len(topology.racks) == 8
    assert len(topology.devices_of_type(DeviceType.SERVER)) == 24
    assert len(topology.devices_of_type(DeviceType.CRAC)) == 4
    assert len(topology.devices_of_type(DeviceType.PDU)) == 8


def test_racks_alternate_between_cracs():
    topology = build_topology(halls=1, racks_per_hall=4, cracs_per_hall=2)
    cooled = {rack: topology.targets_of(rack, "cooled_by")[0] for rack in topology.racks}
    assert cooled["dc1/hall-a/r01"] == "dc1/hall-a/hall/crac-1"
    assert cooled["dc1/hall-a/r02"] == "dc1/hall-a/hall/crac-2"
    assert cooled["dc1/hall-a/r03"] == "dc1/hall-a/hall/crac-1"


def test_servers_depend_on_rack_pdu_and_switch():
    topology = build_topology(halls=1, racks_per_hall=1, servers_per_rack=2)
    server = "dc1/hall-a/r01/srv-01"
    assert topology.targets_of(server, "powered_by") == ["dc1/hall-a/r01/pdu-a"]
    assert topology.targets_of(server, "uplinks_to") == ["dc1/hall-a/r01/sw-01"]
    assert sorted(topology.sources_of("dc1/hall-a/r01/sw-01", "part_of")) == [
        "dc1/hall-a/r01/xcvr-1",
        "dc1/hall-a/r01/xcvr-2",
    ]


def test_device_keys_are_unique():
    topology = build_topology(sites=2, halls=2, racks_per_hall=3)
    assert len(topology.devices) == len({device.key for device in topology.devices.values()})
