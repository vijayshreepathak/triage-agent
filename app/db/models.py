"""ORM models.

One table for now: every triage run is persisted for audit and history.
JSON columns are used for list-shaped fields — portable across SQLite and
PostgreSQL (where SQLAlchemy maps them to JSONB-compatible storage).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class TriageRecord(Base):
    """A persisted triage run — the clinical audit trail.

    Stores the response contract fields (not internal chain state) so the
    history API can serve records without re-deriving anything.
    """

    __tablename__ = "triage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    patient_id: Mapped[str] = mapped_column(String(128), index=True)
    message: Mapped[str] = mapped_column(Text)
    urgency_level: Mapped[str] = mapped_column(String(16), index=True)
    triage_decision: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer)
    red_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommended_action: Mapped[str] = mapped_column(Text)
    needs_search: Mapped[bool] = mapped_column(Boolean, default=False)
    search_decision_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
