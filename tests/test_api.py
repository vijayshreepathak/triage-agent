"""API layer tests — full HTTP stack with the graph running on fakes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

CHEST_PAIN_MESSAGE = (
    "I've been having crushing chest pain for the past 20 minutes that radiates to my left arm. "
    "I'm sweating a lot and feel nauseous."
)


@pytest.mark.asyncio
async def test_triage_returns_complete_contract(client: AsyncClient) -> None:
    response = await client.post("/triage", json={"patient_id": "case_001", "message": CHEST_PAIN_MESSAGE})

    assert response.status_code == 200
    body = response.json()
    assert body["patient_message_id"] == "case_001"
    assert body["urgency_level"] == "emergency"
    assert body["red_flags"]  # deterministic rule + llm union
    assert 0 <= body["confidence"] <= 100
    assert body["disclaimers"]  # hardcoded, always present
    assert "emergency" in body["recommended_action"].lower() or "911" in body["recommended_action"]
    assert body["request_id"]
    # Request ID is echoed as a header for correlation.
    assert response.headers["X-Request-ID"] == body["request_id"]


@pytest.mark.asyncio
async def test_triage_validation_rejects_bad_input(client: AsyncClient) -> None:
    empty_message = await client.post("/triage", json={"patient_id": "p1", "message": ""})
    missing_field = await client.post("/triage", json={"message": "hello"})

    assert empty_message.status_code == 422
    assert missing_field.status_code == 422


@pytest.mark.asyncio
async def test_health_reports_providers(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "llm_provider" in body and "search_provider" in body


@pytest.mark.asyncio
async def test_metrics_accumulate_after_requests(client: AsyncClient) -> None:
    await client.post("/triage", json={"patient_id": "case_001", "message": CHEST_PAIN_MESSAGE})
    response = await client.get("/metrics")

    body = response.json()
    assert body["requests_total"] == 1
    assert body["searches_skipped_total"] == 1  # emergency case skips search
    assert body["graph_latency_ms"]["count"] == 1
    assert "parse_input" in body["node_latency_ms"]


@pytest.mark.asyncio
async def test_debug_returns_trace_without_root_causes(client: AsyncClient) -> None:
    response = await client.post("/debug", json={"patient_id": "case_001", "message": CHEST_PAIN_MESSAGE})

    assert response.status_code == 200
    body = response.json()
    assert body["triage"]["urgency_level"] == "emergency"
    assert body["search_decision_reason"] == "skip_emergency_time_critical"
    node_names = [t["node_name"] for t in body["execution_trace"]]
    assert "search_medical_sources" not in node_names  # skipped node absent from trace
    assert len(node_names) == 10
    # No internal detail leaks: errors expose user-safe fields only.
    for error in body["errors"]:
        assert "root_cause" not in error


@pytest.mark.asyncio
async def test_custom_request_id_is_propagated(client: AsyncClient) -> None:
    response = await client.post(
        "/triage",
        json={"patient_id": "case_001", "message": CHEST_PAIN_MESSAGE},
        headers={"X-Request-ID": "my-custom-id"},
    )
    assert response.headers["X-Request-ID"] == "my-custom-id"
    assert response.json()["request_id"] == "my-custom-id"
