"""Versioned SQLite storage; equal content is not a new regulatory update."""
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from .models import PolicyEvent, RunReport, SourceDocument


def text_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(":memory:", check_same_thread=False) if self.path == ":memory:" else None
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, url TEXT NOT NULL, content_hash TEXT NOT NULL,
                    observed_at TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(url, content_hash)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, started_at TEXT NOT NULL, payload TEXT NOT NULL
                );
            """)

    def connect(self):
        con = self._memory or sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        return con

    def save_event(self, event: PolicyEvent) -> bool:
        event.source.content_hash = text_hash(event.source.text)
        with self.connect() as con:
            row = con.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?)", (event.id, event.source.url, event.source.content_hash, event.observed_at.isoformat(), event.model_dump_json()))
            return row.rowcount == 1

    def latest_source(self, url: str) -> SourceDocument | None:
        with self.connect() as con:
            row = con.execute("SELECT payload FROM events WHERE url=? ORDER BY observed_at DESC, rowid DESC LIMIT 1", (url,)).fetchone()
        return PolicyEvent.model_validate_json(row["payload"]).source if row else None

    def events(self, limit: int = 100, offset: int = 0) -> list[PolicyEvent]:
        with self.connect() as con:
            rows = con.execute("SELECT payload FROM events ORDER BY observed_at DESC, rowid DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [PolicyEvent.model_validate_json(row["payload"]) for row in rows]

    def count_events(self) -> int:
        with self.connect() as con:
            return con.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def get_event(self, event_id: str) -> PolicyEvent | None:
        with self.connect() as con:
            row = con.execute("SELECT payload FROM events WHERE id=?", (event_id,)).fetchone()
        return PolicyEvent.model_validate_json(row["payload"]) if row else None

    def save_run(self, report: RunReport):
        with self.connect() as con:
            con.execute("INSERT INTO runs VALUES (?, ?, ?)", (report.run_id, report.started_at.isoformat(), report.model_dump_json()))

    def runs(self, limit: int = 100) -> list[RunReport]:
        with self.connect() as con:
            rows = con.execute("SELECT payload FROM runs ORDER BY started_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
        return [RunReport.model_validate_json(row["payload"]) for row in rows]
