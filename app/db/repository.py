"""Triage history repository.

The only place SQL queries live. Consumers (routes) speak in domain terms:
save a run, list recent runs, list runs for a patient. Persistence failure
must never fail a triage — ``save_run`` contains its own errors and
reports success as a bool so callers can log-and-continue.
"""

from __future__ import annotations

from sqlalchemy import desc, select

from app.db.database import Database
from app.db.models import TriageRecord
from app.models.state import GraphState
from app.schemas.triage import TriageResponse
from app.utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


class TriageRepository:
    """CRUD for triage records over an injected Database."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def save_run(
        self, state: GraphState, response: TriageResponse, *, user_id: str | None = None
    ) -> bool:
        """Persist one completed run. Never raises — triage already succeeded."""
        record = TriageRecord(
            user_id=user_id,
            request_id=response.request_id,
            patient_id=response.patient_message_id,
            message=state.patient_message,
            urgency_level=str(response.urgency_level),
            triage_decision=response.triage_decision,
            reasoning=response.reasoning,
            confidence=response.confidence,
            red_flags=response.red_flags,
            sources=response.sources,
            recommended_action=response.recommended_action,
            needs_search=state.needs_search,
            search_decision_reason=state.search_decision_reason,
            latency_ms=float(state.metadata.get("graph_latency_ms", 0.0)),
            error_count=len(state.errors),
        )
        try:
            async with self._db.session() as session:
                session.add(record)
                await session.commit()
            return True
        except Exception as exc:
            logger.error("failed to persist triage record", extra={"error": repr(exc)})
            return False

    async def list_recent(
        self, limit: int = _DEFAULT_LIMIT, *, user_id: str | None = None
    ) -> list[TriageRecord]:
        """Most recent runs, newest first; optionally scoped to one user."""
        limit = max(1, min(limit, _MAX_LIMIT))
        async with self._db.session() as session:
            stmt = select(TriageRecord).order_by(desc(TriageRecord.created_at)).limit(limit)
            if user_id:
                stmt = stmt.where(TriageRecord.user_id == user_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def count(self, *, user_id: str | None = None) -> int:
        """Total persisted runs (for /health and the UI dashboard)."""
        from sqlalchemy import func

        async with self._db.session() as session:
            stmt = select(func.count(TriageRecord.id))
            if user_id:
                stmt = stmt.where(TriageRecord.user_id == user_id)
            result = await session.execute(stmt)
            return int(result.scalar() or 0)

    async def list_for_patient(self, patient_id: str, limit: int = _DEFAULT_LIMIT) -> list[TriageRecord]:
        """Runs for one patient id, newest first."""
        limit = max(1, min(limit, _MAX_LIMIT))
        async with self._db.session() as session:
            result = await session.execute(
                select(TriageRecord)
                .where(TriageRecord.patient_id == patient_id)
                .order_by(desc(TriageRecord.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())

    async def stats(self, *, user_id: str | None = None) -> dict[str, object]:
        """Aggregate urgency counts for the dashboard."""
        from sqlalchemy import func

        async with self._db.session() as session:
            stmt = select(TriageRecord.urgency_level, func.count(TriageRecord.id)).group_by(
                TriageRecord.urgency_level
            )
            if user_id:
                stmt = stmt.where(TriageRecord.user_id == user_id)
            rows = await session.execute(stmt)
            by_urgency = {level: count for level, count in rows.all()}
            return {"total": await self.count(user_id=user_id), "by_urgency": by_urgency}
