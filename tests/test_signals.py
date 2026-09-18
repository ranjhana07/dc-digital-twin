import random

import pytest

from twin.simulator import signals


def test_diurnal_peaks_in_afternoon():
    afternoon = signals.diurnal_factor(14 * 3600)
    night = signals.diurnal_factor(2 * 3600)
    assert afternoon > night
    assert 0.1 <= night <= afternoon <= 0.95


def test_diurnal_is_periodic():
    assert signals.diurnal_factor(5000) == pytest.approx(signals.diurnal_factor(5000 + 86400))


def test_ar1_noise_is_deterministic_per_seed():
    first = signals.Ar1Noise(random.Random(3))
    second = signals.Ar1Noise(random.Random(3))
    assert [first.next() for _ in range(5)] == [second.next() for _ in range(5)]


def test_smooth_moves_toward_target():
    assert signals.smooth(20.0, 30.0, 60.0, 120.0) == pytest.approx(20.0 + 10.0 * (1 - 0.6065), rel=1e-3)
    assert signals.smooth(20.0, 30.0, 1e6, 60.0) == pytest.approx(30.0)


def test_server_power_scales_with_load():
    assert signals.server_power(0.0) == signals.SERVER_IDLE_W
    assert signals.server_power(1.0) == signals.SERVER_MAX_W
    assert signals.server_power(0.5, boost=1.0) > signals.server_power(0.5)


def test_fan_degradation_raises_outlet_temp():
    healthy = signals.fan_rpm(24.0, 0.5)
    degraded = signals.fan_rpm(24.0, 0.5, health=0.4)
    power = signals.server_power(0.5)
    assert degraded < healthy
    assert signals.outlet_temp(24.0, power, degraded) > signals.outlet_temp(24.0, power, healthy) + 8


def test_pdu_load_percentage():
    power = signals.pdu_power([500.0, 500.0])
    assert signals.pdu_load_pct(power, 2400.0) == pytest.approx(42.5)
    assert signals.pdu_current(2300.0) == pytest.approx(10.0)


def test_cooling_failure_raises_supply_temp():
    assert signals.crac_supply_temp(18.0, 0.15, 0.5) > signals.crac_supply_temp(18.0, 1.0, 0.5) + 8


def test_optics_loss_increases_ber():
    nominal = signals.pre_fec_ber_log10(signals.NOMINAL_RX_DBM, 45.0, 0.0)
    dirty = signals.pre_fec_ber_log10(signals.NOMINAL_RX_DBM - 6.0, 45.0, 0.0)
    assert nominal == pytest.approx(-9.0)
    assert dirty > nominal + 3
    assert signals.pre_fec_ber(-20.0, 45.0, 0.0) <= 0.1
