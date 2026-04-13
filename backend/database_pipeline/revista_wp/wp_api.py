"""WordPress REST client for revistacastells.cat."""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

import requests

from .models import Article, CATEGORY_MAP, clean_text, slug_from_url

log = logging.getLogger("revista_wp")

BASE_URL = "https://revistacastells.cat"
API_BASE = f"{BASE_URL}/wp-json/wp/v2"
USER_AGENT = (
    "Mozilla/5.0 (compatible; RevistacastellsScraper/2.0; +https://github.com/castellers)"
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_TAG_RE = re.compile(
    r"<(script|style|nav|footer)[^>]*>.*?</\1>", re.S | re.I
)
_ENTITY_MAP = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#8217;": "'",
    "&#8216;": "'",
    "&#8220;": '"',
    "&#8221;": '"',
    "&#8230;": "…",
    "&hellip;": "…",
    "&mdash;": "—",
    "&ndash;": "–",
    "&laquo;": "«",
    "&raquo;": "»",
}


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "ca,es;q=0.9,en;q=0.8",
        }
    )
    return s


def api_get(
    session: requests.Session,
    endpoint: str,
    params: dict,
    delay: float,
) -> Optional[requests.Response]:
    time.sleep(delay)
    url = f"{API_BASE}/{endpoint}"
    try:
        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        log.warning("API error %s — %s", url, exc)
        return None


def fetch_taxonomy(
    session: requests.Session, endpoint: str, delay: float
) -> dict[int, str]:
    terms: dict[int, str] = {}
    page = 1
    while True:
        resp = api_get(session, endpoint, {"per_page": 100, "page": page}, delay)
        if resp is None:
            break
        data = resp.json()
        if not data:
            break
        for item in data:
            terms[item["id"]] = item["name"]
        if len(data) < 100:
            break
        page += 1
    log.info("Fetched %d %s terms.", len(terms), endpoint)
    return terms


def strip_html(html: str) -> str:
    html = _BLOCK_TAG_RE.sub(" ", html)
    html = _HTML_TAG_RE.sub(" ", html)
    for entity, char in _ENTITY_MAP.items():
        html = html.replace(entity, char)
    return clean_text(html)


def resolve_category(cat_names: list[str]) -> str:
    for name in cat_names:
        key = name.lower().strip()
        if key in CATEGORY_MAP:
            return CATEGORY_MAP[key]
        slug = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
        if slug in CATEGORY_MAP:
            return CATEGORY_MAP[slug]
    return cat_names[0].lower().strip() if cat_names else "general"


def post_to_article(
    post: dict[str, Any],
    cat_map: dict[int, str],
    tag_map: dict[int, str],
) -> Article:
    url = post.get("link", "")
    title = strip_html(post.get("title", {}).get("rendered", ""))

    raw_date = post.get("date_gmt") or post.get("date") or ""
    date_str = raw_date[:10]

    cat_ids = post.get("categories", [])
    cat_names = [cat_map[cid] for cid in cat_ids if cid in cat_map]
    category = resolve_category(cat_names)

    tag_ids = post.get("tags", [])
    tags = [tag_map[tid] for tid in tag_ids if tid in tag_map]

    author: Optional[str] = None
    embedded = post.get("_embedded", {})
    author_list = embedded.get("author", [])
    if author_list and isinstance(author_list[0], dict):
        author = author_list[0].get("name")

    image_url: Optional[str] = None
    media_list = embedded.get("wp:featuredmedia", [])
    if media_list and isinstance(media_list[0], dict):
        image_url = media_list[0].get("source_url")

    body = strip_html(post.get("content", {}).get("rendered", ""))

    excerpt_raw = strip_html(post.get("excerpt", {}).get("rendered", ""))
    excerpt = (
        (excerpt_raw[:220] + ("…" if len(excerpt_raw) > 220 else ""))
        if excerpt_raw
        else None
    )

    return Article(
        id=post.get("slug") or slug_from_url(url),
        url=url,
        title=title,
        date=date_str,
        category=category,
        tags=tags,
        author=author,
        excerpt=excerpt,
        body=body,
        image_url=image_url,
    ).enrich()


def fetch_all_posts(
    session: requests.Session,
    delay: float,
    per_page: int,
    max_pages: int,
    after: Optional[str],
    known_slugs: Optional[set[str]] = None,
) -> list[dict]:
    all_posts: list[dict] = []
    page = 1
    total_pages: Optional[int] = None

    while True:
        params: dict[str, Any] = {
            "per_page": per_page,
            "page": page,
            "status": "publish",
            "orderby": "date",
            "order": "desc",
            "_embed": "author,wp:featuredmedia",
        }
        if after:
            params["after"] = after

        resp = api_get(session, "posts", params, delay)
        if resp is None:
            log.error("API request failed on page %d. Stopping.", page)
            break

        if total_pages is None:
            try:
                total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
                total_posts = resp.headers.get("X-WP-Total", "?")
                log.info("API: %s total posts, %d pages.", total_posts, total_pages)
            except (ValueError, TypeError):
                total_pages = 1

        posts = resp.json()
        if not isinstance(posts, list) or not posts:
            break

        log.info("  Page %d/%s — %d posts.", page, total_pages, len(posts))
        all_posts.extend(posts)

        if known_slugs is not None and posts:
            page_slugs = [
                post.get("slug") or slug_from_url(post.get("link", ""))
                for post in posts
            ]
            if all(s in known_slugs for s in page_slugs):
                log.info(
                    "  Early stop: page %d is fully indexed (all slugs known).",
                    page,
                )
                break

        if page >= (total_pages or 1):
            break
        if max_pages and page >= max_pages:
            log.info("  Stopped at max-pages=%d.", max_pages)
            break
        page += 1

    return all_posts
