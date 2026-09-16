import random
from collections import defaultdict

from twin.common.metrics import DeviceType
from twin.common.topics import Reading
from twin.common.topology import Topology
from twin.simulator import signals
from twin.simulator.faults import FaultSchedule


def _round(value: float) -> float:
    if abs(value) < 0.01:
        return float(f"{value:.4g}")
    return round(value, 3)


class Simulation:
    def __init__(
        self,
        topology: Topology,
        schedule: FaultSchedule | None = None,
        seed: int = 7,
        setpoint_c: float = 18.0,
        pdu_capacity_w: float = 2400.0,
    ) -> None:
        self.topology = topology
        self.schedule = schedule or FaultSchedule()
        self.setpoint_c = setpoint_c
        self.pdu_capacity_w = pdu_capacity_w
        self.rng = random.Random(seed)
        self._noise: dict[str, signals.Ar1Noise] = {}
        self._outlet: dict[str, float] = {}
        self._rack_scale: dict[str, float] = {}
        self._recirculation: dict[str, float] = {}
        self._server_offset: dict[str, float] = {}
        self._rack_crac: dict[str, str] = {}
        self._rack_devices: dict[str, dict[DeviceType, list[str]]] = {}
        self._hall_racks: dict[str, list[str]] = defaultdict(list)
        self._index()

    def _index(self) -> None:
        for rack_key in sorted(self.topology.racks):
            rack = self.topology.racks[rack_key]
            self._rack_scale[rack_key] = self.rng.uniform(0.85, 1.15)
            self._recirculation[rack_key] = self.rng.uniform(2.0, 4.5)
            self._rack_crac[rack_key] = self.topology.targets_of(rack_key, "cooled_by")[0]
            self._hall_racks[f"{rack.site}/{rack.hall}"].append(rack_key)
            by_type: dict[DeviceType, list[str]] = defaultdict(list)
            for device in sorted(self.topology.devices_in_rack(rack_key), key=lambda item: item.key):
                by_type[device.type].append(device.key)
                if device.type is DeviceType.SERVER:
                    self._server_offset[device.key] = self.rng.uniform(-0.08, 0.08)
            self._rack_devices[rack_key] = by_type

    def _noise_for(self, key: str, sigma: float = 0.02, phi: float = 0.9) -> float:
        if key not in self._noise:
            self._noise[key] = signals.Ar1Noise(self.rng, phi=phi, sigma=sigma)
        return self._noise[key].next()

    def step(self, t: float, dt_s: float = 5.0) -> list[Reading]:
        effects = self.schedule.effects_at(t)
        diurnal = signals.diurnal_factor(t)
        readings: list[Reading] = []

        def emit(key: str, metric: str, value: float) -> None:
            readings.append(Reading(key, metric, t, _round(value)))

        rack_load = {
            rack_key: signals.clip(diurnal * scale + self._noise_for(rack_key + "#load", 0.01), 0.05, 0.98)
            for rack_key, scale in self._rack_scale.items()
        }
        hall_load = {
            hall_key: sum(rack_load[rack_key] for rack_key in rack_keys) / len(rack_keys)
            for hall_key, rack_keys in self._hall_racks.items()
        }
        supply = self._step_cracs(effects.cooling_factor, hall_load, emit)
        for rack_key in sorted(self._rack_scale):
            self._step_rack(rack_key, rack_load[rack_key], supply[self._rack_crac[rack_key]], effects, dt_s, emit)
        return readings

    def _step_cracs(self, cooling_factors, hall_load, emit) -> dict[str, float]:
        supply: dict[str, float] = {}
        for crac in self.topology.devices_of_type(DeviceType.CRAC):
            load = hall_load[crac.hall_key]
            cooling = cooling_factors.get(crac.key, 1.0)
            supply_temp = signals.crac_supply_temp(self.setpoint_c, cooling, load)
            supply_temp += self._noise_for(crac.key, 0.03)
            effort = signals.crac_cooling_pct(load, cooling)
            supply[crac.key] = supply_temp
            emit(crac.key, "supply_temp", supply_temp)
            emit(crac.key, "return_temp", signals.crac_return_temp(supply_temp, load))
            emit(crac.key, "cooling_pct", effort)
            emit(crac.key, "fan_rpm", signals.crac_fan_rpm(effort))
            emit(crac.key, "power_w", signals.crac_power(effort))
        return supply

    def _step_rack(self, rack_key, load, supply_temp, effects, dt_s, emit) -> None:
        devices = self._rack_devices[rack_key]
        inlet = signals.rack_inlet_temp(
            supply_temp, self._recirculation[rack_key], load, self._noise_for(rack_key + "#inlet", 0.15, 0.8)
        )
        pdu_key = devices[DeviceType.PDU][0]
        boost = effects.load_boost.get(pdu_key, 0.0)
        powers: list[float] = []
        for key in devices[DeviceType.SERVER]:
            cpu = signals.server_cpu_load(load, self._server_offset[key], self._noise_for(key, 0.03), boost)
            power = signals.server_power(cpu, boost)
            fan = signals.fan_rpm(inlet, cpu, effects.fan_health.get(key, 1.0)) + self._noise_for(key + "#fan", 20.0)
            target = signals.outlet_temp(inlet, power, fan)
            previous = self._outlet.get(key, target)
            self._outlet[key] = signals.smooth(previous, target, dt_s, 90.0)
            powers.append(power)
            emit(key, "cpu_load", cpu)
            emit(key, "power_w", power)
            emit(key, "fan_rpm", fan)
            emit(key, "inlet_temp", inlet)
            emit(key, "outlet_temp", self._outlet[key])
        traffic = signals.clip(load + self._noise_for(rack_key + "#traffic", 0.02), 0.0, 1.0)
        switch_key = devices[DeviceType.SWITCH][0]
        switch_power = signals.switch_power(traffic)
        powers.append(switch_power)
        emit(switch_key, "power_w", switch_power)
        emit(switch_key, "fan_rpm", signals.switch_fan_rpm(inlet, effects.fan_health.get(switch_key, 1.0)))
        emit(switch_key, "inlet_temp", inlet)
        for key in devices[DeviceType.TRANSCEIVER]:
            temp = signals.module_temp(inlet, traffic)
            rx = signals.rx_power_dbm(
                signals.NOMINAL_RX_DBM, effects.optics_loss_db.get(key, 0.0), self._noise_for(key + "#rx", 0.03)
            )
            tx = signals.tx_power_dbm(signals.NOMINAL_TX_DBM, temp, self._noise_for(key + "#tx", 0.02))
            ber = signals.pre_fec_ber(rx, temp, self._noise_for(key + "#ber", 0.08))
            emit(key, "module_temp", temp)
            emit(key, "rx_power_dbm", rx)
            emit(key, "tx_power_dbm", tx)
            emit(key, "pre_fec_ber", ber)
        pdu_total = signals.pdu_power(powers)
        emit(pdu_key, "power_w", pdu_total)
        emit(pdu_key, "current_a", signals.pdu_current(pdu_total))
        emit(pdu_key, "load_pct", signals.pdu_load_pct(pdu_total, self.pdu_capacity_w))
