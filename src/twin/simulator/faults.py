from dataclasses import dataclass
from enum import StrEnum


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
