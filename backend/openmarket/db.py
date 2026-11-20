"""Persistencia local en SQLite (caché de precios, carteras, transacciones, listas de seguimiento)."""
from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from .config import Settings

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_cache (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    provider TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (symbol, interval)
);
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    base_currency TEXT NOT NULL DEFAULT 'USD',
    paper INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ts TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('buy','sell','deposit','withdraw')),
    symbol TEXT,
    quantity REAL,
    price REAL,
    fee REAL NOT NULL DEFAULT 0,
    amount REAL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tx_portfolio ON transactions(portfolio_id, ts);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    kind TEXT NOT NULL,
    threshold REAL NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    triggered_at TEXT,
    last_value REAL,
    last_source TEXT
);
CREATE TABLE IF NOT EXISTS watchlist (
    symbol TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, settings: Settings):
        self.path = settings.db_path

    @contextmanager
    def connect(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            if write:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        if self.path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with self.connect() as c:
            if self.path != ":memory:":
                c.execute("PRAGMA journal_mode = WAL")
            c.execute("BEGIN IMMEDIATE")
            c.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            row = c.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            version = int(row["value"]) if row else 0
            if not 0 <= version <= SCHEMA_VERSION:
                raise RuntimeError("Versión de SQLite incompatible con OpenMarket")
            if version == 0:
                for statement in _SCHEMA.split(";"):
                    if statement.strip():
                        c.execute(statement)
                c.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )

    def ready(self) -> bool:
        with self.connect() as c:
            row = c.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            return row is not None and row["value"] == str(SCHEMA_VERSION)
