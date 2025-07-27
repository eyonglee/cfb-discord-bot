

import os
import asyncpg
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Read the database URL
DATABASE_URL = os.getenv("DATABASE_URL")

_pool: asyncpg.pool.Pool | None = None

async def init_db_pool():
    """
    Initialize the global asyncpg pool. Call once on bot startup.
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool

async def get_db_pool():
    """
    Return the initialized pool. Raises if init_db_pool() was not called.
    """
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db_pool() first.")
    return _pool

async def get_active_week():
    """
    Fetch the currently active week number from the weeks table.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT week_num FROM weeks WHERE active = TRUE LIMIT 1;"
        )
        return row["week_num"] if row else None
    
async def get_users():
    """
    Fetch all users from the users table.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users;")
        return [dict(row) for row in rows]