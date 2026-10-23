from fastapi import APIRouter, Depends, HTTPException

from twin.api.deps import get_repository
from twin.api.repository import Repository
from twin.api.schemas import DeviceOut, MetaOut, RackOut, SiteOut, ThresholdOut, TopologyGraph
from twin.common.metrics import DEVICE_METRICS, THRESHOLDS, UNITS

router = APIRouter(tags=["fleet"])


@router.get("/sites", response_model=list[SiteOut])
async def list_sites(repo: Repository = Depends(get_repository)) -> list[SiteOut]:
    return await repo.list_sites()


@router.get("/racks", response_model=list[RackOut])
async def list_racks(hall: str | None = None, repo: Repository = Depends(get_repository)) -> list[RackOut]:
    return await repo.list_racks(hall)


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(
    rack: str | None = None, device_type: str | None = None, repo: Repository = Depends(get_repository)
) -> list[DeviceOut]:
    return await repo.list_devices(rack, device_type)


@router.get("/devices/{site}/{hall}/{rack}/{device}", response_model=DeviceOut)
async def get_device(
    site: str, hall: str, rack: str, device: str, repo: Repository = Depends(get_repository)
) -> DeviceOut:
    found = await repo.get_device(f"{site}/{hall}/{rack}/{device}")
    if found is None:
        raise HTTPException(status_code=404, detail="device not found")
    return found


@router.get("/topology", response_model=TopologyGraph)
async def topology(repo: Repository = Depends(get_repository)) -> TopologyGraph:
    return await repo.topology()


@router.get("/meta", response_model=MetaOut)
async def meta() -> MetaOut:
    return MetaOut(
        device_types={device_type.value: list(metrics) for device_type, metrics in DEVICE_METRICS.items()},
        thresholds=[
            ThresholdOut(
                device_type=device_type.value,
                metric=metric,
                warn=threshold.warn,
                crit=threshold.crit,
                direction=threshold.direction,
                unit=UNITS.get(metric, ""),
            )
            for (device_type, metric), threshold in THRESHOLDS.items()
        ],
    )
