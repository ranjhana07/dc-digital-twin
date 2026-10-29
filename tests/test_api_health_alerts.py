from datetime import timedelta

from fake_repository import NOW
from twin.api.schemas import PredictionOut, RiskOut

SERVER = "dc1/hall-a/r01/srv-01"


def test_health_endpoints_reflect_latest_readings(client, repo):
    repo.set_reading(SERVER, "inlet_temp", 33.0)
    repo.set_reading("dc1/hall-a/r02/srv-01", "inlet_temp", 22.0)
    repo.add_alert(1, SERVER, "inlet_temp", "critical")
    racks = client.get("/api/health/racks").json()
    assert racks[0]["rack_key"] == "dc1/hall-a/r01"
    assert racks[0]["status"] == "critical"
    assert racks[0]["worst_device"] == SERVER
    assert racks[-1]["status"] == "healthy"
    offenders = client.get("/api/health/offenders", params={"limit": 3}).json()
    assert offenders[0]["device_key"] == SERVER
    summary = client.get("/api/health/summary").json()
    assert summary["racks"] == 4
    assert summary["critical"] == 1
    assert summary["open_alerts"] == {"critical": 1}


def test_alert_listing_filters(client, repo):
    repo.add_alert(1, SERVER, "inlet_temp", "critical", minutes=0)
    repo.add_alert(2, SERVER, "fan_rpm", "warning", minutes=5)
    repo.add_alert(3, "dc1/hall-a/r02/srv-01", "inlet_temp", "warning", status="resolved", minutes=9)
    assert [row["id"] for row in client.get("/api/alerts").json()] == [3, 2, 1]
    assert [row["id"] for row in client.get("/api/alerts", params={"status": "open"}).json()] == [2, 1]
    assert [row["id"] for row in client.get("/api/alerts", params={"severity": "critical"}).json()] == [1]
    assert client.get("/api/alerts", params={"status": "weird"}).status_code == 422


def test_ack_and_resolve_flow(client, repo):
    repo.add_alert(7, SERVER, "inlet_temp", "warning")
    acked = client.post("/api/alerts/7/ack").json()
    assert acked["status"] == "acknowledged"
    resolved = client.post("/api/alerts/7/resolve").json()
    assert resolved["status"] == "resolved"
    assert client.post("/api/alerts/99/ack").status_code == 404


def test_forecast_and_risk_routes(client, repo):
    for step in (1, 2):
        repo.prediction_rows.append(
            PredictionOut(
                device_key=SERVER, metric="inlet_temp", task="thermal", made_at=NOW, target_ts=NOW + timedelta(minutes=step),
                horizon_step=step, predicted=25.0 + step, lower=24.0, upper=27.0, model_version="v1",
            )
        )
    for metric, risk in (("inlet_temp", 0.9), ("outlet_temp", 0.2)):
        repo.risk_rows.append(
            RiskOut(device_key=SERVER, metric=metric, task="thermal", computed_at=NOW, risk=risk, severity="critical" if risk > 0.8 else "ok",
                    p_warn=risk, p_crit=risk / 2, rate_per_hour=1.0, z_score=0.5, breach_step=3)
        )
    points = client.get("/api/predictions", params={"device_key": SERVER, "metric": "inlet_temp"}).json()
    assert [point["horizon_step"] for point in points] == [1, 2]
    assert client.get("/api/predictions", params={"device_key": SERVER}).status_code == 422
    risky = client.get("/api/predictions/risk", params={"min_risk": 0.5}).json()
    assert [row["metric"] for row in risky] == ["inlet_temp"]
    assert len(client.get("/api/predictions/risk").json()) == 2
