def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_sites_and_racks(client):
    sites = client.get("/api/sites").json()
    assert sites == [{"code": "dc1", "name": "DC1", "halls": 1, "racks": 4}]
    racks = client.get("/api/racks").json()
    assert len(racks) == 4
    assert racks[0]["rack_key"] == "dc1/hall-a/r01"
    assert client.get("/api/racks", params={"hall": "hall-z"}).json() == []


def test_devices_filter_by_rack_and_type(client):
    in_rack = client.get("/api/devices", params={"rack": "dc1/hall-a/r01"}).json()
    assert {device["device_type"] for device in in_rack} == {"server", "switch", "transceiver", "pdu"}
    servers = client.get("/api/devices", params={"device_type": "server"}).json()
    assert len(servers) == 8
    cracs = client.get("/api/devices", params={"device_type": "crac"}).json()
    assert all(device["rack_key"] is None for device in cracs)


def test_device_lookup(client):
    found = client.get("/api/devices/dc1/hall-a/r02/srv-01")
    assert found.status_code == 200
    assert found.json()["rack_key"] == "dc1/hall-a/r02"
    assert client.get("/api/devices/dc1/hall-a/r02/nope").status_code == 404


def test_topology_graph(client):
    graph = client.get("/api/topology").json()
    kinds = {node["kind"] for node in graph["nodes"]}
    assert kinds == {"rack", "device"}
    relations = {edge["relation"] for edge in graph["edges"]}
    assert {"cooled_by", "powered_by", "in_rack", "uplinks_to", "part_of"} == relations


def test_meta_lists_metrics_and_thresholds(client):
    meta = client.get("/api/meta").json()
    assert "inlet_temp" in meta["device_types"]["server"]
    inlet = next(item for item in meta["thresholds"] if item["device_type"] == "server" and item["metric"] == "inlet_temp")
    assert (inlet["warn"], inlet["crit"], inlet["unit"]) == (27.0, 32.0, "C")
