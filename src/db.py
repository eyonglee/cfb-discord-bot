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

# ------------------------------
# Internal DB helper utilities
# ------------------------------

async def _fetchrow_dict(query: str, *args):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None

async def _fetch_dict(query: str, *args):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]

async def _execute(query: str, *args):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)

async def get_active_week():
    """Return the active week number, or None if not set."""
    row = await _fetchrow_dict("SELECT week_num FROM weeks WHERE active = TRUE LIMIT 1;")
    return row["week_num"] if row else None
    
async def get_users():
    """
    Fetch all users from the users table.
    """
    return await _fetch_dict("SELECT * FROM users;")
    
async def get_teams():
    """
    Fetch all teams from the teams table.
    """
    return await _fetch_dict("SELECT * FROM teams;")
    
async def get_team(team_id: int):
    """Fetch a single team by its primary key (team_id). Returns dict or None."""
    return await _fetchrow_dict("SELECT * FROM teams WHERE team_id = $1;", team_id)

async def get_user(discord_id: int):
    """Fetch a single user by Discord ID (users.discord_id). Returns dict or None."""
    return await _fetchrow_dict("SELECT * FROM users WHERE discord_id = $1;", discord_id)
    
async def get_user_team(discord_id: int):
    """Fetch the team associated with a specific user by their Discord ID."""
    return await _fetchrow_dict(
        """
        SELECT u.*, t.* FROM teams t
        JOIN users u ON t.team_id = u.team_id
        WHERE u.discord_id = $1;
        """,
        discord_id,
    )

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
    # Determine the active week to attribute this result to.
    active_week = await get_active_week()
    if active_week is None:
        raise RuntimeError("No active week found. Cannot save result.")

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
    await _execute(
        query,
        active_week,
        result["discord_id"],
        result["opponent_id"],
        result["user_score"],
        result["opponent_score"],
        result["user_win"],
    )

async def get_active_week_row():
    """Return the full active week row as a dict, or None if not found."""
    return await _fetchrow_dict(
        "SELECT week_num, year, active, created_at FROM weeks WHERE active = TRUE LIMIT 1;"
    )
    
async def get_games_from_week(week_num: int):
    """
    Fetch all games from a specific week.
    """
    return await _fetch_dict("SELECT * FROM games WHERE week_num = $1;", week_num)
    
async def get_games_from_user(discord_id: int):
    """
    Fetch all games reported by a specific user.
    """
    return await _fetch_dict("SELECT * FROM games WHERE discord_id = $1;", discord_id)
    
async def get_game(week_num: int, discord_id: int):
    """
    Fetch a specific game reported by a user in a specific week.
    """
    return await _fetchrow_dict(
        "SELECT * FROM games WHERE week_num = $1 AND discord_id = $2;",
        week_num,
        discord_id,
    )
    

async def get_standings():
    """
    Calculate and return the current standings of all users.
    Returns a list of dicts with keys: discord_id, wins, losses, ties, total_games
    """
    return await _fetch_dict(
        """
        SELECT 
            discord_id,
            SUM(CASE WHEN user_win = TRUE THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN user_win = FALSE THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN user_win IS NULL THEN 1 ELSE 0 END) AS ties,
            COUNT(*) AS total_games
        FROM games
        GROUP BY discord_id
        ORDER BY wins DESC, losses ASC, ties DESC;
        """
    )

async def all_users_reported_for_week(week_num: int) -> bool:
    """Return True if every user has a game record for the given week."""
    total_users_row = await _fetchrow_dict("SELECT COUNT(*) AS c FROM users;")
    total_users = total_users_row["c"] if total_users_row else 0

    if total_users == 0:
        return False

    reported_row = await _fetchrow_dict(
        "SELECT COUNT(DISTINCT discord_id) AS c FROM games WHERE week_num = $1;",
        week_num,
    )
    reported = reported_row["c"] if reported_row else 0
    return reported >= total_users

# -------- Week advancement internals (connection-scoped) --------
async def _get_active_week_row_for_update(conn) -> dict | None:
    row = await conn.fetchrow(
        "SELECT week_num, year FROM weeks WHERE active = TRUE LIMIT 1 FOR UPDATE;"
    )
    return dict(row) if row else None

async def _advance_to_next_week(conn, week_num: int, year: int) -> dict | None:
    await conn.execute("UPDATE weeks SET active = FALSE WHERE active = TRUE;")
    new_row = await conn.fetchrow(
        """
        INSERT INTO weeks (week_num, year, active, created_at)
        VALUES ($1, $2, TRUE, now())
        RETURNING week_num, year, active, created_at;
        """,
        week_num + 1,
        year,
    )
    return dict(new_row) if new_row else None

async def _users_report_counts(conn, week_num: int) -> tuple[int, int]:
    total_users_row = await conn.fetchrow("SELECT COUNT(*) AS c FROM users;")
    total_users = total_users_row["c"] if total_users_row else 0
    reported_row = await conn.fetchrow(
        "SELECT COUNT(DISTINCT discord_id) AS c FROM games WHERE week_num = $1;",
        week_num,
    )
    reported = reported_row["c"] if reported_row else 0
    return total_users, reported

async def advance_week() -> dict | None:
    """
    Advance to the next week by deactivating the current active week and
    inserting a new active week with week_num + 1 (same year).
    Returns the new week row as a dict, or None if no change.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await _get_active_week_row_for_update(conn)
            if not current:
                return None
            return await _advance_to_next_week(conn, current["week_num"], current["year"])

async def maybe_auto_advance_week() -> dict | None:
    """If all users have reported for the active week, advance and return new week row."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await _get_active_week_row_for_update(conn)
            if not current:
                return None

            week_num = current["week_num"]

            total_users, reported = await _users_report_counts(conn, week_num)
            if total_users == 0:
                return None

            if reported < total_users:
                return None

            return await _advance_to_next_week(conn, week_num, current["year"])
