"""HTTP routes. Validation in, graph out — zero business logic.

Every handler is: validate (Pydantic does it), call the runner, map state
to the response contract, record metrics, persist. Anything more belongs
in a node, service, or repository.

Auth: /triage, /debug, /history and /metrics are guarded by the pluggable
``require_auth`` dependency (AUTH_MODE=none|api_key|clerk). The UI, docs,
/health and the dataset proxy stay open.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth import require_auth
from app.api.deps import MetricsDep, RepositoryDep, RunnerDep, SettingsDep
from app.api.mappers import state_to_debug_response, state_to_response
from app.schemas.config import AppConfigResponse
from app.schemas.debug import DebugResponse
from app.schemas.history import HistoryRecordOut, HistoryResponse
from app.schemas.triage import HealthResponse, TriageRequest, TriageResponse
from app.utils.logging import request_id_var

router = APIRouter()

UserDep = Annotated[str | None, Depends(require_auth)]
AuthDep = Depends(require_auth)

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_DATASET_URL = "https://ai-stance.vercel.app/api/cases"
_LOCAL_CASES = _STATIC_DIR / "data" / "cases.json"
_cases_cache: dict[str, object] | None = None


@router.get("/", include_in_schema=False)
async def index(settings: SettingsDep) -> object:
    """Dev: legacy static console. Production: redirect to Next.js UI or API landing."""
    from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

    if settings.app_env.strip().lower() == "production":
        frontend = settings.frontend_url.strip()
        if frontend:
            return RedirectResponse(url=frontend, status_code=307)
        return HTMLResponse(
            """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>ViZ Triage Agent — API</title>
  <style>
    body{font-family:system-ui,sans-serif;background:#06080f;color:#e2e8f0;margin:0;min-height:100vh;display:grid;place-items:center;padding:2rem}
    main{max-width:32rem;text-align:center}
    h1{font-size:1.5rem;margin-bottom:.5rem}
    p{color:#94a3b8;line-height:1.6}
    a{color:#22d3ee;margin:0 .35rem}
    code{background:#0f172a;padding:.15rem .4rem;border-radius:.25rem;font-size:.85em}
  </style>
</head>
<body>
  <main>
    <h1>ViZ Triage Agent — API only</h1>
    <p>This Render service runs the FastAPI + LangGraph backend.
       The modern UI is deployed separately on Vercel.</p>
    <p>Set <code>FRONTEND_URL</code> to your Vercel domain to auto-redirect here.</p>
    <p>
      <a href="/docs">API docs</a> ·
      <a href="/health">Health</a> ·
      <a href="/cases">Cases JSON</a>
    </p>
  </main>
</body>
</html>"""
        )

    return FileResponse(_STATIC_DIR / "index.html")


@router.get("/config", response_model=AppConfigResponse, include_in_schema=False)
async def app_config(settings: SettingsDep) -> AppConfigResponse:
    """Frontend bootstrap config (publishable keys only — never secrets)."""
    return AppConfigResponse(
        auth_mode=settings.auth_mode,
        clerk_publishable_key=settings.clerk_publishable_key if settings.clerk_configured else "",
        clerk_configured=settings.clerk_configured,
        search_provider=str(settings.search_provider),
        llm_provider=str(settings.llm_provider),
        debug_enabled=settings.debug_endpoint_enabled,
    )


@router.get("/stats", dependencies=[AuthDep])
async def stats(repository: RepositoryDep, user_id: UserDep) -> dict[str, object]:
    """Dashboard aggregates (scoped to authenticated user when Clerk is on)."""
    uid = user_id if user_id not in (None, "api_key") else None
    return await repository.stats(user_id=uid)


@router.get("/cases", include_in_schema=False)
async def cases() -> dict[str, object]:
    """Proxy the clinical dataset for the UI (cached; avoids browser CORS)."""
    global _cases_cache  # noqa: PLW0603 - simple process-lifetime cache
    if _cases_cache is None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(_DATASET_URL)
                response.raise_for_status()
                _cases_cache = response.json()
        except httpx.HTTPError:
            if _LOCAL_CASES.is_file():
                import json

                _cases_cache = json.loads(_LOCAL_CASES.read_text(encoding="utf-8"))
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Dataset unavailable and no local fallback found",
                ) from None
    return _cases_cache


@router.post("/triage", response_model=TriageResponse, dependencies=[AuthDep])
async def triage(
    request: TriageRequest,
    runner: RunnerDep,
    metrics: MetricsDep,
    repository: RepositoryDep,
    user_id: UserDep,
) -> TriageResponse:
    """Run the triage graph for one patient message.

    Always returns 200 with a valid (possibly degraded) triage response —
    the graph guarantees a safe result on every path. Client errors are
    422 via Pydantic; infrastructure errors surface as 500 through the
    global handler without leaking internals.
    """
    state = await runner.run(
        patient_id=request.patient_id,
        patient_message=request.message,
        request_id=request_id_var.get(),
    )
    metrics.record_run(state)
    response = state_to_response(state)
    uid = user_id if user_id not in (None, "api_key") else None
    await repository.save_run(state, response, user_id=uid)
    return response


@router.post("/debug", response_model=DebugResponse, dependencies=[AuthDep])
async def debug_triage(
    request: TriageRequest,
    runner: RunnerDep,
    metrics: MetricsDep,
    settings: SettingsDep,
    repository: RepositoryDep,
    user_id: UserDep,
) -> DebugResponse:
    """Triage plus full execution trace. Disabled outside dev via config."""
    if not settings.debug_endpoint_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    state = await runner.run(
        patient_id=request.patient_id,
        patient_message=request.message,
        request_id=request_id_var.get(),
    )
    metrics.record_run(state)
    debug_response = state_to_debug_response(state)
    uid = user_id if user_id not in (None, "api_key") else None
    await repository.save_run(state, debug_response.triage, user_id=uid)
    return debug_response


@router.get("/history", response_model=HistoryResponse, dependencies=[AuthDep])
async def history(
    repository: RepositoryDep,
    user_id: UserDep,
    limit: int = Query(default=50, ge=1, le=200),
    patient_id: str | None = Query(default=None, max_length=128),
) -> HistoryResponse:
    """Persisted triage runs, newest first; optionally filtered by patient."""
    uid = user_id if user_id not in (None, "api_key") else None
    if patient_id:
        records = await repository.list_for_patient(patient_id, limit, user_id=uid)
    else:
        records = await repository.list_recent(limit, user_id=uid)
    return HistoryResponse(
        total_stored=await repository.count(user_id=uid),
        count=len(records),
        records=[HistoryRecordOut.model_validate(r) for r in records],
    )


@router.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDep) -> HealthResponse:
    """Liveness + configuration visibility (no secrets)."""
    from app.api.deps import get_database
    from app.services.mcp_health import ping_mcp_server

    db = get_database()
    connected = await db.ping()
    mcp_mode = str(settings.search_provider) == "mcp"
    mcp_configured = bool(settings.mcp_server_url.strip())
    mcp_connected = await ping_mcp_server(settings.mcp_server_url) if mcp_mode and mcp_configured else False
    return HealthResponse(
        status="ok" if connected else "degraded",
        llm_provider=str(settings.llm_provider),
        search_provider=str(settings.search_provider),
        database=db.dialect,
        database_connected=connected,
        auth_mode=settings.auth_mode,
        mcp_agent="stance-medical-search" if mcp_mode else "",
        mcp_configured=mcp_configured,
        mcp_connected=mcp_connected,
    )


@router.get("/metrics", dependencies=[AuthDep])
async def metrics_endpoint(metrics: MetricsDep) -> dict[str, object]:
    """Point-in-time metrics snapshot (JSON; exporter-agnostic)."""
    return metrics.snapshot()
