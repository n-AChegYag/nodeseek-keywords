"""
RSS fetching and keyword-matching logic.
No Telegram-specific code lives here — only data retrieval and pure matching.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import aiohttp
import feedparser

from config import RSS_BASE_URL

logger = logging.getLogger(__name__)

# Cloudflare requires a browser-like UA; confirmed by community tools (ljnchn/seeknode)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.nodeseek.com/",
    "Cache-Control": "no-cache",
}

# All forum categories available via the RSS feed
CATEGORIES: dict[str, str] = {
    "daily":       "日常",
    "tech":        "技术",
    "info":        "情报",
    "review":      "测评",
    "trade":       "交易",
    "carpool":     "拼车",
    "dev":         "Dev",
    "photo-share": "贴图",
    "expose":      "曝光",
    "sandbox":     "沙盒",
}


async def fetch_entries(category: Optional[str] = None) -> list[dict]:
    """
    Fetch and parse the NodeSeek RSS feed.

    Args:
        category: If provided, filter to a specific board (e.g. "trade").
                  If None, fetch the global feed (all boards, ~20 latest posts).

    Returns:
        List of dicts with keys: post_id, title, link, category, author.

    Raises:
        aiohttp.ClientError: On network or HTTP errors (caller handles alerting).
    """
    url = RSS_BASE_URL if category is None else f"{RSS_BASE_URL}?category={category}"
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(headers=_HEADERS, timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise aiohttp.ClientError(
                    f"HTTP {resp.status} from {url}"
                )
            raw = await resp.text()

    feed = feedparser.parse(raw)
    entries: list[dict] = []
    for entry in feed.entries:
        try:
            post_id = int(entry.get("id", 0))
        except (ValueError, TypeError):
            continue
        if not post_id:
            continue

        tags = entry.get("tags") or []
        cat = tags[0].get("term", "") if tags else ""

        entries.append(
            {
                "post_id":  post_id,
                "title":    entry.get("title", "").strip(),
                "link":     entry.get("link", ""),
                "category": cat,
                "author":   entry.get("author", "").strip(),
            }
        )

    return entries


def matches(title: str, keyword: str, match_mode: str = "substring") -> bool:
    """
    Match a post title against a keyword.

    Modes:
        substring — case-insensitive substring search (default).
        regex     — case-insensitive regular expression search.
                    Invalid patterns are silently treated as non-matching.
    """
    if match_mode == "regex":
        try:
            return bool(re.search(keyword, title, re.IGNORECASE))
        except re.error:
            logger.warning("Invalid regex pattern %r — treating as non-matching", keyword)
            return False
    return keyword.lower() in title.lower()
