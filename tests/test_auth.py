"""Authentication mode tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_database, get_metrics_registry, get_runner, get_settings
from app.api.main import create_app
from app.config.settings import Settings
from app.db.database import Database
from app.graph.builder import build_triage_graph
from app.graph.runner import TriageGraphRunner
from app.nodes.factory import build_node_bundle
from app.services.metrics import MetricsRegistry
from tests.fakes import FakeLLM, FakeSearchTool, emergency_case_responses

CHEST_PAIN_MESSAGE = (
    "I've been having crushing chest pain for the past 20 minutes that radiates to my left arm. "
    "I'm sweating a lot and feel nauseous."
)


def _build_app(**settings_overrides: object) -> FastAPI:
    get_settings.cache_clear()
    get_database.cache_clear()
    get_runner.cache_clear()
    get_metrics_registry.cache_clear()

    app = create_app()
    settings = Settings(
        debug_endpoint_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        **settings_overrides,
    )
    llm = FakeLLM(emergency_case_responses())
    runner = TriageGraphRunner(
        build_triage_graph(build_node_bundle(llm=llm, search_tool=FakeSearchTool(), settings=settings))
    )
    metrics = MetricsRegistry()
    memory_db = Database("sqlite+aiosqlite:///:memory:")

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_runner] = lambda: runner
    app.dependency_overrides[get_metrics_registry] = lambda: metrics
    app.dependency_overrides[get_database] = lambda: memory_db
    return app


@pytest.mark.asyncio
async def test_clerk_mode_rejects_unauthenticated_triage() -> None:
    app = _build_app(
        auth_mode="clerk",
        clerk_publishable_key="pk_test_example",
        clerk_issuer="https://example.clerk.accounts.dev",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/triage",
            json={"patient_id": "case_001", "message": CHEST_PAIN_MESSAGE},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_key_mode_accepts_valid_key() -> None:
    app = _build_app(auth_mode="api_key", api_keys="secret-test-key")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/triage",
            json={"patient_id": "case_001", "message": CHEST_PAIN_MESSAGE},
            headers={"X-API-Key": "secret-test-key"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_config_exposes_clerk_bootstrap_without_secret() -> None:
    app = _build_app(
        auth_mode="clerk",
        clerk_publishable_key="pk_test_example",
        clerk_issuer="https://example.clerk.accounts.dev",
        clerk_secret_key="sk_test_must_not_leak",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/config")
    assert response.status_code == 200
    body = response.json()
    assert body["auth_mode"] == "clerk"
    assert body["clerk_configured"] is True
    assert body["clerk_publishable_key"] == "pk_test_example"
    assert "sk_test" not in response.text
