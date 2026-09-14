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


SERVER_IDLE_W = 140.0
SERVER_MAX_W = 420.0
OVERLOAD_EXTRA_W = 130.0


def server_cpu_load(base: float, offset: float, noise: float, boost: float = 0.0) -> float:
    return clip(base + offset + noise + 0.4 * boost, 0.02, 1.0)


def server_power(cpu_load: float, boost: float = 0.0) -> float:
    return SERVER_IDLE_W + (SERVER_MAX_W - SERVER_IDLE_W) * cpu_load + OVERLOAD_EXTRA_W * boost


def fan_rpm(inlet_temp: float, cpu_load: float, health: float = 1.0) -> float:
    target = 3000.0 + 240.0 * max(inlet_temp - 20.0, 0.0) + 3200.0 * cpu_load
    return clip(target, 2800.0, 9500.0) * health


def outlet_temp(inlet_temp: float, power_w: float, fan_speed_rpm: float) -> float:
    return inlet_temp + power_w / 35.0 * (6000.0 / max(fan_speed_rpm, 500.0))


def switch_power(traffic: float) -> float:
    return 120.0 + 45.0 * traffic


def switch_fan_rpm(inlet_temp: float, health: float = 1.0) -> float:
    return (4200.0 + 150.0 * max(inlet_temp - 20.0, 0.0)) * health
