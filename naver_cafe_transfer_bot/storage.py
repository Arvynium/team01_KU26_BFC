"""이미 확인한 글을 기억해 중복 알림을 막는 SQLite 저장소."""

from __future__ import annotations

import sqlite3
from datetime import datetime


class SeenStore:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS seen (
                   key TEXT PRIMARY KEY,
                   title TEXT,
                   link TEXT,
                   matched INTEGER,
                   sent INTEGER,
                   seen_at TEXT
               )"""
        )
        self.conn.commit()

    def has(self, key: str) -> bool:
        return self.conn.execute("SELECT 1 FROM seen WHERE key = ?", (key,)).fetchone() is not None

    def add(self, key: str, title: str, link: str, matched: bool, sent: bool) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO seen VALUES (?, ?, ?, ?, ?, ?)",
            (key, title, link, int(matched), int(sent), datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
