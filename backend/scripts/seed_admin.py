"""
Seeds exactly one GOVERNMENT_ADMIN account, from environment variables, if
(and only if) it does not already exist. Safe to run every deploy — it
never resets, deletes, or overwrites existing data (Section 46 of the
architecture doc: "do NOT automatically reset production/demo database
every time the server starts").

Run with:  python -m scripts.seed_admin
"""
import asyncio

from app.core.config import settings
from app.modules.auth import service


async def main() -> None:
    user = await service.create_user_for_seeding(
        username=settings.admin_default_username,
        password=settings.admin_default_password,
        role="GOVERNMENT_ADMIN",
    )
    print(f"Admin user ready: username={user['username']} role={user['role']} (already existed: {user.get('_id') is not None})")


if __name__ == "__main__":
    asyncio.run(main())
