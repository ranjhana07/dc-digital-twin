from collections import defaultdict

import pytest

from twin.common.metrics import ALL_METRICS, DEVICE_METRICS
from twin.common.topology import build_topology
from twin.simulator.engine import Simulation
from twin.simulator.faults import FaultKind, FaultSchedule, FaultSpec

T0 = 1_780_000_000.0


@pytest.fixture
def topology():
    return build_topology(halls=1, racks_per_hall=2, servers_per_rack=2, cracs_per_hall=2)


def run(simulation, start, steps, dt=60.0):
    series = defaultdict(list)
    for index in range(steps):
        for reading in simulation.step(start + index * dt, dt):
            series[(reading.device_key, reading.metric)].append(reading.value)
    return series


def test_step_emits_every_metric_of_every_device(topology):
    readings = Simulation(topology).step(T0)
    emitted = {(reading.device_key, reading.metric) for reading in readings}
    expected = {
        (device.key, metric) for device in topology.devices.values() for metric in DEVICE_METRICS[device.type]
    }
    assert emitted == expected
    assert all(reading.metric in ALL_METRICS for reading in readings)


def test_same_seed_gives_same_output(topology):
    first = Simulation(topology, seed=11).step(T0)
    second = Simulation(topology, seed=11).step(T0)
    third = Simulation(topology, seed=12).step(T0)
    assert first == second
    assert first != third


def test_healthy_values_stay_in_safe_ranges(topology):
    series = run(Simulation(topology), T0, 120)
    for (key, metric), values in series.items():
        if metric == "inlet_temp":
            assert max(values) < 27.0
        if metric == "outlet_temp":
            assert max(values) < 40.0
        if metric == "load_pct":
            assert max(values) < 80.0
        if metric == "pre_fec_ber":
            assert max(values) < 1e-6


def fault_run(topology, kind, target, metric_key):
    quiet = Simulation(topology, seed=3)
    faulty = Simulation(topology, FaultSchedule([FaultSpec(kind, target, T0, 7200.0, ramp_s=300.0)]), seed=3)
    return run(quiet, T0, 90)[metric_key], run(faulty, T0, 90)[metric_key]


def test_cooling_failure_heats_served_racks(topology):
    crac = "dc1/hall-a/hall/crac-1"
    quiet, faulty = fault_run(topology, FaultKind.COOLING_FAILURE, crac, ("dc1/hall-a/r01/srv-01", "inlet_temp"))
    assert max(faulty) > 30.0
    assert max(quiet) < 27.0
    _, other_rack = fault_run(topology, FaultKind.COOLING_FAILURE, crac, ("dc1/hall-a/r02/srv-01", "inlet_temp"))
    assert max(other_rack) < 27.0


def test_fan_degradation_lowers_rpm_and_raises_outlet(topology):
    server = "dc1/hall-a/r01/srv-01"
    quiet_rpm, faulty_rpm = fault_run(topology, FaultKind.FAN_DEGRADATION, server, (server, "fan_rpm"))
    quiet_out, faulty_out = fault_run(topology, FaultKind.FAN_DEGRADATION, server, (server, "outlet_temp"))
    assert min(faulty_rpm) < 0.5 * min(quiet_rpm)
    assert max(faulty_out) > max(quiet_out) + 10


def test_dirty_optics_drops_rx_and_raises_ber(topology):
    xcvr = "dc1/hall-a/r01/xcvr-1"
    quiet_rx, faulty_rx = fault_run(topology, FaultKind.DIRTY_OPTICS, xcvr, (xcvr, "rx_power_dbm"))
    quiet_ber, faulty_ber = fault_run(topology, FaultKind.DIRTY_OPTICS, xcvr, (xcvr, "pre_fec_ber"))
    assert min(faulty_rx) < min(quiet_rx) - 5
    assert max(faulty_ber) > 1e-4 > max(quiet_ber)


def test_pdu_overload_pushes_load_pct(topology):
    pdu = "dc1/hall-a/r01/pdu-a"
    quiet, faulty = fault_run(topology, FaultKind.PDU_OVERLOAD, pdu, (pdu, "load_pct"))
    assert max(faulty) > max(quiet) + 15
