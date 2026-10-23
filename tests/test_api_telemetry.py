from datetime import datetime, timedelta, timezone

from fake_repository import NOW

DEVICE = "dc1/hall-a/r01/srv-01"


def seed_history(repo, minutes=30):
    repo.history[(DEVICE, "inlet_temp")] = [(NOW - timedelta(minutes=minutes - index), 20.0 + index * 0.1) for index in range(minutes)]


def window(minutes):
    return {"start": (NOW - timedelta(minutes=minutes)).isoformat(), "end": NOW.isoformat()}


def test_latest_filters(client, repo):
    repo.set_reading(DEVICE, "inlet_temp", 23.0)
    repo.set_reading(DEVICE, "fan_rpm", 4800.0)
    repo.set_reading("dc1/hall-a/r02/srv-01", "inlet_temp", 24.0)
    assert len(client.get("/api/telemetry/latest").json()) == 3
    only_device = client.get("/api/telemetry/latest", params={"device_key": DEVICE}).json()
    assert {row["metric"] for row in only_device} == {"inlet_temp", "fan_rpm"}
    by_rack = client.get("/api/telemetry/latest", params={"rack_key": "dc1/hall-a/r02"}).json()
    assert [row["value"] for row in by_rack] == [24.0]


def test_range_returns_points_in_window(client, repo):
    seed_history(repo)
    response = client.get("/api/telemetry/range", params={"device_key": DEVICE, "metric": "inlet_temp", **window(10)})
    assert response.status_code == 200
    assert len(response.json()) == 10


def test_range_limit_applies(client, repo):
    seed_history(repo)
    response = client.get("/api/telemetry/range", params={"device_key": DEVICE, "metric": "inlet_temp", "limit": 5, **window(30)})
    assert len(response.json()) == 5


def test_unknown_metric_is_rejected(client):
    response = client.get("/api/telemetry/range", params={"device_key": DEVICE, "metric": "humidity"})
    assert response.status_code == 422


def test_start_after_end_is_rejected(client):
    params = {"device_key": DEVICE, "metric": "inlet_temp", "start": NOW.isoformat(), "end": (NOW - timedelta(hours=1)).isoformat()}
    assert client.get("/api/telemetry/range", params=params).status_code == 422


def test_series_downsamples_into_buckets(client, repo):
    seed_history(repo)
    response = client.get(
        "/api/telemetry/series", params={"device_key": DEVICE, "metric": "inlet_temp", "bucket_s": 600, **window(30)}
    )
    body = response.json()
    assert body["bucket_s"] == 600
    assert 3 <= len(body["points"]) <= 4
    first = body["points"][0]
    assert first["min"] <= first["avg"] <= first["max"]
    parsed = datetime.fromisoformat(first["ts"].replace("Z", "+00:00"))
    assert parsed.tzinfo == timezone.utc
