import pytest

from twin.common.topology import build_topology
from twin.simulator.faults import FaultKind, FaultSchedule, FaultSpec, random_schedule


def spec(**overrides):
    values = dict(kind=FaultKind.COOLING_FAILURE, target="dc1/hall-a/hall/crac-1", start_s=1000.0, duration_s=3000.0)
    values.update(overrides)
    return FaultSpec(**values)


def test_intensity_ramps_holds_and_recovers():
    fault = spec(ramp_s=500.0, recovery_s=200.0)
    assert fault.intensity(900.0) == 0.0
    assert fault.intensity(1250.0) == pytest.approx(0.5)
    assert fault.intensity(2000.0) == 1.0
    assert fault.intensity(4100.0) == pytest.approx(0.5)
    assert fault.intensity(4300.0) == 0.0


def test_active_window_includes_recovery():
    fault = spec(recovery_s=200.0)
    assert not fault.active(999.0)
    assert fault.active(4100.0)
    assert not fault.active(4200.0)


def test_effects_cover_each_fault_kind():
    schedule = FaultSchedule(
        [
            spec(),
            spec(kind=FaultKind.FAN_DEGRADATION, target="srv"),
            spec(kind=FaultKind.DIRTY_OPTICS, target="xcvr"),
            spec(kind=FaultKind.PDU_OVERLOAD, target="pdu"),
        ]
    )
    effects = schedule.effects_at(2000.0)
    assert effects.cooling_factor["dc1/hall-a/hall/crac-1"] < 0.2
    assert effects.fan_health["srv"] < 0.4
    assert effects.optics_loss_db["xcvr"] > 7
    assert effects.load_boost["pdu"] == 1.0
    assert schedule.effects_at(0.0).cooling_factor == {}


def test_random_schedule_is_reproducible_and_targets_right_types():
    topology = build_topology()
    first = random_schedule(topology, seed=5, start_s=0.0, horizon_s=86400.0, count=8)
    second = random_schedule(topology, seed=5, start_s=0.0, horizon_s=86400.0, count=8)
    assert first.specs == second.specs
    assert {item.kind for item in first.specs} == set(FaultKind)
    for item in first.specs:
        assert item.target in topology.devices
        assert item.end_s <= 86400.0
