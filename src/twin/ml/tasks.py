from dataclasses import dataclass

from twin.common.metrics import DeviceType


@dataclass(frozen=True)
class ForecastTask:
    name: str
    device_type: DeviceType
    features: tuple[str, ...]
    targets: tuple[str, ...]
    log10_metrics: tuple[str, ...] = ()

    @property
    def target_index(self) -> list[int]:
        return [self.features.index(target) for target in self.targets]

    def is_log(self, metric: str) -> bool:
        return metric in self.log10_metrics


TASKS: dict[str, ForecastTask] = {
    "thermal": ForecastTask(
        name="thermal",
        device_type=DeviceType.SERVER,
        features=("inlet_temp", "outlet_temp", "cpu_load", "fan_rpm", "power_w"),
        targets=("inlet_temp", "outlet_temp"),
    ),
    "power": ForecastTask(
        name="power",
        device_type=DeviceType.PDU,
        features=("power_w", "current_a", "load_pct"),
        targets=("power_w", "load_pct"),
    ),
    "ber": ForecastTask(
        name="ber",
        device_type=DeviceType.TRANSCEIVER,
        features=("rx_power_dbm", "tx_power_dbm", "module_temp", "pre_fec_ber"),
        targets=("rx_power_dbm", "pre_fec_ber"),
        log10_metrics=("pre_fec_ber",),
    ),
}


@dataclass(frozen=True)
class WindowConfig:
    input_len: int = 60
    horizon: int = 30
    step_s: int = 60
    stride: int = 3
