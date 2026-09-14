import json
import math

from twin.common.metrics import UNITS


class PayloadError(ValueError):
    pass


def encode_payload(ts: float, value: float, metric: str | None = None) -> bytes:
    body: dict[str, float | str] = {"ts": round(ts, 3), "value": value}
    if metric in UNITS:
        body["unit"] = UNITS[metric]
    return json.dumps(body, separators=(",", ":")).encode()


def decode_payload(raw: bytes | str) -> tuple[float, float]:
    try:
        body = json.loads(raw)
        ts = float(body["ts"])
        value = float(body["value"])
    except (ValueError, KeyError, TypeError) as exc:
        raise PayloadError(f"malformed payload: {exc}") from exc
    if not math.isfinite(value) or not math.isfinite(ts):
        raise PayloadError("non finite number in payload")
    return ts, value
