from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://novarisk:novarisk@localhost:5432/novarisk",
    )
    return create_engine(database_url, pool_pre_ping=True, future=True)


def check_db_status() -> dict[str, Any]:
    """
    Returns database connectivity and PostGIS status information.
    This function is health-check safe: it never raises to the caller.
    """
    try:
        engine = get_engine()
        with engine.connect() as connection:
            db_now = connection.execute(text("SELECT NOW() AS now_utc")).scalar_one()
            postgis_version = connection.execute(text("SELECT PostGIS_Version() AS version")).scalar_one()

        return {
            "connected": True,
            "postgis": True,
            "postgis_version": str(postgis_version),
            "db_time": str(db_now),
        }
    except Exception as exc:
        return {
            "connected": False,
            "postgis": False,
            "error": str(exc),
        }
