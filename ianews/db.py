from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator, Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    feed_url TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    title TEXT NOT NULL,
    link TEXT NOT NULL UNIQUE,
    summary TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    matched_keywords TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id);
"""


@dataclass(frozen=True)
class ArticleRow:
    id: int
    source_name: str
    title: str
    link: str
    summary: str | None
    published_at: str | None
    fetched_at: str
    matched_keywords: str | None


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def session(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_source(conn: sqlite3.Connection, name: str, feed_url: str) -> int:
    conn.execute(
        "INSERT INTO sources (name, feed_url) VALUES (?, ?) "
        "ON CONFLICT(feed_url) DO UPDATE SET name = excluded.name",
        (name, feed_url),
    )
    cur = conn.execute("SELECT id FROM sources WHERE feed_url = ?", (feed_url,))
    row = cur.fetchone()
    assert row is not None
    return int(row[0])


def insert_article(
    conn: sqlite3.Connection,
    source_id: int,
    title: str,
    link: str,
    summary: str | None,
    published_at: datetime | None,
    matched_keywords: list[str] | None,
) -> bool:
    kw = ",".join(matched_keywords) if matched_keywords else None
    pub = published_at.isoformat() if published_at else None
    try:
        conn.execute(
            """
            INSERT INTO articles (source_id, title, link, summary, published_at, matched_keywords)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_id, title, link, summary, pub, kw),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def list_articles(
    conn: sqlite3.Connection,
    limit: int = 50,
    source: str | None = None,
) -> list[ArticleRow]:
    q = """
    SELECT a.id, s.name AS source_name, a.title, a.link, a.summary,
           a.published_at, a.fetched_at, a.matched_keywords
    FROM articles a
    JOIN sources s ON s.id = a.source_id
    """
    args: list[object] = []
    if source:
        q += " WHERE s.name = ? OR s.feed_url = ?"
        args.extend([source, source])
    q += " ORDER BY COALESCE(a.published_at, a.fetched_at) DESC LIMIT ?"
    args.append(limit)
    cur = conn.execute(q, args)
    return [
        ArticleRow(
            id=int(r["id"]),
            source_name=str(r["source_name"]),
            title=str(r["title"]),
            link=str(r["link"]),
            summary=r["summary"],
            published_at=r["published_at"],
            fetched_at=str(r["fetched_at"]),
            matched_keywords=r["matched_keywords"],
        )
        for r in cur.fetchall()
    ]


def list_sources(conn: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    return conn.execute("SELECT id, name, feed_url FROM sources ORDER BY name").fetchall()
