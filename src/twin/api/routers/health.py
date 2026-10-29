from fastapi import APIRouter, Depends, Query

from twin.api.deps import get_repository
from twin.api.health import FleetHealth
from twin.api.repository import Repository
from twin.api.schemas import HealthSummary, Offender, RackHealth

router = APIRouter(prefix="/health", tags=["health"])


async def load_fleet(repo: Repository) -> FleetHealth:
    devices = await repo.list_devices()
    readings = await repo.latest_readings()
    alerts = await repo.alerts(None, None, 2000)
    return FleetHealth(devices, readings, alerts)


@router.get("/racks", response_model=list[RackHealth])
async def racks(repo: Repository = Depends(get_repository)) -> list[RackHealth]:
    return (await load_fleet(repo)).racks()


@router.get("/offenders", response_model=list[Offender])
async def offenders(limit: int = Query(10, ge=1, le=100), repo: Repository = Depends(get_repository)) -> list[Offender]:
    return (await load_fleet(repo)).offenders(limit)


@router.get("/summary", response_model=HealthSummary)
async def summary(repo: Repository = Depends(get_repository)) -> HealthSummary:
    return (await load_fleet(repo)).summary()
