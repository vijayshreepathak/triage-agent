"""History endpoint contracts (projection of persisted TriageRecord rows)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HistoryRecordOut(BaseModel):
    """One persisted triage run, as served by GET /history."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: str
    patient_id: str
    message: str
    urgency_level: str
    triage_decision: str
    reasoning: str
    confidence: int
    red_flags: list[str]
    sources: list[str]
    recommended_action: str
    needs_search: bool
    search_decision_reason: str | None
    latency_ms: float
    created_at: datetime


class HistoryResponse(BaseModel):
    """GET /history response body."""

    total_stored: int
    count: int
    records: list[HistoryRecordOut] = Field(default_factory=list)
