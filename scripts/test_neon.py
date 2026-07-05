"""Quick Neon connectivity check."""
import asyncio

from app.config.settings import get_settings
from app.db.database import Database


async def main() -> None:
    settings = get_settings()
    db = Database(settings.database_url)
    await db.create_all()
    ok = await db.ping()
    print(f"dialect={db.dialect} connected={ok}")
    await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
