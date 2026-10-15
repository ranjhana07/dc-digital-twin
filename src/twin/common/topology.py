from dataclasses import dataclass, field

from twin.common.metrics import DeviceType

HALL_LEVEL_RACK = "hall"


@dataclass(frozen=True)
class Device:
    site: str
    hall: str
    rack: str
    code: str
    type: DeviceType

    @property
    def key(self) -> str:
        return f"{self.site}/{self.hall}/{self.rack}/{self.code}"

    @property
    def rack_key(self) -> str:
        return f"{self.site}/{self.hall}/{self.rack}"

    @property
    def hall_key(self) -> str:
        return f"{self.site}/{self.hall}"


@dataclass(frozen=True)
class Rack:
    site: str
    hall: str
    code: str
    grid_row: int
    grid_col: int

    @property
    def key(self) -> str:
        return f"{self.site}/{self.hall}/{self.code}"


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    relation: str


@dataclass
class Topology:
    racks: dict[str, Rack] = field(default_factory=dict)
    devices: dict[str, Device] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def devices_of_type(self, device_type: DeviceType) -> list[Device]:
        return [device for device in self.devices.values() if device.type == device_type]

    def devices_in_rack(self, rack_key: str) -> list[Device]:
        return [device for device in self.devices.values() if device.rack_key == rack_key]

    def targets_of(self, src: str, relation: str) -> list[str]:
        return [edge.dst for edge in self.edges if edge.src == src and edge.relation == relation]

    def sources_of(self, dst: str, relation: str) -> list[str]:
        return [edge.src for edge in self.edges if edge.dst == dst and edge.relation == relation]


def build_topology(
    sites: int = 1,
    halls: int = 2,
    racks_per_hall: int = 6,
    servers_per_rack: int = 4,
    cracs_per_hall: int = 2,
    xcvrs_per_switch: int = 2,
    racks_per_row: int = 3,
) -> Topology:
    topology = Topology()
    for site_index in range(1, sites + 1):
        site = f"dc{site_index}"
        for hall_index in range(halls):
            hall = f"hall-{chr(ord('a') + hall_index)}"
            cracs = []
            for crac_index in range(1, cracs_per_hall + 1):
                crac = Device(site, hall, HALL_LEVEL_RACK, f"crac-{crac_index}", DeviceType.CRAC)
                topology.devices[crac.key] = crac
                cracs.append(crac)
            for rack_index in range(racks_per_hall):
                rack = Rack(
                    site, hall, f"r{rack_index + 1:02d}", rack_index // racks_per_row, rack_index % racks_per_row
                )
                topology.racks[rack.key] = rack
                topology.edges.append(Edge(rack.key, cracs[rack_index % len(cracs)].key, "cooled_by"))
                _populate_rack(topology, rack, servers_per_rack, xcvrs_per_switch)
    return topology


def _populate_rack(topology: Topology, rack: Rack, servers: int, xcvrs: int) -> None:
    pdu = Device(rack.site, rack.hall, rack.code, "pdu-a", DeviceType.PDU)
    switch = Device(rack.site, rack.hall, rack.code, "sw-01", DeviceType.SWITCH)
    members = [pdu, switch]
    members += [
        Device(rack.site, rack.hall, rack.code, f"srv-{index:02d}", DeviceType.SERVER)
        for index in range(1, servers + 1)
    ]
    members += [
        Device(rack.site, rack.hall, rack.code, f"xcvr-{index}", DeviceType.TRANSCEIVER)
        for index in range(1, xcvrs + 1)
    ]
    for device in members:
        topology.devices[device.key] = device
        topology.edges.append(Edge(device.key, rack.key, "in_rack"))
        if device.type in (DeviceType.SERVER, DeviceType.SWITCH):
            topology.edges.append(Edge(device.key, pdu.key, "powered_by"))
        if device.type == DeviceType.SERVER:
            topology.edges.append(Edge(device.key, switch.key, "uplinks_to"))
        if device.type == DeviceType.TRANSCEIVER:
            topology.edges.append(Edge(device.key, switch.key, "part_of"))


DEVICE_PREFIXES: dict[str, DeviceType] = {
    "srv-": DeviceType.SERVER,
    "sw-": DeviceType.SWITCH,
    "xcvr-": DeviceType.TRANSCEIVER,
    "pdu-": DeviceType.PDU,
    "crac-": DeviceType.CRAC,
}


def device_type_of(device_key: str) -> DeviceType | None:
    code = device_key.rsplit("/", 1)[-1]
    for prefix, device_type in DEVICE_PREFIXES.items():
        if code.startswith(prefix):
            return device_type
    return None


def rack_key_of(device_key: str) -> str:
    return device_key.rsplit("/", 1)[0]
