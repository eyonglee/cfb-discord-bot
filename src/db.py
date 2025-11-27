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

async def get_user_by_team(team_id: int):
    """Fetch a single user by their team_id. Returns dict or None."""
    return await _fetchrow_dict("SELECT * FROM users WHERE team_id = $1;", team_id)
    
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
        opponent_id: int | None,
        user_score: int | None,
        opponent_score: int | None,
        user_win: bool | None,
        bye: bool (optional, defaults to False)
    }
    """
    # Determine the active week and season to attribute this result to.
    active_week_row = await get_active_week_row()
    if active_week_row is None:
        raise RuntimeError("No active week found. Cannot save result.")

    active_week = active_week_row["week_num"]
    active_year = active_week_row["year"]

    bye = result.get("bye", False)

    query = """
    INSERT INTO games (week_num, year, discord_id, opponent_id, user_score, opp_score, user_win, bye, created_at, updated_at)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now(), now())
    ON CONFLICT (week_num, discord_id)
    DO UPDATE SET opponent_id = EXCLUDED.opponent_id,
                  user_score = EXCLUDED.user_score,
                  opp_score = EXCLUDED.opp_score,
                  user_win = EXCLUDED.user_win,
                  bye = EXCLUDED.bye,
                  updated_at = now();
    """
    await _execute(
        query,
        active_week,
        active_year,
        result["discord_id"],
        result["opponent_id"],
        result["user_score"],
        result["opponent_score"],
        result["user_win"],
        bye,
    )

    # If this was a user-vs-user game, also mirror the result for the opponent.
    # We detect this when the opponent's team belongs to a user.
    opponent_team_id = result.get("opponent_id")
    if opponent_team_id is None or bye:
        return

    opponent_user = await get_user_by_team(opponent_team_id)
    if not opponent_user:
        return

    opponent_discord_id = opponent_user["discord_id"]

    # Find the reporting user's team (may be None if they are not assigned).
    reporter_user = await get_user(result["discord_id"])
    reporter_team_id = reporter_user["team_id"] if reporter_user and "team_id" in reporter_user else None

    # Mirror scores and win/loss for the opponent's perspective.
    us = result.get("user_score")
    os = result.get("opponent_score")
    win = result.get("user_win")

    mirror_user_score = os
    mirror_opp_score = us
    if win is None:
        mirror_user_win = None
    else:
        mirror_user_win = not win

    # Upsert the mirrored row for the opponent user.
    await _execute(
        query,
        active_week,
        active_year,
        opponent_discord_id,
        reporter_team_id,
        mirror_user_score,
        mirror_opp_score,
        mirror_user_win,
        False,  # bye is always False for mirrored user-vs-user games
    )

    # Mark both sides as user games.
    await _execute(
        """
        UPDATE games
        SET user_game = TRUE, updated_at = now()
        WHERE week_num = $1 AND discord_id = ANY($2::bigint[]);
        """,
        active_week,
        [result["discord_id"], opponent_discord_id],
    )

async def get_active_week_row():
    """Return the full active week row as a dict, or None if not found."""
    return await _fetchrow_dict(
        "SELECT week_num, year, active, created_at FROM weeks WHERE active = TRUE LIMIT 1;"
    )

async def has_played_team_this_year(discord_id: int, opponent_id: int) -> bool:
    """
    Return True if the user has already played the given opponent team
    in the current season (year of the active week).
    """
    active = await get_active_week_row()
    if not active:
        return False

    year = active["year"]
    row = await _fetchrow_dict(
        """
        SELECT 1
        FROM games
        WHERE discord_id = $1
          AND opponent_id = $2
          AND year = $3;
        """,
        discord_id,
        opponent_id,
        year,
    )
    return row is not None
    
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
    Calculate and return the current standings of all users
    for the active season (current year).
    Returns a list of dicts with keys: discord_id, wins, losses, ties, total_games
    """
    active = await get_active_week_row()
    if not active:
        return []

    year = active["year"]

    return await _fetch_dict(
        """
        SELECT 
            discord_id,
            SUM(CASE WHEN user_win = TRUE THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN user_win = FALSE THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN user_win IS NULL THEN 1 ELSE 0 END) AS ties,
            COUNT(*) AS total_games
        FROM games
        WHERE year = $1
        GROUP BY discord_id
        ORDER BY wins DESC, losses ASC, ties DESC;
        """,
        year,
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

    # weeks 0 - 15 regular season
    # weeks 16-20 post season
    # week 21 is offseason

    if week_num == 21:
        print("New Season!!!")
        new_year = year + 1
        new_week = 0

    else:
        new_year = year
        new_week = week_num + 1

    new_row = await conn.fetchrow(
        """
        INSERT INTO weeks (week_num, year, active, created_at)
        VALUES ($1, $2, TRUE, now())
        RETURNING week_num, year, active, created_at;
        """,
        new_week,
        new_year,
    )

    try:
        new_row = dict(new_row)

        if week_num == 21:
            print("offseason!!")
            new_row[week_num] = 'Offseason'
        elif week_num == 16:
            print("Conference championship week!!")
            new_row[week_num] = 'Conference Championships'
        elif week_num > 16:
            print("Bowl weeks!!!")
            post_week = week_num % 16
            new_row['week_num'] = f'Bowl Week {post_week}'

    except:
        new_row = None

    return new_row

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
