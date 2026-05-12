"""
RAG (Retrieval-Augmented Generation) runtime: hybrid retrieval (vector + BM25)
plus reranking and metadata filtering of search results.

This module owns everything that runs at *query time*. The sister module
`backend/database_pipeline/load_castellers_info_chunks.py` owns *indexing*
(loading JSON chunks, computing embeddings, writing to Supabase). They share
only the OpenAI embedding helper and `DATABASE_URL`, which live in the loader
because the .env wiring is set up there.
"""

import os
import re
import threading
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from psycopg2 import pool as pg_pool


def _normalized_year_set(values) -> Set[int]:
    out: Set[int] = set()
    for y in values or []:
        try:
            out.add(int(y))
        except (TypeError, ValueError):
            pass
    return out


def _chunk_matches_extracted_colla(meta: Dict, detected_colles: List[str]) -> bool:
    chunk_colles = [c.lower() for c in (meta.get("colles") or []) if c]
    if not chunk_colles:
        return False
    for colla in detected_colles:
        colla_lower = colla.lower()
        for chunk_colla in chunk_colles:
            if colla_lower in chunk_colla or chunk_colla in colla_lower:
                return True
    return False


def _chunk_matches_extracted_years(meta: Dict, all_years: Set[int]) -> bool:
    if not all_years:
        return True
    chunk_years = _normalized_year_set(meta.get("years") or [])
    if chunk_years & all_years:
        return True
    for yr in meta.get("year_ranges") or []:
        yr_l = str(yr).lower()
        if any(str(y) in yr_l for y in all_years):
            return True
    return False


def filter_rag_results_by_chunk_metadata(
    results: List[Tuple[dict, float]],
    entities: dict,
) -> List[Tuple[dict, float]]:
    """
    Drop vector hits whose castellers_info_chunks metadata does not align with
    extracted colles / years from the agent (hard filter; reranking still uses
    extra cues like decades in the question text).
    If nothing would remain, returns the original list (metadata often sparse).
    """
    if not results:
        return results

    detected_colles = [c for c in (entities.get("colla") or []) if c]
    detected_anys = entities.get("anys", []) or []
    all_years = _normalized_year_set(detected_anys)

    need_colla = bool(detected_colles)
    need_year = bool(all_years)
    if not need_colla and not need_year:
        return results

    filtered = []
    for doc_info, base_score in results:
        meta = doc_info.get("meta", {}) or {}
        if need_colla and not _chunk_matches_extracted_colla(meta, detected_colles):
            continue
        if need_year and not _chunk_matches_extracted_years(meta, all_years):
            continue
        filtered.append((doc_info, base_score))

    return filtered if filtered else results


def expand_decade_to_years(question: str) -> List[int]:

    decade_patterns = {
        r'\bany[s]?\s*80\b|\bdècada.*80\b|anys\s*vuitanta': range(1980, 1990),
        r'\bany[s]?\s*70\b|\bdècada.*70\b|anys\s*setanta': range(1970, 1980),
        r'\bany[s]?\s*90\b|\bdècada.*90\b|anys\s*noranta': range(1990, 2000),
        r'\bany[s]?\s*60\b|\bdècada.*60\b|anys\s*seixanta': range(1960, 1970),
        r'\bany[s]?\s*50\b|\bdècada.*50\b|anys\s*cinquanta': range(1950, 1960),
        r'\bsegle\s*XVIII\b|segle\s*18': range(1700, 1800),
        r'\bsegle\s*XIX\b|segle\s*19': range(1800, 1900),
        r'\bsegle\s*XX\b|segle\s*20': range(1900, 2000),
    }
    
    years = []
    for pattern, year_range in decade_patterns.items():
        if re.search(pattern, question, re.IGNORECASE):
            years.extend(list(year_range))
    
    return years


def rerank_rag_results(results: list, entities: dict, question: str) -> list:

    if not results:
        return results

    results = filter_rag_results_by_chunk_metadata(results, entities)

    question_lower = question.lower()
    detected_colles = entities.get("colla", []) or []
    detected_anys = entities.get("anys", []) or []
    
    # Expand decade references to years
    expanded_years = expand_decade_to_years(question)
    all_years = _normalized_year_set(list(detected_anys) + list(expanded_years))
    
    # Extract query words for keyword matching (remove common words)
    stop_words = {'el', 'la', 'els', 'les', 'un', 'una', 'de', 'del', 'a', 'amb', 'per', 'que', 'és', 'i', 'o'}
    query_words = [w.lower() for w in re.findall(r'\b\w+\b', question) if w.lower() not in stop_words and len(w) > 2]
    
    reranked: list = []

    for doc_info, base_score in results:
        meta = doc_info.get("meta", {})
        boost = 0.0
        boost_reasons: list = []

        # 1. Colla boost — strong but no longer pinned at the top of the list.
        chunk_colles = [c.lower() for c in (meta.get("colles") or [])]
        for colla in detected_colles:
            colla_lower = colla.lower()
            for chunk_colla in chunk_colles:
                if colla_lower in chunk_colla or chunk_colla in colla_lower:
                    boost += 0.35
                    boost_reasons.append(f"colla:{colla}")
                    break

        # 2. Year boost
        chunk_years = _normalized_year_set(meta.get("years") or [])
        chunk_year_ranges = [str(yr).lower() for yr in (meta.get("year_ranges") or [])]

        year_matches = chunk_years & all_years
        if year_matches:
            boost += 0.2 * min(len(year_matches), 3)  # Cap at 0.6
            boost_reasons.append(f"years:{list(year_matches)[:3]}")

        for yr in chunk_year_ranges:
            if any(str(y) in yr for y in all_years):
                boost += 0.1
                boost_reasons.append(f"year_range:{yr}")
                break

        # 3. Keyword fuzzy matching against the chunk's `keywords` field.
        chunk_keywords = [kw.lower() for kw in (meta.get("keywords") or [])]
        keyword_matches = 0
        for query_word in query_words:
            for chunk_kw in chunk_keywords:
                similarity = SequenceMatcher(None, query_word, chunk_kw).ratio()
                if similarity > 0.7 or query_word in chunk_kw or chunk_kw in query_word:
                    keyword_matches += 1
                    break

        if keyword_matches > 0:
            kw_boost = (
                0.15 + (min(keyword_matches, 4) - 1) * 0.15
                if keyword_matches > 1
                else 0.1
            )
            boost += kw_boost
            boost_reasons.append(f"keywords:{keyword_matches}")

        # 3b. Light body-text overlap. Catches chunks whose body answers the
        # question even when the curator-set `keywords` are sparse. Bounded so
        # it can't dominate.
        chunk_text_lower = (doc_info.get("text") or "").lower()
        if query_words and chunk_text_lower:
            text_hits = sum(1 for w in query_words if w in chunk_text_lower)
            text_overlap = text_hits / max(1, len(query_words))
            if text_overlap >= 0.25:
                text_boost = min(0.10, text_overlap * 0.20)
                boost += text_boost
                boost_reasons.append(f"text:{text_hits}/{len(query_words)}")

        # 4. Category relevance boost
        category = meta.get("category", "")
        if "història" in question_lower or "origen" in question_lower:
            if category in ("history", "historia"):
                boost += 0.15
                boost_reasons.append("cat:history")
        elif "tècnic" in question_lower or "estructura" in question_lower:
            if category in ("technique", "tecnica"):
                boost += 0.15
                boost_reasons.append("cat:technique")
        elif "concurs" in question_lower:
            if category == "concurs":
                boost += 0.15
                boost_reasons.append("cat:concurs")

        # 5. Place matching
        chunk_places = [p.lower() for p in (meta.get("places") or [])]
        detected_llocs = entities.get("llocs", []) or []
        for lloc in detected_llocs:
            if lloc.lower() in chunk_places:
                boost += 0.15
                boost_reasons.append(f"place:{lloc}")
                break

        # 6. Curated-source boost. Non-revista chunks are typically
        # encyclopedic and higher-signal-per-token than revista cronicles, so
        # we nudge them up as a tie-breaker (small enough to never override
        # real evidence in revista chunks).
        chunk_id = (meta.get("chunk_id") or "")
        if chunk_id and not chunk_id.startswith("revista_"):
            boost += 0.05
            boost_reasons.append("curated")

        # 7. Penalize colla-category chunks when no colla is detected
        if not detected_colles and category == "colles":
            boost -= 0.2
            boost_reasons.append("no_colla_penalty")

        final_score = min(base_score + boost, 1.0)
        reranked.append((doc_info, final_score))

    # Single global ordering by score; let the cross-encoder-style boosts do
    # the work instead of pinning colla matches at the top regardless of
    # everything else.
    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked


# ===========================================================================
# Hybrid retrieval (vector + Catalan BM25, fused with RRF)
# ===========================================================================
#
# Flow:
#   1. Embed the (augmented) query with OpenAI.
#   2. Issue a single SQL that runs vector top-N and BM25 top-N in parallel
#      CTEs and fuses them with Reciprocal Rank Fusion.
#   3. If the fused top-k is dominated by `revista_*` chunks (which outnumber
#      curated ones ~10:1), append a small vector-only top-up of curated
#      chunks so the reranker always sees both worlds.
#
# The reranker (`rerank_rag_results` above) consumes the result.

# Reciprocal Rank Fusion constant. Standard literature value is 60; tweaks
# here barely move recall@k for top results.
RRF_K_CONSTANT = 60

# How many candidates each leg returns before fusion. Larger = better recall,
# slightly higher latency. 50 each = ~100 union, plenty for top-30 final.
HYBRID_VEC_LIMIT = 50
HYBRID_BM25_LIMIT = 50

# Per-leg weights inside RRF: rrf(d) = w_vec/(k+r_vec) + w_bm/(k+r_bm).
# Only the ratio matters for ordering; we keep both near 1.0 so the resulting
# score scale stays comparable to plain unweighted RRF (downstream reranker
# thresholds don't have to move).
#
# 1.3 / 0.7  →  ~65% semantic / 35% lexical contribution at matching ranks.
# Catalan named entities (colla, castell, any, lloc) make lexical matches
# valuable, but semantic similarity is the more reliable signal overall, so
# it gets the higher weight.
HYBRID_VEC_WEIGHT = 1.3
HYBRID_BM25_WEIGHT = 0.7

# IVFFlat probes: speed/recall trade-off for the pgvector index. The index is
# built with lists=100; lower probes = faster, slightly lower recall.
try:
    RAG_IVFFLAT_PROBES = max(1, min(100, int(os.getenv("RAG_IVFFLAT_PROBES", "25"))))
except ValueError:
    RAG_IVFFLAT_PROBES = 25

# Connection pool sizing for the hot RAG search path. Indexing scripts use a
# fresh `psycopg2.connect` instead, so this pool only sees query traffic.
try:
    RAG_DB_POOL_MIN = max(1, int(os.getenv("RAG_DB_POOL_MIN", "1")))
    RAG_DB_POOL_MAX = max(RAG_DB_POOL_MIN, int(os.getenv("RAG_DB_POOL_MAX", "8")))
except ValueError:
    RAG_DB_POOL_MIN, RAG_DB_POOL_MAX = 1, 8

# Cap the number of OR-ed terms in the BM25 tsquery. Catalan stop words are
# already filtered by the dictionary, but we still trim to avoid pathological
# queries (very long pasted text) blowing up planning time.
HYBRID_BM25_MAX_TERMS = 20

# Characters that have special meaning inside `to_tsquery` and must never
# reach the parser raw, otherwise it raises a syntax error.
_TSQUERY_BAD_CHARS_RE = re.compile(r"[&|!()*:'\"\\<>]")
_TSQUERY_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9]{3,}", re.UNICODE)


def _build_or_tsquery_terms(query: str) -> str:
    """
    Convert a free-text question into an OR-ed `to_tsquery` payload.

    Postgres' `plainto_tsquery` AND-joins all extracted lexemes, which gives
    near-zero recall on natural-language questions like
    "A quin any apareixen les colles universitàries?" — almost no chunk
    contains every term. Real BM25 engines OR the terms and let the score
    rank, which is what we want here.

    Returns an empty string when the query yields no usable tokens; callers
    should treat that as "skip the BM25 leg" (an empty tsquery never matches).
    """
    if not query:
        return ""
    cleaned = _TSQUERY_BAD_CHARS_RE.sub(" ", query.lower())
    words = _TSQUERY_WORD_RE.findall(cleaned)
    seen: Set[str] = set()
    ordered: List[str] = []
    for w in words:
        if w in seen:
            continue
        seen.add(w)
        ordered.append(w)
        if len(ordered) >= HYBRID_BM25_MAX_TERMS:
            break
    return " | ".join(ordered)


# ---- Connection pool (lazy, thread-safe) ----------------------------------

_rag_search_pool: Optional[pg_pool.ThreadedConnectionPool] = None
_rag_search_pool_lock = threading.Lock()


def _get_rag_search_pool() -> pg_pool.ThreadedConnectionPool:
    """Lazy pool for RAG retrieval only (indexing scripts use a fresh conn)."""
    global _rag_search_pool
    if _rag_search_pool is not None:
        return _rag_search_pool
    with _rag_search_pool_lock:
        if _rag_search_pool is not None:
            return _rag_search_pool
        # Imported lazily so importing rag.py never triggers .env loading or
        # OpenAI client construction at module-import time.
        from database_pipeline.load_castellers_info_chunks import DATABASE_URL
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL not set in .env file")
        _rag_search_pool = pg_pool.ThreadedConnectionPool(
            RAG_DB_POOL_MIN,
            RAG_DB_POOL_MAX,
            dsn=DATABASE_URL,
            connect_timeout=10,
        )
        return _rag_search_pool


# ---- Search ---------------------------------------------------------------

def _row_to_result_hybrid(row) -> Tuple[Dict, float]:
    (
        chunk_id, title, text, category,
        years, year_ranges, colles, places, keywords, castells,
        cos_sim, _bm25, _rrf, _vec_rank, _bm_rank,
    ) = row
    return (
        {
            "meta": {
                "chunk_id": chunk_id,
                "title": title,
                "category": category,
                "years": years or [],
                "year_ranges": year_ranges or [],
                "colles": colles or [],
                "places": places or [],
                "keywords": keywords or [],
                "castells": castells or [],
            },
            "text": text,
        },
        float(cos_sim or 0.0),
    )


def _row_to_result_vector_only(row) -> Tuple[Dict, float]:
    (
        chunk_id, title, text, category,
        years, year_ranges, colles, places, keywords, castells, cos_sim,
    ) = row
    return (
        {
            "meta": {
                "chunk_id": chunk_id,
                "title": title,
                "category": category,
                "years": years or [],
                "year_ranges": year_ranges or [],
                "colles": colles or [],
                "places": places or [],
                "keywords": keywords or [],
                "castells": castells or [],
            },
            "text": text,
        },
        float(cos_sim or 0.0),
    )


def search_castellers_info(
    query: str,
    k: int = 30,
    min_non_revista: int = 10,
    non_revista_topup: int = 10,
) -> List[Tuple[Dict, float]]:
    """
    Hybrid retrieval over `castellers_info_chunks`: dense (OpenAI embeddings)
    + sparse (Postgres `tsvector` with the Catalan analyzer) fused via
    Reciprocal Rank Fusion. Returns the top `k` candidates with cosine
    similarity as the score so downstream reranker thresholds remain
    interpretable.

    Args:
        query: Search text for hybrid retrieval (typically the current question
            plus extracted entity names; short follow-ups may prepend the
            previous user question — see `agent.py::_build_rag_retrieval_text`).
        k: Number of top candidates to return after RRF fusion.
        min_non_revista: If the fused top-k contains fewer than this many
            curated (non-`revista_*`) chunks, run a separate vector top-up to
            ensure curated chunks always reach the reranker.
        non_revista_topup: Size of that secondary curated-only query.

    Returns:
        List of (doc_info, cosine_similarity) tuples, ordered by RRF fusion
        score. The reranker is responsible for the final ordering.
    """
    # Imported lazily to avoid pulling OpenAI/psycopg2 setup into rag.py at
    # module-import time (and to keep this file independent of indexing).
    from database_pipeline.load_castellers_info_chunks import (
        DATABASE_URL,
        get_embedding_single,
    )

    print(f"[RAG Search] Starting hybrid search for: {query[:80]}...", flush=True)

    embed_start = datetime.now()
    q_emb = get_embedding_single(query)
    embed_time = (datetime.now() - embed_start).total_seconds() * 1000
    print(f"[TIMING] Query embedding (OpenAI API): {embed_time:.2f}ms", flush=True)

    conn = None
    cur = None
    pool_obj = None
    conn_start = datetime.now()
    try:
        pool_obj = _get_rag_search_pool()
        conn = pool_obj.getconn()
        conn_time = (datetime.now() - conn_start).total_seconds() * 1000
        host = urlparse(DATABASE_URL).hostname if DATABASE_URL else "?"
        print(f"[RAG Search] Pooled connection in {conn_time:.2f}ms ({host})", flush=True)
        cur = conn.cursor()

        embedding_str = "[" + ",".join(str(x) for x in q_emb.tolist()) + "]"

        cur.execute(f"SET ivfflat.probes = {RAG_IVFFLAT_PROBES};")

        or_terms = _build_or_tsquery_terms(query)
        bm25_enabled = bool(or_terms)

        # Hybrid query: vector top-N ∪ BM25 top-N → RRF fusion → top-k.
        #
        # Notes on the design:
        # - BM25 uses `to_tsquery('catalan', %(or_terms)s)` with OR semantics
        #   (`a | b | c`). `plainto_tsquery` would AND every lexeme, which on
        #   natural-language questions returns ~0 matches in this corpus.
        #   `or_terms` is sanitized in Python (`_build_or_tsquery_terms`) so
        #   the parser never sees `& | ! ( ) : *` etc.
        # - The `fused` CTE is driven off `vec ∪ bm` chunk IDs (≈50–100 rows)
        #   instead of scanning the whole table. We reuse `vec.cos_sim` when
        #   available so cosine similarity is computed at most once per row.
        # - When `or_terms` is empty (very short queries), we fall back to a
        #   pure vector path — same shape, no BM25 column.
        if bm25_enabled:
            hybrid_sql = """
                WITH vec AS (
                    SELECT
                        chunk_id,
                        1 - (combined_embedding <=> %(emb)s::vector) AS cos_sim,
                        row_number() OVER (
                            ORDER BY combined_embedding <=> %(emb)s::vector
                        ) AS r
                    FROM castellers_info_chunks
                    ORDER BY combined_embedding <=> %(emb)s::vector
                    LIMIT %(vec_k)s
                ),
                tq AS (
                    SELECT to_tsquery('catalan', %(or_terms)s) AS q
                ),
                bm AS (
                    SELECT
                        c.chunk_id,
                        ts_rank_cd(c.search_tsv, tq.q) AS bm25,
                        row_number() OVER (
                            ORDER BY ts_rank_cd(c.search_tsv, tq.q) DESC
                        ) AS r
                    FROM castellers_info_chunks c
                    CROSS JOIN tq
                    WHERE c.search_tsv @@ tq.q
                    ORDER BY ts_rank_cd(c.search_tsv, tq.q) DESC
                    LIMIT %(bm_k)s
                ),
                ids AS (
                    SELECT chunk_id FROM vec
                    UNION
                    SELECT chunk_id FROM bm
                ),
                fused AS (
                    SELECT
                        c.chunk_id, c.title, c.text, c.category,
                        c.years, c.year_ranges, c.colles, c.places,
                        c.keywords, c.castells,
                        COALESCE(
                            vec.cos_sim,
                            1 - (c.combined_embedding <=> %(emb)s::vector)
                        ) AS cos_sim,
                        COALESCE(bm.bm25, 0)                              AS bm25,
                        COALESCE(%(w_vec)s / (%(rrf_const)s + vec.r), 0)
                          + COALESCE(%(w_bm)s / (%(rrf_const)s + bm.r), 0) AS rrf,
                        vec.r AS vec_rank,
                        bm.r  AS bm_rank
                    FROM ids
                    JOIN castellers_info_chunks c USING (chunk_id)
                    LEFT JOIN vec ON vec.chunk_id = c.chunk_id
                    LEFT JOIN bm  ON bm.chunk_id  = c.chunk_id
                )
                SELECT
                    chunk_id, title, text, category,
                    years, year_ranges, colles, places, keywords, castells,
                    cos_sim, bm25, rrf, vec_rank, bm_rank
                FROM fused
                ORDER BY rrf DESC, cos_sim DESC
                LIMIT %(final_k)s;
            """
        else:
            # Vector-only fallback (an empty tsquery never matches anything).
            hybrid_sql = """
                WITH vec AS (
                    SELECT
                        chunk_id,
                        1 - (combined_embedding <=> %(emb)s::vector) AS cos_sim,
                        row_number() OVER (
                            ORDER BY combined_embedding <=> %(emb)s::vector
                        ) AS r
                    FROM castellers_info_chunks
                    ORDER BY combined_embedding <=> %(emb)s::vector
                    LIMIT %(vec_k)s
                )
                SELECT
                    c.chunk_id, c.title, c.text, c.category,
                    c.years, c.year_ranges, c.colles, c.places,
                    c.keywords, c.castells,
                    vec.cos_sim                                  AS cos_sim,
                    0::float                                     AS bm25,
                    %(w_vec)s / (%(rrf_const)s + vec.r)          AS rrf,
                    vec.r                                        AS vec_rank,
                    NULL::bigint                                 AS bm_rank
                FROM vec
                JOIN castellers_info_chunks c USING (chunk_id)
                ORDER BY rrf DESC, cos_sim DESC
                LIMIT %(final_k)s;
            """

        params: Dict[str, Any] = {
            "emb": embedding_str,
            "or_terms": or_terms,
            "vec_k": HYBRID_VEC_LIMIT,
            "bm_k": HYBRID_BM25_LIMIT,
            "rrf_const": RRF_K_CONSTANT,
            "w_vec": HYBRID_VEC_WEIGHT,
            "w_bm": HYBRID_BM25_WEIGHT,
            "final_k": k,
        }

        db_start = datetime.now()
        cur.execute(hybrid_sql, params)
        rows = cur.fetchall()
        db_time = (datetime.now() - db_start).total_seconds() * 1000

        vec_only = sum(1 for r in rows if r[13] is not None and r[14] is None)
        bm_only = sum(1 for r in rows if r[13] is None and r[14] is not None)
        both = sum(1 for r in rows if r[13] is not None and r[14] is not None)
        leg = "hybrid" if bm25_enabled else "vector-only"
        print(
            f"[TIMING] Hybrid DB search ({leg}): {db_time:.2f}ms "
            f"({len(rows)} results: vec-only={vec_only}, bm-only={bm_only}, "
            f"both={both}; bm_terms={or_terms[:80] or '∅'})",
            flush=True,
        )

        results: List[Tuple[Dict, float]] = [_row_to_result_hybrid(r) for r in rows]

        # ---- Non-revista top-up ------------------------------------------
        # The fused top-k may still be dominated by `revista_*` chunks
        # because they outnumber curated ones ~10:1. Make sure the reranker
        # always sees curated chunks: if fewer than `min_non_revista` are
        # present, run a vector-only secondary query restricted to
        # non-`revista_*` and append the missing ones.
        if min_non_revista and non_revista_topup:
            non_revista_count = sum(
                1 for doc, _ in results
                if not (doc["meta"].get("chunk_id") or "").startswith("revista_")
            )
            if non_revista_count < min_non_revista:
                existing_ids = {doc["meta"]["chunk_id"] for doc, _ in results}
                topup_start = datetime.now()
                cur.execute(
                    """
                    SELECT
                        chunk_id, title, text, category,
                        years, year_ranges, colles, places, keywords, castells,
                        1 - (combined_embedding <=> %s::vector) AS cos_sim
                    FROM castellers_info_chunks
                    WHERE LEFT(chunk_id, 8) <> 'revista_'
                    ORDER BY combined_embedding <=> %s::vector
                    LIMIT %s
                    """,
                    [embedding_str, embedding_str, non_revista_topup],
                )
                topup_rows = cur.fetchall()
                topup_time = (datetime.now() - topup_start).total_seconds() * 1000
                added = 0
                for trow in topup_rows:
                    if trow[0] in existing_ids:
                        continue
                    results.append(_row_to_result_vector_only(trow))
                    existing_ids.add(trow[0])
                    added += 1
                print(
                    f"[RAG Search] Non-revista top-up: had "
                    f"{non_revista_count}/{min_non_revista}, appended {added} "
                    f"curated chunks ({topup_time:.2f}ms)",
                    flush=True,
                )

        return results

    except Exception as e:
        print(f"Error searching castellers_info_chunks: {e}")
        if conn is not None and not conn.closed:
            try:
                conn.rollback()
            except Exception:
                pass
        return []
    finally:
        if cur is not None:
            cur.close()
        if conn is not None and pool_obj is not None:
            pool_obj.putconn(conn)


# ---- Cache warm-up --------------------------------------------------------

# A single OR-ed tsquery covering the most-frequently-hit Catalan castellers
# stems pulls a wide swath of GIN posting lists into the buffer cache in one
# shot. Each word here is intentionally chosen to:
#   1. stem to a high-frequency lexeme in the corpus (colla, casteller, any,
#      diada, plaça, pilar, concurs, història, actuació, tècnica, gamma…), so
#      a real user query about any of these topics finds its posting list
#      already hot;
#   2. cover the major domain "facets" we see in real traffic — colles
#      (universitàries, internacionals, locals), tradition (història, tècnica,
#      tradicional), event types (concurs, diada, actuació), structures
#      (castell, pilar, gamma).
#
# This is much more effective than a single-noun warmup: for a single hybrid
# call it forces Postgres to read ~10-20 posting lists into memory, so most
# subsequent real questions land on warm GIN pages regardless of which of
# these terms they happen to mention.
_WARMUP_QUERY = (
    "colla castellera tradicional història concurs diada actuació castellers diada actaució"
    "pilar castell gamma tècnica plaça any universitària internacional"
)

# A second, very different query specifically warms the IVFFlat clusters that
# the first query won't touch. IVFFlat is lookup-by-cluster, so two distinct
# semantic anchors load distinct cluster pages.
_WARMUP_QUERY_SEMANTIC_2 = (
    "història dels castells segle XIX origen tradició catalana concurs minyons xiquets dades"
)


def warm_rag_caches() -> None:
    """
    Pre-load OpenAI + Supabase caches so the first real user doesn't pay the
    cold-start tax. Designed to be called from FastAPI's startup hook,
    ideally as a background task (it takes a few seconds end-to-end).

    We fire two diverse hybrid queries:
      1. A wide OR-ed lexical query that pulls the most common Catalan
         castellers GIN posting lists into the buffer cache.
      2. A semantically distant query that loads a different region of the
         IVFFlat index than the first one would.

    Failures are logged but never raised — the app still starts and the first
    real query just pays the cold-start cost it would have paid anyway.
    """
    overall_start = datetime.now()
    print("[RAG Warmup] Starting cache pre-warm…", flush=True)
    total_rows = 0
    try:
        # Lexical-rich pass: many GIN posting lists, plus the top-up path
        # (min_non_revista=10 forces the secondary curated vector query to
        # fire — that's the one that paid ~3 s on a cold cache).
        results_1 = search_castellers_info(
            _WARMUP_QUERY,
            k=5,
            min_non_revista=10,
            non_revista_topup=5,
        )
        total_rows += len(results_1)

        # Semantically distant pass: warms a different IVFFlat cluster region.
        # Skip the top-up here (already warmed by pass 1) to keep the warmup
        # short.
        results_2 = search_castellers_info(
            _WARMUP_QUERY_SEMANTIC_2,
            k=5,
            min_non_revista=0,
            non_revista_topup=0,
        )
        total_rows += len(results_2)

        elapsed = (datetime.now() - overall_start).total_seconds() * 1000
        print(
            f"[RAG Warmup] Done in {elapsed:.0f}ms ({total_rows} rows across "
            f"2 passes). First real query should now be on warm caches.",
            flush=True,
        )
    except Exception as e:  # pragma: no cover - best-effort warmup
        elapsed = (datetime.now() - overall_start).total_seconds() * 1000
        print(
            f"[RAG Warmup] Failed after {elapsed:.0f}ms: {e}. "
            f"First real query will be cold (no functional impact).",
            flush=True,
        )
