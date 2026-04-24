from __future__ import annotations

import email.utils
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import feedparser
import httpx


@dataclass
class FeedEntry:
    title: str
    link: str
    summary: str | None
    published: datetime | None
    raw: dict[str, Any]


def _parse_http_date(s: str | None) -> datetime | None:
    if not s:
        return None
    t = email.utils.parsedate_to_datetime(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t


def _entry_datetime(e: Any) -> datetime | None:
    if getattr(e, "published_parsed", None) and e.published_parsed:
        t = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
        return t
    if getattr(e, "updated_parsed", None) and e.updated_parsed:
        return datetime(*e.updated_parsed[:6], tzinfo=timezone.utc)
    return _parse_http_date(getattr(e, "published", None))


def _strip_html(s: str) -> str:
    t = re.sub(r"<[^>]+>", " ", s)
    t = unescape(t)
    return " ".join(t.split())


def _entry_summary(e: Any) -> str | None:
    raw = getattr(e, "summary", None) or getattr(e, "description", None)
    if not raw:
        return None
    text = _strip_html(raw) if "<" in raw else raw.strip()
    return text or None


def parse_feed_document(text: str, base_url: str = "") -> list[FeedEntry]:
    parsed = feedparser.parse(text)
    out: list[FeedEntry] = []
    base = base_url
    for e in parsed.entries:
        title = (getattr(e, "title", None) or "").strip()
        link = (getattr(e, "link", None) or "").strip()
        if not title or not link:
            continue
        if not link.startswith(("http://", "https://")):
            link = urljoin(base, link)
        summary = _entry_summary(e)
        published = _entry_datetime(e)
        out.append(
            FeedEntry(
                title=title,
                link=link,
                summary=summary,
                published=published,
                raw=dict(e),
            )
        )
    return out


def fetch_feed(feed_url: str, timeout: float = 30.0) -> list[FeedEntry]:
    headers = {
        "User-Agent": "ianews/0.1 (+https://github.com/) feed aggregator",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        r = client.get(feed_url)
        r.raise_for_status()
        return parse_feed_document(r.text, str(r.url))


def load_entries_from_path(path: Path) -> list[FeedEntry]:
    text = path.read_text(encoding="utf-8", errors="replace")
    base = path.resolve().as_uri()
    return parse_feed_document(text, base)


def take_latest_entries(entries: list[FeedEntry], limit: int) -> list[FeedEntry]:
    min_dt = datetime.min.replace(tzinfo=timezone.utc)
    entries = sorted(entries, key=lambda e: e.published or min_dt, reverse=True)
    return entries[:limit]


def fetch_feed_latest(
    feed_url: str,
    limit: int = 80,
    timeout: float = 30.0,
) -> list[FeedEntry]:
    entries = fetch_feed(feed_url, timeout=timeout)
    return take_latest_entries(entries, limit)


def discover_feed_url(site_url: str, timeout: float = 20.0) -> str | None:
    headers = {"User-Agent": "ianews/0.1 feed discovery"}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        r = client.get(site_url)
        r.raise_for_status()
        text = r.text
    for m in re.finditer(
        r'<link[^>]+rel=["\']alternate["\'][^>]*>',
        text,
        re.I,
    ):
        tag = m.group(0)
        if re.search(r'type=["\']application/(rss|atom)\+xml["\']', tag, re.I):
            hm = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
            if hm:
                return urljoin(str(r.url), hm.group(1))
    for m in re.finditer(r'href=["\']([^"\']+\.(?:rss|xml))["\']', text, re.I):
        return urljoin(str(r.url), m.group(1))
    return None
