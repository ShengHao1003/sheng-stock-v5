from __future__ import annotations
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", "user_settings.db"))


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            price_min REAL NOT NULL,
            price_max REAL NOT NULL,
            mode INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def get_user_setting(user_id: str) -> dict:
    default_min = float(os.getenv("DEFAULT_PRICE_MIN", "10"))
    default_max = float(os.getenv("DEFAULT_PRICE_MAX", "300"))
    default_mode = int(os.getenv("DEFAULT_ANALYSIS_MODE", "1"))
    with _connect() as conn:
        row = conn.execute(
            "SELECT price_min, price_max, mode FROM user_settings WHERE user_id=?",
            (user_id,),
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT OR REPLACE INTO user_settings(user_id, price_min, price_max, mode) VALUES(?,?,?,?)",
                (user_id, default_min, default_max, default_mode),
            )
            return {"price_min": default_min, "price_max": default_max, "mode": default_mode}
        return {"price_min": float(row[0]), "price_max": float(row[1]), "mode": int(row[2])}


def save_user_setting(user_id: str, *, price_min: float | None = None, price_max: float | None = None, mode: int | None = None) -> dict:
    st = get_user_setting(user_id)
    if price_min is not None:
        st["price_min"] = float(price_min)
    if price_max is not None:
        st["price_max"] = float(price_max)
    if mode is not None:
        st["mode"] = int(mode)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_settings(user_id, price_min, price_max, mode, updated_at)
            VALUES(?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                price_min=excluded.price_min,
                price_max=excluded.price_max,
                mode=excluded.mode,
                updated_at=CURRENT_TIMESTAMP
            """,
            (user_id, st["price_min"], st["price_max"], st["mode"]),
        )
    return st
