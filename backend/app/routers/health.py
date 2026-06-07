# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine

router = APIRouter(tags=["health"])


def _db_connected() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": "1.0.0",
        "db_connected": _db_connected(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/db")
def health_db() -> dict:
    connected = _db_connected()
    return {
        "status": "ok" if connected else "error",
        "db_connected": connected,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
