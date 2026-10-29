from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from twin.api.orm import AssetEdgeRow, DeviceRow, HallRow, RackRow, SiteRow
from twin.api.schemas import DeviceOut, RackOut, SiteOut, TopologyEdge, TopologyGraph, TopologyNode


class AssetQueries:
    sessions: async_sessionmaker[AsyncSession]

    async def list_sites(self) -> list[SiteOut]:
        statement = (
            select(SiteRow.code, SiteRow.name, func.count(func.distinct(HallRow.id)), func.count(RackRow.id))
            .join(HallRow, HallRow.site_id == SiteRow.id, isouter=True)
            .join(RackRow, RackRow.hall_id == HallRow.id, isouter=True)
            .group_by(SiteRow.id)
            .order_by(SiteRow.code)
        )
        async with self.sessions() as session:
            rows = (await session.execute(statement)).all()
        return [SiteOut(code=code, name=name, halls=halls, racks=racks) for code, name, halls, racks in rows]

    async def list_racks(self, hall: str | None = None) -> list[RackOut]:
        statement = (
            select(RackRow, HallRow.code, SiteRow.code, func.count(DeviceRow.id))
            .join(HallRow, RackRow.hall_id == HallRow.id)
            .join(SiteRow, HallRow.site_id == SiteRow.id)
            .join(DeviceRow, DeviceRow.rack_id == RackRow.id, isouter=True)
            .group_by(RackRow.id, HallRow.code, SiteRow.code)
            .order_by(RackRow.rack_key)
        )
        if hall:
            statement = statement.where(HallRow.code == hall)
        async with self.sessions() as session:
            rows = (await session.execute(statement)).all()
        return [
            RackOut(
                rack_key=rack.rack_key,
                site=site,
                hall=hall_code,
                code=rack.code,
                grid_row=rack.grid_row,
                grid_col=rack.grid_col,
                device_count=count,
            )
            for rack, hall_code, site, count in rows
        ]

    @staticmethod
    def _device_out(device: DeviceRow) -> DeviceOut:
        return DeviceOut(
            device_key=device.device_key,
            site=device.hall.site.code,
            hall=device.hall.code,
            rack_key=device.rack.rack_key if device.rack else None,
            code=device.code,
            device_type=device.device_type,
        )

    def _device_statement(self):
        return select(DeviceRow).options(
            selectinload(DeviceRow.rack), selectinload(DeviceRow.hall).selectinload(HallRow.site)
        )

    async def list_devices(self, rack_key: str | None = None, device_type: str | None = None) -> list[DeviceOut]:
        statement = self._device_statement().order_by(DeviceRow.device_key)
        if rack_key:
            statement = statement.join(RackRow, DeviceRow.rack_id == RackRow.id).where(RackRow.rack_key == rack_key)
        if device_type:
            statement = statement.where(DeviceRow.device_type == device_type)
        async with self.sessions() as session:
            devices = (await session.execute(statement)).scalars().all()
        return [self._device_out(device) for device in devices]

    async def get_device(self, device_key: str) -> DeviceOut | None:
        statement = self._device_statement().where(DeviceRow.device_key == device_key)
        async with self.sessions() as session:
            device = (await session.execute(statement)).scalar_one_or_none()
        return self._device_out(device) if device else None

    async def topology(self) -> TopologyGraph:
        racks = await self.list_racks()
        devices = await self.list_devices()
        async with self.sessions() as session:
            edge_rows = (await session.execute(select(AssetEdgeRow))).scalars().all()
        nodes = [
            TopologyNode(
                id=rack.rack_key,
                kind="rack",
                label=rack.code,
                type="rack",
                hall_key=f"{rack.site}/{rack.hall}",
                grid_row=rack.grid_row,
                grid_col=rack.grid_col,
            )
            for rack in racks
        ]
        nodes += [
            TopologyNode(
                id=device.device_key,
                kind="device",
                label=device.code,
                type=device.device_type,
                hall_key=f"{device.site}/{device.hall}",
            )
            for device in devices
        ]
        edges = [TopologyEdge(src=edge.src_key, dst=edge.dst_key, relation=edge.relation) for edge in edge_rows]
        return TopologyGraph(nodes=nodes, edges=edges)

    async def asset_edges(self) -> list[tuple[str, str, str]]:
        async with self.sessions() as session:
            rows = (await session.execute(select(AssetEdgeRow))).scalars().all()
        return [(row.src_key, row.dst_key, row.relation) for row in rows]
