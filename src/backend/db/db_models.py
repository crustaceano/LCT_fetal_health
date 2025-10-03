# SQLAlchemy модели (async)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, JSON, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID, DOUBLE_PRECISION, JSONB
import uuid
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dataset: Mapped[str] = mapped_column(String(16), nullable=False)
    study_number: Mapped[int]
    started_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    stopped_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String(16), server_default=text("'starting'"))
    meta: Mapped[dict] = mapped_column(JSON, server_default=text("'{}'::jsonb"))
    pipeline: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text(
            """'{"bpm": [], "uterus": [], "window_seconds": 180}'::jsonb"""
        ),
    )
    __table_args__ = (
        CheckConstraint("dataset in ('hypoxia','regular')", name="sessions_dataset_chk"),
        CheckConstraint("status in ('starting','running','stopped','error')", name="sessions_status_chk"),
    )

