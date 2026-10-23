from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from twin.api.deps import get_repository
from twin.api.repository import Repository
from twin.api.schemas import PointOut, ReadingOut, SeriesOut
from twin.common.metrics import ALL_METRICS

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def require_metric(metric: str) -> str:
    if metric not in ALL_METRICS:
        raise HTTPException(status_code=422, detail=f"unknown metric {metric}")
    return metric


def default_window(start: datetime | None, end: datetime | None, minutes: int) -> tuple[datetime, datetime]:
    end = end or datetime.now(timezone.utc)
    start = start or end - timedelta(minutes=minutes)
    if start >= end:
        raise HTTPException(status_code=422, detail="start must be before end")
    return start, end


@router.get("/latest", response_model=list[ReadingOut])
async def latest(
    device_key: str | None = None,
    rack_key: str | None = None,
    metric: str | None = None,
    repo: Repository = Depends(get_repository),
) -> list[ReadingOut]:
    return await repo.latest_readings(device_key, rack_key, metric)


@router.get("/range", response_model=list[PointOut])
async def telemetry_range(
    device_key: str,
    metric: str = Depends(require_metric),
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(5000, ge=1, le=50000),
    repo: Repository = Depends(get_repository),
) -> list[PointOut]:
    start, end = default_window(start, end, 15)
    return await repo.telemetry_range(device_key, metric, start, end, limit)


@router.get("/series", response_model=SeriesOut)
async def series(
    device_key: str,
    metric: str = Depends(require_metric),
    start: datetime | None = None,
    end: datetime | None = None,
    bucket_s: int = Query(60, ge=1, le=86400),
    repo: Repository = Depends(get_repository),
) -> SeriesOut:
    start, end = default_window(start, end, 60)
    points = await repo.telemetry_series(device_key, metric, start, end, bucket_s)
    return SeriesOut(device_key=device_key, metric=metric, bucket_s=bucket_s, points=points)
