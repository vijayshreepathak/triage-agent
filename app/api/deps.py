"""Dependency injection wiring — the application's composition root.

The ONLY module that knows concrete implementations. Everything is built
once (cached) and shared across requests, which is safe because every
component is stateless per-request by design.

Tests override ``get_runner`` / ``get_metrics_registry`` via FastAPI's
``app.dependency_overrides`` — no monkeypatching, no network.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.config.settings import Settings, get_settings
from app.db.database import Database
from app.db.repository import TriageRepository
from app.graph.builder import build_triage_graph
from app.graph.runner import TriageGraphRunner
from app.nodes.factory import build_node_bundle
from app.services.metrics import MetricsRegistry
from app.tools.llm_providers import create_llm_client
from app.tools.search_providers import create_search_tool


@lru_cache
def get_metrics_registry() -> MetricsRegistry:
    """Process-lifetime metrics registry."""
    settings = get_settings()
    return MetricsRegistry(
        cost_per_1m_prompt_tokens=settings.cost_per_1m_prompt_tokens,
        cost_per_1m_completion_tokens=settings.cost_per_1m_completion_tokens,
    )


@lru_cache
def get_runner() -> TriageGraphRunner:
    """Build the full stack once: tools -> nodes -> graph -> runner."""
    settings = get_settings()
    metrics = get_metrics_registry()
    llm = create_llm_client(settings, metrics)
    search_tool = create_search_tool(settings)
    bundle = build_node_bundle(llm=llm, search_tool=search_tool, settings=settings)
    return TriageGraphRunner(build_triage_graph(bundle))


@lru_cache
def get_database() -> Database:
    """Process-lifetime database (SQLite default, Postgres via DATABASE_URL)."""
    return Database(get_settings().database_url)


def get_repository() -> TriageRepository:
    """Repository over the shared database (cheap to construct per request)."""
    return TriageRepository(get_database())


SettingsDep = Annotated[Settings, Depends(get_settings)]
RunnerDep = Annotated[TriageGraphRunner, Depends(get_runner)]
MetricsDep = Annotated[MetricsRegistry, Depends(get_metrics_registry)]
RepositoryDep = Annotated[TriageRepository, Depends(get_repository)]
