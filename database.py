import asyncpg
import json
import logging
from typing import Optional
import config

log = logging.getLogger(__name__)
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(config.DATABASE_URL, statement_cache_size=0)
            log.info("Successfully connected to PostgreSQL (Supabase).")
        except Exception as e:
            log.error(f"Failed to connect to database: {e}")
            raise
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        log.info("Database connection closed.")

async def create_tables() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seasons (
                id               SERIAL PRIMARY KEY,
                month            VARCHAR NOT NULL,
                districts        TEXT[]  NOT NULL,
                is_active        BOOLEAN NOT NULL DEFAULT TRUE,
                leaderboard_message_id  BIGINT,
                leaderboard_channel_id  BIGINT,
                created_at       TIMESTAMP NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS bases (
                id              SERIAL PRIMARY KEY,
                season_id       INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
                district_name   VARCHAR NOT NULL,
                link            TEXT    NOT NULL,
                screenshot_url  TEXT    NOT NULL,
                builder         VARCHAR
            );

            ALTER TABLE bases ADD COLUMN IF NOT EXISTS builder VARCHAR;

            CREATE TABLE IF NOT EXISTS scores (
                id                  SERIAL PRIMARY KEY,
                season_id           INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
                player_id           BIGINT  NOT NULL,
                district_scores     JSONB   NOT NULL,
                total_stars         INT     NOT NULL,
                total_percent       INT     NOT NULL,
                three_star_count    INT     NOT NULL,
                grade               VARCHAR NOT NULL,
                result_message_id   BIGINT,
                submitted_at        TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """
        )
        log.info("Database tables initialized.")

# Season

async def get_active_season() -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM seasons WHERE is_active = TRUE LIMIT 1"
    )

async def create_season(month: str, districts: list[str]) -> asyncpg.Record:
    pool = await get_pool()
    return await pool.fetchrow(
        """
        INSERT INTO seasons (month, districts, is_active)
        VALUES ($1, $2, TRUE)
        RETURNING *
        """,
        month,
        districts,
    )

async def save_leaderboard_message(
    season_id: int, message_id: int, channel_id: int
) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE seasons
        SET leaderboard_message_id = $1, leaderboard_channel_id = $2
        WHERE id = $3
        """,
        message_id,
        channel_id,
        season_id,
    )

async def end_season(season_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE seasons SET is_active = FALSE WHERE id = $1", season_id
    )

async def get_season_by_name(month: str) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM seasons WHERE LOWER(month) = LOWER($1)", month
    )

async def delete_season(season_id: int) -> None:
    pool = await get_pool()
    await pool.execute("DELETE FROM seasons WHERE id = $1", season_id)

async def get_all_seasons() -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT month FROM seasons ORDER BY created_at DESC"
    )

# Scores
async def get_score(season_id: int, player_id: int) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM scores WHERE season_id = $1 AND player_id = $2",
        season_id,
        player_id,
    )

async def submit_score(
    season_id: int,
    player_id: int,
    district_scores: dict,
    total_stars: int,
    total_percent: int,
    three_star_count: int,
    grade: str,
) -> asyncpg.Record:
    pool = await get_pool()
    return await pool.fetchrow(
        """
        INSERT INTO scores
            (season_id, player_id, district_scores, total_stars,
             total_percent, three_star_count, grade)
        VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7)
        RETURNING *
        """,
        season_id,
        player_id,
        json.dumps(district_scores),
        total_stars,
        total_percent,
        three_star_count,
        grade,
    )

async def save_result_message_id(score_id: int, message_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE scores SET result_message_id = $1 WHERE id = $2", message_id, score_id
    )

async def update_score(
    score_id: int,
    district_scores: dict,
    total_stars: int,
    total_percent: int,
    three_star_count: int,
    grade: str,
) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE scores
        SET district_scores  = $1::jsonb,
            total_stars      = $2,
            total_percent    = $3,
            three_star_count = $4,
            grade            = $5
        WHERE id = $6
        """,
        json.dumps(district_scores),
        total_stars,
        total_percent,
        three_star_count,
        grade,
        score_id,
    )

async def delete_score(season_id: int, player_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM scores WHERE season_id = $1 AND player_id = $2",
        season_id,
        player_id,
    )

async def get_all_scores(season_id: int) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        """
        SELECT * FROM scores
        WHERE season_id = $1
        ORDER BY
            three_star_count DESC,
            total_stars      DESC,
            total_percent    DESC,
            submitted_at     ASC
        """,
        season_id,
    )

async def get_player_all_scores(player_id: int) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        """
        SELECT s.*, se.month, se.districts
        FROM scores s
        JOIN seasons se ON se.id = s.season_id
        WHERE s.player_id = $1
        ORDER BY se.created_at DESC
        """,
        player_id,
    )
async def get_district_leaderboard(season_id: int, district_name: str) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        """
        SELECT
            player_id,
            (district_scores -> $1 ->> 'stars') AS stars,
            (district_scores -> $1 ->> 'percent') AS percent
        FROM scores
        WHERE season_id = $2
          AND (district_scores -> $1 ->> 'stars') IS NOT NULL
        ORDER BY
            (district_scores -> $1 ->> 'stars')::INT DESC,
            (district_scores -> $1 ->> 'percent')::INT DESC,
            submitted_at ASC
        """,
        district_name,
        season_id,
    )
# Bases

async def add_base(
    season_id: int, district_name: str, link: str, screenshot_url: str, builder: Optional[str] = None
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM bases WHERE season_id = $1 AND district_name = $2",
                season_id,
                district_name,
            )
            await conn.execute(
                """
                INSERT INTO bases (season_id, district_name, link, screenshot_url, builder)
                VALUES ($1, $2, $3, $4, $5)
                """,
                season_id,
                district_name,
                link,
                screenshot_url,
                builder,
            )

async def get_bases(season_id: int) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT * FROM bases WHERE season_id = $1", season_id
    )
