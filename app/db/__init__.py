"""Persistence layer: async SQLAlchemy engine, ORM models, repositories.

SQLite (aiosqlite) by default so the app runs with zero infrastructure;
PostgreSQL (asyncpg) in production via a single DATABASE_URL change —
e.g. ``postgresql+asyncpg://user:pass@host:5432/triage``. The repository
pattern keeps every consumer ignorant of which engine is underneath.
"""
