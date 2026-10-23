from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SiteRow(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    halls: Mapped[list["HallRow"]] = relationship(back_populates="site")


class HallRow(Base):
    __tablename__ = "halls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    code: Mapped[str] = mapped_column(Text)
    site: Mapped[SiteRow] = relationship(back_populates="halls")
    racks: Mapped[list["RackRow"]] = relationship(back_populates="hall")


class RackRow(Base):
    __tablename__ = "racks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    code: Mapped[str] = mapped_column(Text)
    rack_key: Mapped[str] = mapped_column(Text, unique=True)
    grid_row: Mapped[int] = mapped_column(Integer)
    grid_col: Mapped[int] = mapped_column(Integer)
    power_capacity_w: Mapped[int] = mapped_column(Integer)
    hall: Mapped[HallRow] = relationship(back_populates="racks")
    devices: Mapped[list["DeviceRow"]] = relationship(back_populates="rack")


class DeviceRow(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    rack_id: Mapped[int | None] = mapped_column(ForeignKey("racks.id"))
    code: Mapped[str] = mapped_column(Text)
    device_key: Mapped[str] = mapped_column(Text, unique=True)
    device_type: Mapped[str] = mapped_column(Text)
    rack: Mapped[RackRow | None] = relationship(back_populates="devices")
    hall: Mapped[HallRow] = relationship()


class AssetEdgeRow(Base):
    __tablename__ = "asset_edges"

    src_key: Mapped[str] = mapped_column(Text, primary_key=True)
    dst_key: Mapped[str] = mapped_column(Text, primary_key=True)
    relation: Mapped[str] = mapped_column(Text, primary_key=True)


class PredictionRow(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_key: Mapped[str] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(Text)
    task: Mapped[str] = mapped_column(Text)
    made_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    horizon_step: Mapped[int] = mapped_column(Integer)
    predicted: Mapped[float] = mapped_column(Float)
    lower: Mapped[float] = mapped_column(Float)
    upper: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(Text)


class RiskScoreRow(Base):
    __tablename__ = "risk_scores"

    device_key: Mapped[str] = mapped_column(Text, primary_key=True)
    metric: Mapped[str] = mapped_column(Text, primary_key=True)
    task: Mapped[str] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    risk: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(Text)
    p_warn: Mapped[float] = mapped_column(Float)
    p_crit: Mapped[float] = mapped_column(Float)
    rate_per_hour: Mapped[float] = mapped_column(Float)
    z_score: Mapped[float] = mapped_column(Float)
    breach_step: Mapped[int | None] = mapped_column(Integer)


class AlertRow(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_key: Mapped[str] = mapped_column(Text)
    rack_key: Mapped[str] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    risk_score: Mapped[float | None] = mapped_column(Float)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class RcaResultRow(Base):
    __tablename__ = "rca_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rank: Mapped[int] = mapped_column(Integer)
    root_cause_key: Mapped[str] = mapped_column(Text)
    fault_kind: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    alert_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
