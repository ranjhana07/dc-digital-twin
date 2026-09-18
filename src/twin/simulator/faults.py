import random
from dataclasses import dataclass
from enum import StrEnum

from twin.common.metrics import DeviceType
from twin.common.topology import Topology


class FaultKind(StrEnum):
    COOLING_FAILURE = "cooling_failure"
    FAN_DEGRADATION = "fan_degradation"
    DIRTY_OPTICS = "dirty_optics"
    PDU_OVERLOAD = "pdu_overload"


@dataclass(frozen=True)
class FaultSpec:
    kind: FaultKind
    target: str
    start_s: float
    duration_s: float
    ramp_s: float = 600.0
    recovery_s: float = 300.0
    magnitude: float = 1.0

    @property
    def end_s(self) -> float:
        return self.start_s + self.duration_s

    def intensity(self, t: float) -> float:
        if t < self.start_s:
            return 0.0
        if t < self.start_s + self.ramp_s:
            return self.magnitude * (t - self.start_s) / self.ramp_s
        if t <= self.end_s:
            return self.magnitude
        if t < self.end_s + self.recovery_s:
            return self.magnitude * (1.0 - (t - self.end_s) / self.recovery_s)
        return 0.0

    def active(self, t: float) -> bool:
        return self.start_s <= t < self.end_s + self.recovery_s


@dataclass
class FaultEffects:
    cooling_factor: dict[str, float]
    fan_health: dict[str, float]
    optics_loss_db: dict[str, float]
    load_boost: dict[str, float]

    @classmethod
    def empty(cls) -> "FaultEffects":
        return cls({}, {}, {}, {})


COOLING_LOSS = 0.85
FAN_LOSS = 0.65
OPTICS_LOSS_DB = 9.0


class FaultSchedule:
    def __init__(self, specs: list[FaultSpec] | None = None) -> None:
        self.specs = sorted(specs or [], key=lambda spec: spec.start_s)

    def active_specs(self, t: float) -> list[FaultSpec]:
        return [spec for spec in self.specs if spec.active(t)]

    def effects_at(self, t: float) -> FaultEffects:
        effects = FaultEffects.empty()
        for spec in self.active_specs(t):
            level = spec.intensity(t)
            if spec.kind is FaultKind.COOLING_FAILURE:
                effects.cooling_factor[spec.target] = 1.0 - COOLING_LOSS * level
            elif spec.kind is FaultKind.FAN_DEGRADATION:
                effects.fan_health[spec.target] = 1.0 - FAN_LOSS * level
            elif spec.kind is FaultKind.DIRTY_OPTICS:
                effects.optics_loss_db[spec.target] = OPTICS_LOSS_DB * level
            elif spec.kind is FaultKind.PDU_OVERLOAD:
                effects.load_boost[spec.target] = level
        return effects


FAULT_TARGET_TYPES = {
    FaultKind.COOLING_FAILURE: DeviceType.CRAC,
    FaultKind.FAN_DEGRADATION: DeviceType.SERVER,
    FaultKind.DIRTY_OPTICS: DeviceType.TRANSCEIVER,
    FaultKind.PDU_OVERLOAD: DeviceType.PDU,
}


def random_schedule(
    topology: Topology,
    seed: int,
    start_s: float,
    horizon_s: float,
    count: int,
    min_duration_s: float = 2400.0,
    max_duration_s: float = 7200.0,
) -> FaultSchedule:
    rng = random.Random(seed)
    kinds = list(FaultKind)
    slot = horizon_s / max(count, 1)
    specs: list[FaultSpec] = []
    for index in range(count):
        kind = kinds[index % len(kinds)]
        candidates = sorted(device.key for device in topology.devices_of_type(FAULT_TARGET_TYPES[kind]))
        duration = rng.uniform(min_duration_s, min(max_duration_s, slot * 0.8))
        offset = rng.uniform(0.05, 0.95) * (slot - duration)
        specs.append(
            FaultSpec(
                kind=kind,
                target=rng.choice(candidates),
                start_s=start_s + index * slot + max(offset, 0.0),
                duration_s=duration,
                magnitude=rng.uniform(0.8, 1.0),
            )
        )
    return FaultSchedule(specs)
