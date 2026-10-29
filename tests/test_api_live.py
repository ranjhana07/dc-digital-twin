from fake_repository import NOW
from twin.api.schemas import ReadingOut

SERVER = "dc1/hall-a/r01/srv-01"


def batch(*metrics):
    return [ReadingOut(device_key=SERVER, metric=metric, value=float(index), ts=NOW) for index, metric in enumerate(metrics)]


def test_stream_pushes_telemetry_batches(client, repo):
    repo.live_batches.append(batch("inlet_temp", "fan_rpm"))
    with client.websocket_connect("/ws/telemetry") as socket:
        message = socket.receive_json()
    assert message["type"] == "telemetry"
    assert [point["metric"] for point in message["points"]] == ["inlet_temp", "fan_rpm"]
    assert message["points"][0]["device_key"] == SERVER


def test_stream_filters_by_query_metrics(client, repo):
    repo.live_batches.append(batch("inlet_temp", "fan_rpm"))
    with client.websocket_connect("/ws/telemetry?metrics=fan_rpm") as socket:
        message = socket.receive_json()
    assert [point["metric"] for point in message["points"]] == ["fan_rpm"]


def test_stream_sends_heartbeat_when_idle(client):
    with client.websocket_connect("/ws/telemetry") as socket:
        assert socket.receive_json()["type"] == "heartbeat"


def test_client_can_update_filter(client, repo):
    with client.websocket_connect("/ws/telemetry") as socket:
        socket.send_json({"device_key": SERVER, "metrics": ["fan_rpm"]})
        repo.live_batches.append(batch("inlet_temp", "fan_rpm"))
        for _ in range(20):
            message = socket.receive_json()
            if message["type"] == "telemetry":
                break
    assert [point["metric"] for point in message["points"]] == ["fan_rpm"]


def test_invalid_json_gets_error_message(client):
    with client.websocket_connect("/ws/telemetry") as socket:
        socket.send_text("not json")
        types = {socket.receive_json()["type"] for _ in range(3)}
    assert "error" in types
