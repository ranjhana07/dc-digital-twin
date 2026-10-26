import pytest

from fake_repository import NOW
from twin.api.health import FleetHealth, device_health, metric_penalty, rack_health, status_for
from twin.api.schemas import AlertOut, DeviceOut, ReadingOut
from twin.common.metrics import DeviceType


def device(key, device_type):
    rack_key, code = key.rsplit("/", 1)
    return DeviceOut(device_key=key, site="dc1", hall="hall-a", rack_key=rack_key, code=code, device_type=device_type)


def reading(key, metric, value):
    return ReadingOut(device_key=key, metric=metric, value=value, ts=NOW)


def alert(key, status="open", severity="warning"):
    return AlertOut(
        id=1, device_key=key, rack_key=key.rsplit("/", 1)[0], metric="inlet_temp", kind="threshold", severity=severity,
        status=status, message="m", risk_score=None, raised_at=NOW,
    )


def test_penalty_is_zero_inside_limits_and_grows_past_them():
    assert metric_penalty(DeviceType.SERVER, "inlet_temp", 24.0) == 0.0
    warn = metric_penalty(DeviceType.SERVER, "inlet_temp", 27.0)
    mid = metric_penalty(DeviceType.SERVER, "inlet_temp", 29.5)
    crit = metric_penalty(DeviceType.SERVER, "inlet_temp", 33.0)
    assert 0.3 < warn < mid < crit <= 1.0
    assert metric_penalty(DeviceType.SERVER, "cpu_load", 0.99) == 0.0


def test_low_threshold_metrics():
    assert metric_penalty(DeviceType.SERVER, "fan_rpm", 5000.0) == 0.0
    assert metric_penalty(DeviceType.SERVER, "fan_rpm", 2000.0) == pytest.approx(1.0)


def test_ber_penalty_uses_log_scale():
    assert metric_penalty(DeviceType.TRANSCEIVER, "pre_fec_ber", 1e-9) == 0.0
    assert metric_penalty(DeviceType.TRANSCEIVER, "pre_fec_ber", 1e-5) == pytest.approx(0.675, abs=0.01)


def test_device_health_picks_worst_metric():
    health = device_health("k", DeviceType.SERVER, {"inlet_temp": 24.0, "outlet_temp": 52.0})
    assert health.worst_metric == "outlet_temp"
    assert health.score == 0.0
    assert device_health("k", DeviceType.SERVER, {"inlet_temp": 24.0}).score == 100.0


def test_status_thresholds():
    assert [status_for(score) for score in (100, 85, 84.9, 60, 59.9)] == ["healthy", "healthy", "degraded", "degraded", "critical"]


def test_rack_health_combines_min_mean_and_alerts():
    from twin.api.schemas import DeviceHealth

    devices = [DeviceHealth(device_key=f"d{i}", device_type="server", score=score, worst_metric="m" if score < 100 else None, worst_value=1.0) for i, score in enumerate([100, 100, 40])]
    rack = rack_health("r", devices, open_alerts=2)
    assert rack.score == pytest.approx(0.6 * 40 + 0.4 * 80 - 10)
    assert rack.worst_device == "d2"
    assert rack_health("r", [], 0).score == 100.0
    assert rack_health("r", devices, 100).score == pytest.approx(0.6 * 40 + 0.4 * 80 - 20)


def test_fleet_health_ranks_racks_and_offenders():
    devices = [device("dc1/hall-a/r01/srv-01", "server"), device("dc1/hall-a/r01/srv-02", "server"), device("dc1/hall-a/r02/srv-01", "server")]
    readings = [
        reading("dc1/hall-a/r01/srv-01", "inlet_temp", 31.0),
        reading("dc1/hall-a/r01/srv-02", "inlet_temp", 23.0),
        reading("dc1/hall-a/r02/srv-01", "inlet_temp", 23.0),
    ]
    fleet = FleetHealth(devices, readings, [alert("dc1/hall-a/r01/srv-01"), alert("dc1/hall-a/r01/srv-02", status="resolved")])
    racks = fleet.racks()
    assert [rack.rack_key for rack in racks] == ["dc1/hall-a/r01", "dc1/hall-a/r02"]
    assert racks[0].open_alerts == 1
    assert racks[0].status != "healthy"
    assert racks[1].status == "healthy"
    offenders = fleet.offenders()
    assert [offender.device_key for offender in offenders] == ["dc1/hall-a/r01/srv-01"]
    summary = fleet.summary()
    assert summary.racks == 2 and summary.healthy == 1
    assert summary.open_alerts == {"warning": 1}
