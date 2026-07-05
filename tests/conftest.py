"""Test isolation — never hit production Neon or real API keys during pytest."""

from __future__ import annotations

import os

# Must run before app modules load settings / database singletons.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["AUTH_MODE"] = "none"
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")

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


@pytest.fixture()
def test_app() -> FastAPI:
    get_settings.cache_clear()
    get_database.cache_clear()
    get_runner.cache_clear()
    get_metrics_registry.cache_clear()

    app = create_app()
    settings = Settings(debug_endpoint_enabled=True, database_url="sqlite+aiosqlite:///:memory:", auth_mode="none")
    llm = FakeLLM(emergency_case_responses())
    runner = TriageGraphRunner(
        build_triage_graph(build_node_bundle(llm=llm, search_tool=FakeSearchTool(), settings=settings))
    )
    metrics = MetricsRegistry()
    memory_db = Database("sqlite+aiosqlite:///:memory:")

    app.dependency_overrides[get_runner] = lambda: runner
    app.dependency_overrides[get_metrics_registry] = lambda: metrics
    app.dependency_overrides[get_database] = lambda: memory_db
    return app


@pytest.fixture()
async def client(test_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
