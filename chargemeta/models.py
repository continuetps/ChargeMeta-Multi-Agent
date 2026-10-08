from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from .db import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class PortableVector(TypeDecorator):
    """pgvector on PostgreSQL, JSON array on SQLite for local zero-config mode."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(Vector(384) if dialect.name == "postgresql" else JSON())


class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[str] = mapped_column(String(30), default="sqlite")
    url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    tables: Mapped[list["AssetTable"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class AssetTable(Base):
    __tablename__ = "asset_tables"
    __table_args__ = (UniqueConstraint("source_id", "schema_name", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    schema_name: Mapped[str] = mapped_column(String(100), default="main")
    name: Mapped[str] = mapped_column(String(150), index=True)
    comment: Mapped[str | None] = mapped_column(Text)
    ai_comment: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(50), index=True)
    row_count: Mapped[int | None] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=0)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    source: Mapped[DataSource] = relationship(back_populates="tables")
    columns: Mapped[list["AssetColumn"]] = relationship(back_populates="table", cascade="all, delete-orphan")


class AssetColumn(Base):
    __tablename__ = "asset_columns"
    __table_args__ = (UniqueConstraint("table_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("asset_tables.id"))
    name: Mapped[str] = mapped_column(String(150), index=True)
    data_type: Mapped[str] = mapped_column(String(100))
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    primary_key: Mapped[bool] = mapped_column(Boolean, default=False)
    comment: Mapped[str | None] = mapped_column(Text)
    business_name: Mapped[str | None] = mapped_column(String(150), index=True)
    ai_comment: Mapped[str | None] = mapped_column(Text)
    semantic_type: Mapped[str | None] = mapped_column(String(50))
    sensitivity: Mapped[str] = mapped_column(String(30), default="L1-公开")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    search_text: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(PortableVector())
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    table: Mapped[AssetTable] = relationship(back_populates="columns")


class InventoryJob(Base):
    __tablename__ = "inventory_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    status: Mapped[str] = mapped_column(String(30), default="created")
    stage: Mapped[str] = mapped_column(String(50), default="created")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[int] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AssetRelation(Base):
    __tablename__ = "asset_relations"
    __table_args__ = (UniqueConstraint("source_column_id", "target_column_id", "relation_type"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_column_id: Mapped[int] = mapped_column(ForeignKey("asset_columns.id"))
    target_column_id: Mapped[int] = mapped_column(ForeignKey("asset_columns.id"))
    relation_type: Mapped[str] = mapped_column(String(30), default="logical_fk")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")


class MetadataChange(Base):
    __tablename__ = "metadata_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    asset_type: Mapped[str] = mapped_column(String(20))
    asset_name: Mapped[str] = mapped_column(String(300))
    change_type: Mapped[str] = mapped_column(String(30))
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(30), default="v1")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("inventory_jobs.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(50), index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="running")
    input_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    output_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class ReviewTask(Base):
    __tablename__ = "review_tasks"
    __table_args__ = (UniqueConstraint("job_id", "column_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("inventory_jobs.id"), index=True)
    column_id: Mapped[int] = mapped_column(ForeignKey("asset_columns.id"), index=True)
    reason: Mapped[str] = mapped_column(String(200))
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    ai_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    resolution: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
