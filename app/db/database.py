"""Async engine + session factory wrapper.

Neon PostgreSQL requires SSL — connect_args are set automatically when
the URL targets a cloud host or includes ssl=require.
"""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _connect_args_for_url(url: str) -> dict[str, object]:
    """Build driver-specific connect_args (Neon / cloud Postgres need SSL)."""
    parsed = urlparse(url.replace("+asyncpg", ""))
    host = parsed.hostname or ""
    needs_ssl = "ssl=require" in url or "neon" in host or parsed.scheme.startswith("postgres")
    if needs_ssl and "+asyncpg" in url:
        return {"ssl": True}
    return {}


class Database:
    """Owns the engine and hands out sessions. Nothing else."""

    def __init__(self, url: str) -> None:
        self._url = url
        connect_args = _connect_args_for_url(url)
        self._engine = create_async_engine(
            url,
            echo=False,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self.session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def dialect(self) -> str:
        """Backend name for /health visibility (sqlite / postgresql)."""
        return self._engine.dialect.name

    async def create_all(self) -> None:
        """Create tables if absent. Idempotent; called once at startup."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database ready", extra={"dialect": self.dialect, "ssl": bool(_connect_args_for_url(self._url))})

    async def ping(self) -> bool:
        """Return True if the database accepts a connection."""
        from sqlalchemy import text

        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.error("database ping failed", extra={"error": repr(exc)})
            return False

    async def dispose(self) -> None:
        """Close the pool on shutdown."""
        await self._engine.dispose()

    def session(self) -> AsyncSession:
        """New session (caller manages the transaction via ``async with``)."""
        return self.session_factory()
