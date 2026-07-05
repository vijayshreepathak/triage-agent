"""Pluggable authentication (config-driven, zero-friction by default).

Three modes, selected by AUTH_MODE:

- ``none``     open access (default — dev / demo).
- ``api_key``  X-API-Key header checked against a configured key set.
- ``clerk``    Authorization: Bearer <JWT> verified against Clerk's JWKS
               (RS256 signature + issuer check). Works with any Clerk app:
               set CLERK_JWKS_URL and CLERK_ISSUER from the dashboard.

Design: one FastAPI dependency (``require_auth``) guards every protected
route. Failures are uniform 401s with no detail about which check failed —
never leak whether a key exists.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.config.settings import Settings, get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required.",
    headers={"WWW-Authenticate": "Bearer"},
)

# PyJWKClient caches keys internally; cache the client per JWKS URL.
_jwk_clients: dict[str, object] = {}


def _get_jwk_client(jwks_url: str) -> object:
    if jwks_url not in _jwk_clients:
        import jwt

        _jwk_clients[jwks_url] = jwt.PyJWKClient(jwks_url, cache_keys=True)
    return _jwk_clients[jwks_url]


def _verify_clerk_token(token: str, settings: Settings) -> dict[str, object]:
    """Verify a Clerk session JWT (sync — run in a worker thread)."""
    import jwt

    jwks_url = settings.clerk_jwks_url_resolved
    client = _get_jwk_client(jwks_url)
    signing_key = client.get_signing_key_from_jwt(token)  # type: ignore[attr-defined]
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.clerk_issuer or None,
        options={"verify_aud": False},  # Clerk session tokens carry azp, not aud
    )


async def require_auth(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> str | None:
    """Route dependency: allow, or raise a uniform 401.

    Returns:
        Authenticated user id (Clerk ``sub``) when auth_mode=clerk, else None.
    """
    if settings.auth_mode == "none":
        return None

    if settings.auth_mode == "api_key":
        provided = request.headers.get("X-API-Key", "")
        accepted = {k.strip() for k in settings.api_keys.split(",") if k.strip()}
        if provided and provided in accepted:
            return "api_key"
        raise _UNAUTHORIZED

    if settings.auth_mode == "clerk":
        if not settings.clerk_configured:
            logger.error("auth_mode=clerk but Clerk keys are incomplete (publishable key + JWKS/issuer)")
            raise _UNAUTHORIZED
        jwks_url = settings.clerk_jwks_url_resolved
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise _UNAUTHORIZED
        token = auth_header.removeprefix("Bearer ").strip()
        try:
            claims = await asyncio.to_thread(_verify_clerk_token, token, settings)
        except Exception:
            logger.warning("clerk token verification failed")
            raise _UNAUTHORIZED from None
        user_id = str(claims.get("sub", ""))
        request.state.user_id = user_id
        return user_id

    raise _UNAUTHORIZED


AuthDep = Depends(require_auth)
