import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from twin.api.repository import Repository

router = APIRouter(tags=["live"])


def apply_filter(readings, device_key: str | None, metrics: set[str] | None):
    return [
        reading
        for reading in readings
        if (not device_key or reading.device_key == device_key) and (not metrics or reading.metric in metrics)
    ]


@router.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    repo: Repository = websocket.app.state.repository
    interval = websocket.app.state.settings.live_interval_s
    device_key: str | None = websocket.query_params.get("device_key")
    metrics: set[str] | None = set(filter(None, websocket.query_params.get("metrics", "").split(","))) or None
    cursor = datetime.now(timezone.utc) - timedelta(seconds=5)
    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=interval)
                update = json.loads(raw)
                device_key = update.get("device_key") or None
                metrics = set(update.get("metrics") or []) or None
                continue
            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "expected json"})
                continue
            readings = apply_filter(await repo.readings_since(cursor, device_key), device_key, metrics)
            if readings:
                cursor = max(reading.ts for reading in readings)
                await websocket.send_json(
                    {
                        "type": "telemetry",
                        "points": [json.loads(reading.model_dump_json()) for reading in readings],
                    }
                )
            else:
                await websocket.send_json({"type": "heartbeat", "ts": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        return
