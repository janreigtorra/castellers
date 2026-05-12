#!/usr/bin/env python3
"""
load_castellers_info_chunks.py
Carrega els chunks des de:
  - data_basic/data_to_embed/castellers_info_chunks.json
  - data_basic/data_to_embed/revista_castells_scraper.json
a la mateixa taula Supabase amb embeddings optimitzats.

Utilitza:
- OpenAI text-embedding-3-small (dimensions configurables, veure EMBEDDING_DIM)
- Embeddings combinats (TITLE_WEIGHT / TEXT_WEIGHT): es calculen amb title + text a l'API,
  però només es persisteix ``combined_embedding`` a la BD (estalvi d'espai vs. guardar també title/text).
- Per defecte només indexa chunks nous (chunk_id = camp "id" del JSON). Usa --rebuild per recrear la taula i reincrustar-ho tot.
"""

import argparse
import os
import json
import re
import psycopg2
from typing import List, Dict, Any, Tuple, Set, Optional
from openai import OpenAI
import numpy as np
from tqdm import tqdm
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urlparse

# Load .env from multiple possible locations
env_paths = [
    Path(__file__).parent.parent.parent / ".env",      # project root
    Path(__file__).parent.parent.parent / ".env.bak",  # project root backup
    Path(__file__).parent.parent / ".env",              # backend folder
    Path(__file__).parent / ".env",                     # database_pipeline folder
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded .env from: {env_path}")
        break
else:
    load_dotenv()  # Try default locations

# ---------- CONFIGURACIÓ ----------
def convert_to_pooler_url(database_url: str) -> str:
    """Convert direct connection URL (port 5432) to Session Pooler URL (port 6543, IPv4 compatible)"""
    parsed = urlparse(database_url)
    
    # If already using pooler port, return as-is
    if parsed.port == 6543:
        return database_url
    
    # Build new URL with pooler port (6543) - works with IPv4 networks
    pooler_url = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:6543{parsed.path}"
    
    return pooler_url

_raw_database_url = os.getenv("DATABASE_URL")
DATABASE_URL = convert_to_pooler_url(_raw_database_url) if _raw_database_url else None
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI's fast & cheap model
# text-embedding-3-small admet dimensions entre 1 i 1536 (API ``dimensions``)
EMBEDDING_DIM = 1024
TITLE_WEIGHT = 0.15
TEXT_WEIGHT = 0.85
BATCH_SIZE = 64  # Chunks per DB batch (cada chunk = 2 texts a l'API d'embeddings)
_DATA_EMBED = os.path.join(
    os.path.dirname(__file__), "..", "data_basic", "data_to_embed"
)
CASTELLERS_CHUNKS_JSON = os.path.join(_DATA_EMBED, "castellers_info_chunks.json")
REVISTA_CHUNKS_JSON = os.path.join(_DATA_EMBED, "revista_castells_scraper.json")
# Compatibilitat amb codi antic que només referenciava un fitxer
JSON_FILE_PATH = CASTELLERS_CHUNKS_JSON

# ---------- OPENAI CLIENT ----------
_openai_client = None

def get_openai_client() -> OpenAI:
    """Get cached OpenAI client"""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


# text-embedding-3-small admits up to 8192 tokens per input. We leave a buffer.
EMBEDDING_MAX_TOKENS = 8000
# Char-based fallback when tiktoken is not installed. Catalan averages
# ~4 chars/token with cl100k_base, so 28000 chars stays comfortably under 8192.
EMBEDDING_MAX_CHARS_FALLBACK = 28000

try:  # tiktoken is optional but gives precise truncation
    import tiktoken  # type: ignore

    _ENCODING = tiktoken.get_encoding("cl100k_base")

    def _truncate_for_embedding(text: str) -> str:
        if not text:
            return text
        tokens = _ENCODING.encode(text)
        if len(tokens) <= EMBEDDING_MAX_TOKENS:
            return text
        return _ENCODING.decode(tokens[:EMBEDDING_MAX_TOKENS])

    _TRUNCATION_MODE = "tiktoken"
except Exception:  # pragma: no cover - fallback when tiktoken is missing

    def _truncate_for_embedding(text: str) -> str:
        if not text:
            return text
        if len(text) <= EMBEDDING_MAX_CHARS_FALLBACK:
            return text
        return text[:EMBEDDING_MAX_CHARS_FALLBACK]

    _TRUNCATION_MODE = "char"


def _safe_inputs(texts: List[str]) -> List[str]:
    """Return texts truncated to fit within the embedding model's token limit."""
    return [_truncate_for_embedding(t or "") for t in texts]


def get_embeddings_batch(texts: List[str]) -> np.ndarray:
    """Get embeddings for a batch of texts using OpenAI API.

    Inputs are pre-truncated to stay within the model's per-input token limit
    (text-embedding-3-small: 8192 tokens). Without this, a single overlong
    input would cause OpenAI to reject the whole batch with HTTP 400.
    """
    client = get_openai_client()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=_safe_inputs(texts),
        dimensions=EMBEDDING_DIM,
    )

    embeddings = np.array([item.embedding for item in response.data], dtype="float32")

    # Normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0.0] = 1e-9
    embeddings = embeddings / norms

    return embeddings

def get_embedding_single(text: str) -> np.ndarray:
    """Get embedding for a single text"""
    client = get_openai_client()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[_truncate_for_embedding(text or "")],
        dimensions=EMBEDDING_DIM,
    )

    embedding = np.array(response.data[0].embedding, dtype="float32")
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    return embedding

def preload_multilingual_model():
    """Check OpenAI API connectivity (no heavy model to preload with OpenAI)"""
    print(f"[RAG] Using OpenAI embeddings ({EMBEDDING_MODEL}, {EMBEDDING_DIM}d)", flush=True)
    if not OPENAI_API_KEY:
        print("[RAG] WARNING: OPENAI_API_KEY not set!", flush=True)
    else:
        print(f"[RAG] OpenAI API key configured ✓", flush=True)
# ------------------------------------


def get_supabase_connection():
    """Obté una connexió a Supabase amb timeout"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not set in .env file")
    
    parsed = urlparse(DATABASE_URL)
    print(f"🔗 Connecting to: {parsed.hostname}:{parsed.port}")
    
    try:
        # Use 10 second timeout to avoid hanging
        return psycopg2.connect(DATABASE_URL, connect_timeout=10)
    except psycopg2.OperationalError as e:
        error_msg = str(e).lower()
        if 'could not translate host name' in error_msg or 'nodename' in error_msg or 'timeout' in error_msg:
            print("\n" + "="*70)
            print("⚠️  DATABASE CONNECTION FAILED")
            print("="*70)
            print(f"\nError: {e}")
            print("\nThe hostname in your DATABASE_URL may require IPv6 or is unreachable.")
            print("You need to use the Session Pooler URL instead.")
            print("\n📋 TO FIX THIS:")
            print("1. Go to: https://supabase.com/dashboard/project/vvbnjvtkqsgiryideenl/settings/database")
            print("2. Scroll to 'Connection string'")
            print("3. Click 'URI' tab, then select 'Session mode' (port 6543)")
            print("4. Copy the URL - it should look like:")
            print("   postgresql://postgres.vvbnjvtkqsgiryideenl:[PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres")
            print("\n5. Update your .env.bak file with this new DATABASE_URL")
            print("="*70 + "\n")
        raise


def enable_pgvector(conn):
    """Habilita l'extensió pgvector si no està habilitada"""
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        print("✓ pgvector extension enabled")
    except Exception as e:
        print(f"Warning: Could not enable pgvector: {e}")
    finally:
        cur.close()


def _parse_vector_dim(format_type: Optional[str]) -> Optional[int]:
    if not format_type:
        return None
    m = re.search(r"vector\((\d+)\)", format_type, re.IGNORECASE)
    return int(m.group(1)) if m else None


# Catalan BM25 weighted tsvector. Postgres marks the built-in `to_tsvector`
# as STABLE (because it depends on the search_path / dictionary state), and a
# STABLE function is NOT allowed in a STORED generated column.
# The accepted workaround is to wrap the expression in our own IMMUTABLE SQL
# function and reference that function in the generated column.
# Weights: A = title, B = entity arrays (colles, castells, places, keywords),
# C = body text.
SEARCH_TSV_FUNCTION_NAME = "castellers_info_chunks_search_tsv_v1"

SEARCH_TSV_FUNCTION_SQL = f"""
CREATE OR REPLACE FUNCTION {SEARCH_TSV_FUNCTION_NAME}(
    p_title    text,
    p_text     text,
    p_colles   text[],
    p_castells text[],
    p_places   text[],
    p_keywords text[]
) RETURNS tsvector
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT
        setweight(to_tsvector('catalan'::regconfig, coalesce(p_title, '')), 'A') ||
        setweight(to_tsvector(
            'catalan'::regconfig,
            coalesce(array_to_string(p_colles, ' '), '')   || ' ' ||
            coalesce(array_to_string(p_castells, ' '), '') || ' ' ||
            coalesce(array_to_string(p_places, ' '), '')   || ' ' ||
            coalesce(array_to_string(p_keywords, ' '), '')
        ), 'B') ||
        setweight(to_tsvector('catalan'::regconfig, coalesce(p_text, '')), 'C')
$$;
"""

# BEFORE INSERT/UPDATE trigger keeps `search_tsv` in sync with the source
# columns. We use a plain column + trigger instead of a STORED generated
# column because adding a STORED generated column requires a full table
# rewrite that uses `maintenance_work_mem` (Supabase default 32 MB), which
# blows up on tables of even modest size.
SEARCH_TSV_TRIGGER_FUNCTION_NAME = "castellers_info_chunks_search_tsv_trg_v1"
SEARCH_TSV_TRIGGER_NAME = "castellers_info_chunks_search_tsv_trg"

SEARCH_TSV_TRIGGER_FUNCTION_SQL = f"""
CREATE OR REPLACE FUNCTION {SEARCH_TSV_TRIGGER_FUNCTION_NAME}() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.search_tsv := {SEARCH_TSV_FUNCTION_NAME}(
        NEW.title, NEW.text, NEW.colles, NEW.castells, NEW.places, NEW.keywords
    );
    RETURN NEW;
END;
$$;
"""

SEARCH_TSV_TRIGGER_SQL = f"""
DROP TRIGGER IF EXISTS {SEARCH_TSV_TRIGGER_NAME} ON castellers_info_chunks;
CREATE TRIGGER {SEARCH_TSV_TRIGGER_NAME}
BEFORE INSERT OR UPDATE OF title, text, colles, castells, places, keywords
ON castellers_info_chunks
FOR EACH ROW EXECUTE FUNCTION {SEARCH_TSV_TRIGGER_FUNCTION_NAME}();
"""

# Batch size for the one-time backfill. Each row's tsvector is small (a few KB)
# so 500 keeps memory usage trivial while still progressing quickly.
SEARCH_TSV_BACKFILL_BATCH_SIZE = 500


def _ensure_search_tsv_function(cur) -> None:
    """Create-or-replace the IMMUTABLE wrapper used by the trigger."""
    cur.execute(SEARCH_TSV_FUNCTION_SQL)


def _backfill_search_tsv(cur, conn) -> int:
    """Populate `search_tsv` for any existing rows where it's NULL, in batches."""
    total_updated = 0
    while True:
        cur.execute(
            f"""
            WITH cte AS (
                SELECT chunk_id FROM castellers_info_chunks
                WHERE search_tsv IS NULL
                LIMIT {SEARCH_TSV_BACKFILL_BATCH_SIZE}
            )
            UPDATE castellers_info_chunks AS c
            SET search_tsv = {SEARCH_TSV_FUNCTION_NAME}(
                c.title, c.text, c.colles, c.castells, c.places, c.keywords
            )
            FROM cte
            WHERE c.chunk_id = cte.chunk_id;
            """
        )
        updated = cur.rowcount or 0
        if updated == 0:
            break
        total_updated += updated
        # Commit each batch so we don't keep one huge transaction open.
        conn.commit()
        print(f"      … backfilled {total_updated} rows so far")
    return total_updated


def _ensure_search_tsv_column(cur, conn) -> None:
    """Idempotent migration: ensure `search_tsv` column + trigger exist and
    every existing row is populated.

    Order matters:
      1. Ensure the IMMUTABLE search_tsv_v1(...) function exists.
      2. Add the plain `search_tsv tsvector` column if missing
         (NO `GENERATED ALWAYS AS …` — avoids the table rewrite).
      3. Ensure the trigger function + trigger exist (CREATE OR REPLACE).
      4. Batched backfill of any rows where search_tsv IS NULL.
    """
    _ensure_search_tsv_function(cur)

    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'castellers_info_chunks'
          AND column_name = 'search_tsv'
        """
    )
    column_exists = bool(cur.fetchone())

    if not column_exists:
        print("🆕 Adding `search_tsv` column to castellers_info_chunks…")
        cur.execute(
            "ALTER TABLE castellers_info_chunks ADD COLUMN search_tsv tsvector;"
        )

    # Always ensure the trigger is in place (idempotent).
    cur.execute(SEARCH_TSV_TRIGGER_FUNCTION_SQL)
    cur.execute(SEARCH_TSV_TRIGGER_SQL)
    conn.commit()

    # Backfill any NULL rows. On the first migration this populates everything;
    # on subsequent runs it's typically a no-op (the trigger keeps things in
    # sync), but acts as a safety net if rows ever sneak in NULL.
    cur.execute(
        "SELECT COUNT(*) FROM castellers_info_chunks WHERE search_tsv IS NULL;"
    )
    null_count = cur.fetchone()[0] or 0
    if null_count:
        print(
            f"   Backfilling `search_tsv` for {null_count} rows in batches "
            f"of {SEARCH_TSV_BACKFILL_BATCH_SIZE}…"
        )
        total = _backfill_search_tsv(cur, conn)
        print(f"   ✓ Backfill complete ({total} rows updated).")
    elif not column_exists:
        print("   ✓ Column added (no rows to backfill).")


def _create_castellers_info_chunks_indexes(cur) -> None:
    # GIN/IVFFlat index builds use maintenance_work_mem; Supabase default is
    # 32 MB which is too low for our tsvector GIN over thousands of chunks.
    # SET LOCAL is bounded by the current transaction and is allowed by
    # Supabase. If the role lacks permission we just skip silently.
    try:
        cur.execute("SET LOCAL maintenance_work_mem = '256MB';")
    except Exception as exc:
        print(f"   ⚠️  Could not raise maintenance_work_mem: {exc}")

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cic_combined_embedding
        ON castellers_info_chunks
        USING ivfflat (combined_embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cic_years ON castellers_info_chunks USING GIN (years);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cic_year_ranges ON castellers_info_chunks USING GIN (year_ranges);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cic_colles ON castellers_info_chunks USING GIN (colles);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cic_places ON castellers_info_chunks USING GIN (places);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cic_keywords ON castellers_info_chunks USING GIN (keywords);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cic_castells ON castellers_info_chunks USING GIN (castells);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cic_category ON castellers_info_chunks(category);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cic_search_tsv ON castellers_info_chunks USING GIN (search_tsv);"
    )


def _create_castellers_info_chunks_table(cur) -> None:
    # The IMMUTABLE wrapper used by the trigger must exist first.
    _ensure_search_tsv_function(cur)
    cur.execute(
        f"""
        CREATE TABLE castellers_info_chunks (
            chunk_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            category TEXT NOT NULL,
            years INTEGER[],
            year_ranges TEXT[],
            colles TEXT[],
            places TEXT[],
            keywords TEXT[],
            castells TEXT[],
            combined_embedding vector({EMBEDDING_DIM}),
            search_tsv tsvector,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    )
    # Trigger keeps search_tsv in sync with title/text/arrays on every
    # INSERT/UPDATE. Plain column + trigger avoids the STORED-generated-column
    # table rewrite that needs > maintenance_work_mem on large tables.
    cur.execute(SEARCH_TSV_TRIGGER_FUNCTION_SQL)
    cur.execute(SEARCH_TSV_TRIGGER_SQL)
    _create_castellers_info_chunks_indexes(cur)
    print(f"✓ Created castellers_info_chunks with vector({EMBEDDING_DIM})")


def ensure_castellers_info_chunks_table(conn, rebuild: bool) -> None:
    """
    Crea la taula si no existeix. Si rebuild=True, fa DROP i torna a crear.
    Si la taula existeix i la dimensió del vector no coincideix amb EMBEDDING_DIM, llença error (cal --rebuild).
    """
    cur = conn.cursor()
    if rebuild:
        cur.execute("DROP TABLE IF EXISTS castellers_info_chunks CASCADE;")
        conn.commit()
        print("✓ Dropped castellers_info_chunks (--rebuild)")

    cur.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'castellers_info_chunks'
        );
    """
    )
    exists = cur.fetchone()[0]

    if not exists:
        _create_castellers_info_chunks_table(cur)
        conn.commit()
        cur.close()
        return

    cur.execute(
        """
        SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
        WHERE c.relname = 'castellers_info_chunks'
          AND a.attname = 'combined_embedding'
          AND a.attnum > 0 AND NOT a.attisdropped
    """
    )
    row = cur.fetchone()
    dim = _parse_vector_dim(row[0] if row else None)
    if dim is not None and dim != EMBEDDING_DIM:
        cur.close()
        raise ValueError(
            f"La taula usa vector({dim}) però EMBEDDING_DIM={EMBEDDING_DIM}. "
            "Executa amb --rebuild per eliminar la taula i tornar a generar tots els embeddings."
        )

    _ensure_search_tsv_column(cur, conn)
    _create_castellers_info_chunks_indexes(cur)
    conn.commit()
    cur.close()
    print("✓ Taula castellers_info_chunks ja existeix (dimensions OK)")


def get_existing_chunk_ids(conn) -> Set[str]:
    cur = conn.cursor()
    cur.execute("SELECT chunk_id FROM castellers_info_chunks;")
    ids = {r[0] for r in cur.fetchall() if r[0]}
    cur.close()
    return ids


def load_json_chunks(json_path: str) -> List[Dict[str, Any]]:
    """Carrega els chunks del fitxer JSON"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = data.get("chunks", [])
    metadata = data.get("metadata", {})

    print(f"✓ Loaded {len(chunks)} chunks from {os.path.basename(json_path)}")
    print(f"  Source: {metadata.get('source', 'unknown')}")
    print(f"  Description: {metadata.get('description', 'N/A')}")

    return chunks


def load_all_embedding_chunks(
    castellers_path: str = CASTELLERS_CHUNKS_JSON,
    revista_path: str = REVISTA_CHUNKS_JSON,
) -> List[Dict[str, Any]]:
    """
    Combina castellers + revista. Ordre: primer castellers, després revista.
    Els ``id`` han de ser únics; si hi ha duplicat, es conserva el primer.
    """
    seen_ids: Set[str] = set()
    combined: List[Dict[str, Any]] = []

    def ingest(path: str, label: str) -> None:
        if not os.path.isfile(path):
            print(f"⚠️  Fitxer absent, s'omet [{label}]: {path}")
            return
        for c in load_json_chunks(path):
            cid = c.get("id")
            if not cid or not isinstance(cid, str):
                print(f"⚠️  Chunk sense 'id' vàlid a {label}, s'omet (title={c.get('title', '')[:40]!r})")
                continue
            if cid in seen_ids:
                print(f"⚠️  id duplicat '{cid}' a {label}, es manté el primer")
                continue
            seen_ids.add(cid)
            combined.append(c)

    ingest(castellers_path, "castellers")
    ingest(revista_path, "revista")
    print(f"✓ Total chunks únics per indexar (unió): {len(combined)}")
    return combined


def _prepare_chunks_for_index(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Només chunks amb id i text no buit."""
    out: List[Dict[str, Any]] = []
    for c in chunks:
        cid = c.get("id")
        text = (c.get("text") or "").strip()
        if not cid or not isinstance(cid, str):
            continue
        if not text:
            continue
        out.append(c)
    return out


def index_chunks_to_supabase(chunks: List[Dict[str, Any]], rebuild: bool = False) -> None:
    """
    Indexa chunks a Supabase. Per defecte només afegeix ``chunk_id`` encara no presents
    (idempotent respecte al scraper de revista). Usa rebuild=True per DROP + tot de nou.
    """
    conn = get_supabase_connection()
    enable_pgvector(conn)
    ensure_castellers_info_chunks_table(conn, rebuild=rebuild)

    print(f"\n📥 OpenAI embeddings: {EMBEDDING_MODEL} ({EMBEDDING_DIM}d)")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in .env file")

    prepared = _prepare_chunks_for_index(chunks)
    if rebuild:
        to_process = prepared
        print(f"\n🔄 Mode --rebuild: embedding {len(to_process)} chunks (tots els vàlids).")
    else:
        existing = get_existing_chunk_ids(conn)
        to_process = [c for c in prepared if c["id"] not in existing]
        skipped = len(prepared) - len(to_process)
        print(
            f"\n🔄 Incremental: {skipped} ja a la BD, {len(to_process)} nous a embedding+insert."
        )

    if not to_process:
        conn.close()
        print("✅ Res a fer.")
        return

    cur = conn.cursor()
    inserted = 0
    errors = 0

    for i in tqdm(range(0, len(to_process), BATCH_SIZE), desc="Embedding batches"):
        batch = to_process[i : i + BATCH_SIZE]
        flat_inputs: List[str] = []
        for c in batch:
            flat_inputs.append(c.get("title") or "")
            flat_inputs.append((c.get("text") or "").strip())

        # chunk_embs[j] is a (title_emb, text_emb) tuple or None when that chunk
        # could not be embedded.
        chunk_embs: List[Optional[Tuple[np.ndarray, np.ndarray]]] = []

        try:
            embs = get_embeddings_batch(flat_inputs)
            chunk_embs = [(embs[2 * j], embs[2 * j + 1]) for j in range(len(batch))]
        except Exception as batch_err:
            # OpenAI rejects the whole batch if any single input is too long
            # (or transient errors). Fall back to per-chunk embedding so one
            # bad chunk doesn't drop the rest.
            print(
                f"\n⚠️  Batch starting {i} failed ({batch_err}); falling back to "
                f"per-chunk embedding for {len(batch)} chunks."
            )
            for c in batch:
                title = c.get("title") or ""
                text = (c.get("text") or "").strip()
                try:
                    one = get_embeddings_batch([title, text])
                    chunk_embs.append((one[0], one[1]))
                except Exception as one_err:
                    print(
                        f"   ⚠️  Skipping chunk '{(c.get('id') or '?')[:64]}': {one_err}"
                    )
                    chunk_embs.append(None)

        for j, chunk in enumerate(batch):
            if chunk_embs[j] is None:
                errors += 1
                continue
            title_emb, text_emb = chunk_embs[j]
            combined_emb = TITLE_WEIGHT * title_emb + TEXT_WEIGHT * text_emb
            nrm = np.linalg.norm(combined_emb)
            if nrm > 0:
                combined_emb = combined_emb / nrm

            chunk_id = chunk["id"]
            title = chunk.get("title") or ""
            text = (chunk.get("text") or "").strip()
            category = chunk.get("category") or ""
            years = chunk.get("years", []) or []
            year_ranges = chunk.get("year_ranges", []) or []
            colles = chunk.get("colles", []) or []
            places = chunk.get("places", []) or []
            keywords = chunk.get("keywords", []) or []
            castells = chunk.get("castells", []) or []

            try:
                cur.execute(
                    """
                    INSERT INTO castellers_info_chunks (
                        chunk_id, title, text, category,
                        years, year_ranges, colles, places, keywords, castells,
                        combined_embedding
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s
                    )
                    ON CONFLICT (chunk_id) DO NOTHING
                    """,
                    (
                        chunk_id,
                        title,
                        text,
                        category,
                        years,
                        year_ranges,
                        colles,
                        places,
                        keywords,
                        castells,
                        combined_emb.tolist(),
                    ),
                )
                if cur.rowcount:
                    inserted += 1
            except Exception as e:
                errors += 1
                print(f"\n⚠️  Error insert '{chunk_id[:48]}...': {e}")

        conn.commit()

    cur.execute("SELECT COUNT(*) FROM castellers_info_chunks;")
    actual_count = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"\n✅ Indexació finalitzada")
    print(f"   Files noves inserides (aquesta execució): {inserted}")
    print(f"   Errors: {errors}")
    print(f"   Files totals a la BD: {actual_count}")


def prune_revista_chunks_in_supabase(
    json_path: str = REVISTA_CHUNKS_JSON,
    dry_run: bool = False,
) -> int:
    """
    Delete from Supabase any chunk_id starting with 'revista_' that is no longer
    present in the given JSON file. The JSON is treated as the source of truth
    after the pruning rules in `revista_castells_to_chunks.py` have been applied.

    Returns the number of rows deleted (or that would be deleted in dry-run mode).
    """
    print(f"\n🧹 Pruning revista_* DB rows to match JSON: {json_path}")
    if not os.path.isfile(json_path):
        print(f"   ⚠️  Fitxer no trobat, s'omet: {json_path}")
        return 0

    chunks = load_json_chunks(json_path)
    valid_ids: Set[str] = {
        c["id"] for c in chunks
        if isinstance(c.get("id"), str) and c["id"].startswith("revista_")
    }
    print(f"   JSON revista_* chunks: {len(valid_ids)}")

    conn = get_supabase_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT chunk_id FROM castellers_info_chunks "
            "WHERE LEFT(chunk_id, 8) = 'revista_';"
        )
        db_ids: Set[str] = {r[0] for r in cur.fetchall() if r[0]}
        print(f"   DB   revista_* chunks: {len(db_ids)}")

        orphans = sorted(db_ids - valid_ids)
        print(f"   Orphans to remove:    {len(orphans)}")
        if orphans[:5]:
            print("   Sample:", ", ".join(orphans[:5]))

        if not orphans:
            cur.close()
            return 0

        if dry_run:
            print("   DRY RUN: not deleting anything.")
            cur.close()
            return len(orphans)

        # Use array predicate; psycopg2 adapts list -> text[]
        cur.execute(
            "DELETE FROM castellers_info_chunks "
            "WHERE LEFT(chunk_id, 8) = 'revista_' "
            "AND chunk_id = ANY(%s);",
            [orphans],
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        print(f"   ✅ Deleted {deleted} rows.")
        return deleted
    finally:
        conn.close()


def test_search():
    """Test de cerca per verificar que funciona correctament"""
    # Imported here so the indexer doesn't take a hard dependency on the
    # query-time RAG pool unless the test path actually runs.
    from xiquet.rag import search_castellers_info

    print("\n" + "="*60)
    print("🔍 Testing search functionality...")
    print("="*60)
    
    test_queries = [
        "Què són els castells?",
        "Història dels castells al segle XIX",
        "Concurs de Tarragona",
        "Margeners de Guissona",  # Test colla search
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        print("-" * 40)
        
        results = search_castellers_info(query, k=3)
        
        for i, (doc, score) in enumerate(results):
            print(f"  {i+1}. [{score:.3f}] {doc['meta']['title']}")
            print(f"     Category: {doc['meta']['category']}")
            print(f"     Text preview: {doc['text'][:100]}...")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indexa castellers + revista a castellers_info_chunks (OpenAI embeddings)."
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Elimina la taula castellers_info_chunks i torna a crear-la; re-embedeix tots els chunks dels dos JSON.",
    )
    parser.add_argument(
        "--skip-test-search",
        action="store_true",
        help="No executar la cerca de prova al final.",
    )
    parser.add_argument(
        "--castellers-json",
        default=CASTELLERS_CHUNKS_JSON,
        help="Ruta al castellers_info_chunks.json",
    )
    parser.add_argument(
        "--revista-json",
        default=REVISTA_CHUNKS_JSON,
        help="Ruta al revista_castells_scraper.json",
    )
    parser.add_argument(
        "--prune-revista-from-db",
        action="store_true",
        help=(
            "Elimina de la BD els chunks revista_* que ja no apareixen al JSON "
            "(ideal després d'executar revista_castells_to_chunks.py amb pruning)."
        ),
    )
    parser.add_argument(
        "--prune-only",
        action="store_true",
        help="Només executa la neteja de revista_* a la BD, sense indexar.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra què s'esborraria a --prune-revista-from-db sense fer canvis.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🏰 Castellers Info Chunks - Embedding Indexer")
    print("=" * 60)
    print("\n📊 Configuration:")
    print(f"   Model: {EMBEDDING_MODEL}")
    print(f"   Embedding dimensions: {EMBEDDING_DIM}")
    print(f"   Weights: title={TITLE_WEIGHT}, text={TEXT_WEIGHT}")
    print(f"   Castellers JSON: {args.castellers_json}")
    print(f"   Revista JSON: {args.revista_json}")

    if not DATABASE_URL:
        print("\n❌ DATABASE_URL not set in .env file")
        return

    try:
        if not args.prune_only:
            chunks = load_all_embedding_chunks(args.castellers_json, args.revista_json)
            index_chunks_to_supabase(chunks, rebuild=args.rebuild)

        if args.prune_revista_from_db or args.prune_only:
            prune_revista_chunks_in_supabase(
                json_path=args.revista_json, dry_run=args.dry_run
            )

        if not args.prune_only and not args.skip_test_search:
            test_search()
        print("\n" + "=" * 60)
        print("✅ Fet. Taula 'castellers_info_chunks' a punt.")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()

