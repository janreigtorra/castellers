#!/usr/bin/env python3
"""
Fetch Revista dels Castells (WordPress) posts and append chunk-shaped records to
data_basic/data_to_embed/revista_castells_scraper.json.

Idempotent: re-runs skip articles whose article_slug is already present (stable
WP slug). Pagination stops early once a full API page contains only known slugs
(newest-first order).

Chunk shape matches castellers_info_chunks.json (id, title, category, years,
year_ranges, colles, places, keywords, optional castells, text). Extra fields
article_slug, source_url, published_date help merging and future loaders.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

# Local package (same folder as this script). Do not ``pip install models`` — that is unrelated PyPI junk.
_PIPELINE_DIR = Path(__file__).resolve().parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from revista_wp.models import Article  # noqa: E402
from revista_wp.wp_api import (  # noqa: E402
    fetch_all_posts,
    fetch_taxonomy,
    make_session,
    post_to_article,
    slug_from_url,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("revista_to_chunks")

DATA_EMBED_DIR = Path(__file__).resolve().parent.parent / "data_basic" / "data_to_embed"
OUTPUT_JSON = DATA_EMBED_DIR / "revista_castells_scraper.json"
COLLES_FUNDACIO_JSON = (
    Path(__file__).resolve().parent.parent / "joc_del_mocador" / "colles_fundacio.json"
)

MAX_PARAGRAPHS_PER_CHUNK = 3
MAX_CHARS_PER_PARAGRAPH = 1100

# Castell mentions like "3 de 8", "4 d'9", "10 de 8"
_CASTELL_RE = re.compile(
    r"\b([2-9]|10|11)\s+de\s+([4-9]|10|11)\b|"
    r"\b([2-9]|10|11)\s+d['\u2019]\s*([4-9]|10|11)\b",
    re.IGNORECASE,
)


def extract_castells(text: str) -> list[str]:
    found: set[str] = set()
    for m in _CASTELL_RE.finditer(text):
        a, b = (m.group(1) or m.group(3)), (m.group(2) or m.group(4))
        if a and b:
            found.add(f"{a} de {b}")
    return sorted(found)


def normalize_paragraphs(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    blocks = re.split(r"\n\s*\n+", text)
    out: list[str] = []
    for b in blocks:
        b = re.sub(r"\s+", " ", b).strip()
        if b:
            out.append(b)
    if not out:
        one = re.sub(r"\s+", " ", text).strip()
        if one:
            out.append(one)
    return out


def split_long_block(block: str) -> list[str]:
    """Split a single long paragraph into smaller pieces by sentence."""
    if len(block) <= MAX_CHARS_PER_PARAGRAPH:
        return [block]
    parts = re.split(r"(?<=[.!?…])\s+", block)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        return [block[:MAX_CHARS_PER_PARAGRAPH].rstrip() + "…"]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for s in parts:
        if current_len + len(s) + 1 <= MAX_CHARS_PER_PARAGRAPH:
            current.append(s)
            current_len += len(s) + 1
        else:
            if current:
                chunks.append(" ".join(current))
            current = [s]
            current_len = len(s)
    if current:
        chunks.append(" ".join(current))
    return chunks


def flatten_to_paragraphs(body: str) -> list[str]:
    paras = normalize_paragraphs(body)
    flat: list[str] = []
    for p in paras:
        flat.extend(split_long_block(p))
    return flat


def group_paragraphs_for_chunks(paragraphs: list[str]) -> list[str]:
    """Each chunk is at most MAX_PARAGRAPHS_PER_CHUNK paragraphs, joined for readability."""
    groups: list[str] = []
    i = 0
    while i < len(paragraphs):
        g = paragraphs[i : i + MAX_PARAGRAPHS_PER_CHUNK]
        groups.append("\n\n".join(g))
        i += MAX_PARAGRAPHS_PER_CHUNK
    return groups


def publication_year(date_str: str) -> Optional[int]:
    if not date_str or len(date_str) < 4:
        return None
    try:
        return int(date_str[:4])
    except ValueError:
        return None


def norm_colla_name(s: str) -> str:
    """Normalize for comparison with official colla names."""
    t = unicodedata.normalize("NFC", (s or "").strip())
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    t = re.sub(r"\s+", " ", t)
    return t.casefold()


@lru_cache(maxsize=1)
def fundacio_colla_lookup() -> dict[str, str]:
    """
    normalized_name -> canonical name as in colles_fundacio.json.
    If two entries normalize to the same key, keep the longer canonical string.
    """
    with open(COLLES_FUNDACIO_JSON, encoding="utf-8") as f:
        rows: list[dict[str, Any]] = json.load(f)
    out: dict[str, str] = {}
    for row in rows:
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        key = norm_colla_name(name)
        prev = out.get(key)
        if prev is None or len(name) > len(prev):
            out[key] = name.strip()
    return out


def filter_colles_to_fundacio(candidates: list[str]) -> list[str]:
    """Keep only strings that exactly match a colla name in colles_fundacio.json (after norm)."""
    lookup = fundacio_colla_lookup()
    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        key = norm_colla_name(c)
        canon = lookup.get(key)
        if canon and canon not in seen:
            seen.add(canon)
            ordered.append(canon)
    return ordered


def build_keywords(article: Article) -> list[str]:
    k: list[str] = []
    if article.category:
        k.append(article.category)
    k.extend(article.tags)
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for x in k:
        x = x.strip()
        if not x or x.lower() in seen:
            continue
        seen.add(x.lower())
        out.append(x)
    return out[:40]


def article_slug_from_chunk(chunk: dict[str, Any]) -> Optional[str]:
    s = chunk.get("article_slug")
    if isinstance(s, str) and s:
        return s
    cid = chunk.get("id", "")
    if isinstance(cid, str) and cid.startswith("revista_"):
        rest = cid[len("revista_") :]
        if "__p" in rest:
            rest = rest.split("__p", 1)[0]
        return rest or None
    return None


def existing_article_slugs(chunks: list[dict[str, Any]]) -> set[str]:
    slugs: set[str] = set()
    for c in chunks:
        s = article_slug_from_chunk(c)
        if s:
            slugs.add(s)
    return slugs


def article_to_chunks(article: Article) -> list[dict[str, Any]]:
    slug = article.id
    paras = flatten_to_paragraphs(article.body)
    if not paras and article.excerpt:
        paras = flatten_to_paragraphs(article.excerpt)
    if not paras:
        return []

    text_parts = group_paragraphs_for_chunks(paras)
    pub_year = publication_year(article.date)
    years = list(article.years)
    if pub_year is not None and pub_year not in years:
        years = sorted(years + [pub_year])

    year_ranges: list[str] = []
    if pub_year is not None:
        year_ranges.append(str(pub_year))

    combined = f"{article.title}\n{article.body}"
    castells = extract_castells(combined)
    keywords = build_keywords(article)

    out: list[dict[str, Any]] = []
    n = len(text_parts)
    for idx, text in enumerate(text_parts, start=1):
        chunk_id = f"revista_{slug}" if n == 1 else f"revista_{slug}__p{idx:02d}"
        title = article.title if n == 1 else f"{article.title} (part {idx}/{n})"
        chunk: dict[str, Any] = {
            "id": chunk_id,
            "title": title,
            "category": article.category,
            "years": years,
            "year_ranges": year_ranges,
            "colles": filter_colles_to_fundacio(list(article.colles)),
            "places": list(article.places),
            "keywords": keywords,
            "text": text,
            "article_slug": slug,
            "source_url": article.url,
            "published_date": article.date,
        }
        if castells:
            chunk["castells"] = castells
        out.append(chunk)
    return out


def load_output(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "metadata": {
                "source": "revistacastells.cat",
                "description": "Articles from Revista dels Castells (WordPress), chunked for RAG",
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "total_chunks": 0,
                "last_scrape_at": None,
            },
            "chunks": [],
        }
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_output(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["metadata"]["total_chunks"] = len(data.get("chunks", []))
    data["metadata"]["last_scrape_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("Wrote %d chunks → %s", len(data.get("chunks", [])), path)


def merge_chunk_lists(
    existing: list[dict[str, Any]], new_chunks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {c["id"]: c for c in existing if c.get("id")}
    for c in new_chunks:
        cid = c.get("id")
        if cid:
            by_id[cid] = c
    merged = list(by_id.values())

    def sort_key(ch: dict[str, Any]) -> tuple:
        d = ch.get("published_date") or ""
        return (d, ch.get("id", ""))

    merged.sort(key=sort_key, reverse=True)
    return merged


def run(
    delay: float,
    per_page: int,
    max_pages: int,
    after: Optional[str],
    dry_run: bool,
) -> None:
    data = load_output(OUTPUT_JSON)
    chunks: list[dict[str, Any]] = data.get("chunks", [])
    known_slugs = existing_article_slugs(chunks)
    log.info("Existing indexed slugs: %d", len(known_slugs))

    session = make_session()
    log.info("Fetching taxonomies…")
    cat_map = fetch_taxonomy(session, "categories", delay)
    tag_map = fetch_taxonomy(session, "tags", delay)

    log.info("Fetching posts (early stop when a full page is already indexed)…")
    raw_posts = fetch_all_posts(
        session,
        delay,
        min(per_page, 100),
        max_pages,
        after,
        known_slugs=known_slugs,
    )

    new_chunks: list[dict[str, Any]] = []
    for post in raw_posts:
        url = post.get("link", "")
        slug = post.get("slug") or slug_from_url(url)
        if slug in known_slugs:
            continue
        try:
            article = post_to_article(post, cat_map, tag_map)
            built = article_to_chunks(article)
            if not built:
                log.warning("No text for slug=%s, skipping", slug)
                continue
            new_chunks.extend(built)
            known_slugs.add(slug)
        except Exception as exc:
            log.warning("Parse error slug=%s — %s", slug, exc)

    log.info("New chunks this run: %d (from %d new articles)", len(new_chunks), len({c["article_slug"] for c in new_chunks}))

    if dry_run:
        log.info("Dry run: not writing file.")
        return

    data["chunks"] = merge_chunk_lists(chunks, new_chunks)
    save_output(OUTPUT_JSON, data)


def main() -> None:
    p = argparse.ArgumentParser(description="Revista Castells → embed-style JSON chunks")
    p.add_argument("--delay", type=float, default=0.5)
    p.add_argument("--per-page", type=int, default=100)
    p.add_argument("--max-pages", type=int, default=0, help="0 = all pages")
    p.add_argument("--after", default=None, help="ISO date, only posts after")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run(
        delay=args.delay,
        per_page=args.per_page,
        max_pages=args.max_pages,
        after=args.after,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
