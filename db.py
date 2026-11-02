"""Thin database layer supporting MySQL (PyMySQL) and SQLite.

* All queries are parameterised (``%s`` placeholders; translated to ``?`` for SQLite).
* Credentials come from configuration, never from code.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

SQL_DIR = Path(__file__).resolve().parent / "sql"


class Database:
    def __init__(self, engine: str, **opts):
        if engine not in {"sqlite", "mysql"}:
            raise ValueError(f"Unsupported DB_ENGINE '{engine}'. Use 'sqlite' or 'mysql'.")
        self.engine = engine
        self.opts = opts

    @classmethod
    def from_config(cls, cfg) -> "Database":
        engine = cfg["DB_ENGINE"]
        if engine == "sqlite":
            return cls("sqlite", path=cfg["SQLITE_PATH"])
        return cls(
            "mysql",
            host=cfg["MYSQL_HOST"],
            port=int(cfg["MYSQL_PORT"]),
            user=cfg["MYSQL_USER"],
            password=cfg["MYSQL_PASSWORD"],
            database=cfg["MYSQL_DATABASE"],
        )

    # ------------------------------------------------------------------ connections
    def _connect(self, with_database: bool = True):
        if self.engine == "sqlite":
            conn = sqlite3.connect(self.opts["path"])
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        import pymysql  # imported lazily so SQLite mode needs no MySQL driver

        kwargs = dict(
            host=self.opts["host"],
            port=self.opts["port"],
            user=self.opts["user"],
            password=self.opts["password"],
            charset="utf8mb4",
        )
        if with_database:
            kwargs["database"] = self.opts["database"]
        return pymysql.connect(**kwargs)

    @contextmanager
    def connection(self, with_database: bool = True):
        conn = self._connect(with_database)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _sql(self, sql: str) -> str:
        return sql.replace("%s", "?") if self.engine == "sqlite" else sql

    # ------------------------------------------------------------------ helpers
    def query_df(self, sql: str, params=()) -> pd.DataFrame:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(self._sql(sql), tuple(params))
            columns = [c[0] for c in cur.description]
            rows = cur.fetchall()
        return pd.DataFrame.from_records(list(rows), columns=columns)

    def scalar(self, sql: str, params=()):
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(self._sql(sql), tuple(params))
            row = cur.fetchone()
        return row[0] if row else None

    def execute_many(self, sql: str, rows) -> None:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.executemany(self._sql(sql), rows)

    # ------------------------------------------------------------------ schema
    def init_schema(self) -> None:
        """Create the database (MySQL only) and all tables if they do not exist."""
        if self.engine == "mysql":
            name = self.opts["database"]
            if not re.fullmatch(r"[A-Za-z0-9_]+", name):
                raise ValueError("MYSQL_DATABASE may only contain letters, digits and underscores.")
            with self.connection(with_database=False) as conn:
                conn.cursor().execute(
                    f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4"
                )

        script = (SQL_DIR / f"schema_{self.engine}.sql").read_text(encoding="utf-8")
        script = "\n".join(l for l in script.splitlines() if not l.strip().startswith("--"))
        statements = [s.strip() for s in script.split(";") if s.strip()]
        with self.connection() as conn:
            cur = conn.cursor()
            for statement in statements:
                cur.execute(statement)

    def reset_data(self) -> None:
        """Delete all rows (children first so foreign keys stay valid)."""
        with self.connection() as conn:
            cur = conn.cursor()
            for table in ("order_items", "orders", "products"):
                cur.execute(f"DELETE FROM {table}")
