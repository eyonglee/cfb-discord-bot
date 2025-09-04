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
    
async def get_teams():
    """
    Fetch all teams from the teams table.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM teams;")
        return [dict(row) for row in rows]
    
async def get_team(team_id: int):
    """Fetch a single team by its primary key (team_id). Returns dict or None."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM teams WHERE team_id = $1;", team_id)
        return dict(row) if row else None

async def get_user(discord_id: int):
    """Fetch a single user by Discord ID (users.discord_id). Returns dict or None."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE discord_id = $1;", discord_id)
        return dict(row) if row else None
    
async def get_user_team(discord_id: int):
    """Fetch the team associated with a specific user by their Discord ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT u.*, t.* FROM teams t
            JOIN users u ON t.team_id = u.team_id
            WHERE u.discord_id = $1;
        """, discord_id)
        return dict(row) if row else None

async def add_result(result):
    """
    result = {
        week_num: int,
        discord_id: int,
        opponent_id: int,
        user_score: int,
        opponent_score: int,
        user_win: bool
    }
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO games (week_num, discord_id, opponent_id, user_score, opp_score, user_win, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, now(), now())
        ON CONFLICT (week_num, discord_id)
        DO UPDATE SET opponent_id = EXCLUDED.opponent_id,
                      user_score = EXCLUDED.user_score,
                      opp_score = EXCLUDED.opp_score,
                      user_win = EXCLUDED.user_win,
                      updated_at = now();
        """
        await conn.execute(
            query,
            1,
            result["discord_id"],
            result["opponent_id"],
            result["user_score"],
            result["opponent_score"],
            result["user_win"]
        )

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
    
async def get_games_from_week(week_num: int):
    """
    Fetch all games from a specific week.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM games WHERE week_num = $1;", week_num)
        return [dict(row) for row in rows]
    
async def get_games_from_user(discord_id: int):
    """
    Fetch all games reported by a specific user.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM games WHERE discord_id = $1;", discord_id)
        return [dict(row) for row in rows]
    
async def get_game(week_num: int, discord_id: int):
    """
    Fetch a specific game reported by a user in a specific week.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM games WHERE week_num = $1 AND discord_id = $2;",
            week_num,
            discord_id
        )
        return dict(row) if row else None
    

async def get_standings():
    """
    Calculate and return the current standings of all users.
    Returns a list of dicts with keys: discord_id, wins, losses, ties, total_games
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                discord_id,
                SUM(CASE WHEN user_win = TRUE THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN user_win = FALSE THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN user_win IS NULL THEN 1 ELSE 0 END) AS ties,
                COUNT(*) AS total_games
            FROM games
            GROUP BY discord_id
            ORDER BY wins DESC, losses ASC, ties DESC;
        """)
        return [dict(row) for row in rows]