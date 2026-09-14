import math
import random
from dataclasses import dataclass, field


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def diurnal_factor(epoch_s: float, peak_hour: float = 14.0) -> float:
    hour = (epoch_s / 3600.0) % 24.0
    daily = 0.5 + 0.28 * math.cos(2 * math.pi * (hour - peak_hour) / 24.0)
    shoulder = 0.05 * math.cos(4 * math.pi * (hour - 10.0) / 24.0)
    return clip(daily + shoulder, 0.1, 0.95)


@dataclass
class Ar1Noise:
    rng: random.Random
    phi: float = 0.9
    sigma: float = 0.02
    state: float = field(default=0.0, init=False)

    def next(self) -> float:
        self.state = self.phi * self.state + self.rng.gauss(0.0, self.sigma)
        return self.state


def smooth(previous: float, target: float, dt_s: float, tau_s: float) -> float:
    alpha = 1.0 - math.exp(-dt_s / tau_s)
    return previous + alpha * (target - previous)
