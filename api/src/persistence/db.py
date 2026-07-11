import asyncpg


async def create_pool(dsn: str) -> asyncpg.Pool:
    # asyncpg needs postgresql:// not postgresql+asyncpg://
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.create_pool(dsn, min_size=5, max_size=20, command_timeout=30)


async def close_pool(pool: asyncpg.Pool):
    await pool.close()
