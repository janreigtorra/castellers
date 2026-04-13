#!/usr/bin/env python3
"""
load_castellers_info_chunks.py
Carrega els chunks des de:
  - data_basic/data_to_embed/castellers_info_chunks.json
  - data_basic/data_to_embed/revista_castells_scraper.json
a la mateixa taula Supabase amb embeddings optimitzats.

Utilitza:
- OpenAI text-embedding-3-small (dimensions configurables, veure EMBEDDING_DIM)
- Embeddings combinats: 0.2 * title + 0.8 * text (ponderat)
- Per defecte només indexa chunks nous (chunk_id = camp "id" del JSON). Usa --rebuild per recrear la taula i reincrustar-ho tot.
"""

import argparse
import os
import json
import re
import threading
import psycopg2
from psycopg2 import pool as pg_pool
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
# IVFFlat index is built with lists=100; lower probes = faster search, slightly lower recall (tune via env)
try:
    RAG_IVFFLAT_PROBES = max(1, min(100, int(os.getenv("RAG_IVFFLAT_PROBES", "25"))))
except ValueError:
    RAG_IVFFLAT_PROBES = 25
try:
    RAG_DB_POOL_MIN = max(1, int(os.getenv("RAG_DB_POOL_MIN", "1")))
    RAG_DB_POOL_MAX = max(RAG_DB_POOL_MIN, int(os.getenv("RAG_DB_POOL_MAX", "8")))
except ValueError:
    RAG_DB_POOL_MIN, RAG_DB_POOL_MAX = 1, 8
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

def get_embeddings_batch(texts: List[str]) -> np.ndarray:
    """Get embeddings for a batch of texts using OpenAI API"""
    client = get_openai_client()
    
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIM
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
        input=[text],
        dimensions=EMBEDDING_DIM
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


_rag_search_pool: Optional[pg_pool.ThreadedConnectionPool] = None
_rag_search_pool_lock = threading.Lock()


def _get_rag_search_pool() -> pg_pool.ThreadedConnectionPool:
    """Lazy pool for RAG vector search only (indexing scripts use get_supabase_connection)."""
    global _rag_search_pool
    if _rag_search_pool is not None:
        return _rag_search_pool
    with _rag_search_pool_lock:
        if _rag_search_pool is not None:
            return _rag_search_pool
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL not set in .env file")
        _rag_search_pool = pg_pool.ThreadedConnectionPool(
            RAG_DB_POOL_MIN,
            RAG_DB_POOL_MAX,
            dsn=DATABASE_URL,
            connect_timeout=10,
        )
        return _rag_search_pool


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


def _create_castellers_info_chunks_indexes(cur) -> None:
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cic_combined_embedding
        ON castellers_info_chunks
        USING ivfflat (combined_embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cic_title_embedding
        ON castellers_info_chunks
        USING ivfflat (title_embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cic_text_embedding
        ON castellers_info_chunks
        USING ivfflat (text_embedding vector_cosine_ops)
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


def _create_castellers_info_chunks_table(cur) -> None:
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
            title_embedding vector({EMBEDDING_DIM}),
            text_embedding vector({EMBEDDING_DIM}),
            combined_embedding vector({EMBEDDING_DIM}),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    )
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


def create_weighted_embedding(
    title: str,
    text: str,
    title_weight: float = TITLE_WEIGHT,
    text_weight: float = TEXT_WEIGHT
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Crea embeddings per title, text i la combinació ponderada using OpenAI.
    
    Returns:
        Tuple of (title_embedding, text_embedding, combined_embedding)
    """
    # Get embeddings for both texts in one batch (more efficient)
    embeddings = get_embeddings_batch([title, text])
    title_emb = embeddings[0]
    text_emb = embeddings[1]
    
    # Create weighted combination
    combined_emb = title_weight * title_emb + text_weight * text_emb
    
    # Normalize combined embedding (individual ones already normalized)
    combined_emb = combined_emb / np.linalg.norm(combined_emb)
    
    return title_emb, text_emb, combined_emb


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

        try:
            embs = get_embeddings_batch(flat_inputs)
        except Exception as e:
            errors += len(batch)
            print(f"\n⚠️  Error API embeddings (batch starting {i}): {e}")
            continue

        for j, chunk in enumerate(batch):
            title_emb = embs[2 * j]
            text_emb = embs[2 * j + 1]
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
                        title_embedding, text_embedding, combined_embedding
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s
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
                        title_emb.tolist(),
                        text_emb.tolist(),
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


def search_castellers_info(
    query: str,
    k: int = 50
) -> List[Tuple[Dict, float]]:
    """
    Cerca semàntica a la taula castellers_info_chunks using OpenAI embeddings.
    Returns top k results with all metadata for reranking.
    
    Args:
        query: Text de cerca
        k: Nombre de resultats (default 50 for reranking)
    
    Returns:
        Lista de tuples (doc_info, similarity_score)
    """
    from datetime import datetime
    
    print(f"[RAG Search] Starting search for: {query[:50]}...", flush=True)
    
    # Generate query embedding with OpenAI
    print(f"[RAG Search] Generating embedding with OpenAI...", flush=True)
    embed_start = datetime.now()
    q_emb = get_embedding_single(query)
    embed_time = (datetime.now() - embed_start).total_seconds() * 1000
    print(f"[TIMING] Query embedding (OpenAI API): {embed_time:.2f}ms", flush=True)
    
    conn = None
    cur = None
    pool_obj = None
    conn_start = datetime.now()
    try:
        print(f"[RAG Search] Step 3: Acquiring pooled DB connection...", flush=True)
        pool_obj = _get_rag_search_pool()
        conn = pool_obj.getconn()
        conn_time = (datetime.now() - conn_start).total_seconds() * 1000
        host = urlparse(DATABASE_URL).hostname if DATABASE_URL else "?"
        print(f"[RAG Search] Pooled connection in {conn_time:.2f}ms ({host})", flush=True)
        cur = conn.cursor()
        
        # Format embedding for pgvector
        embedding_str = '[' + ','.join(str(x) for x in q_emb.tolist()) + ']'
        
        # IVFFlat: lists=100 on index; probes trades speed vs recall (see RAG_IVFFLAT_PROBES)
        cur.execute(f"SET ivfflat.probes = {RAG_IVFFLAT_PROBES};")
        
        # Execute search query - get all metadata for reranking
        db_start = datetime.now()
        cur.execute("""
            SELECT 
                chunk_id, title, text, category,
                years, year_ranges, colles, places, keywords, castells,
                1 - (combined_embedding <=> %s::vector) as similarity
            FROM castellers_info_chunks
            ORDER BY combined_embedding <=> %s::vector
            LIMIT %s
        """, [embedding_str, embedding_str, k])
        
        rows = cur.fetchall()
        db_time = (datetime.now() - db_start).total_seconds() * 1000
        print(f"[TIMING] DB search: {db_time:.2f}ms ({len(rows)} results)")
        
        # Format results
        results = []
        for row in rows:
            (chunk_id, title, text, category, 
             years, year_ranges, colles, places, keywords, castells,
             similarity) = row
            
            doc_info = {
                "meta": {
                    "chunk_id": chunk_id,
                    "title": title,
                    "category": category,
                    "years": years or [],
                    "year_ranges": year_ranges or [],
                    "colles": colles or [],
                    "places": places or [],
                    "keywords": keywords or [],
                    "castells": castells or []
                },
                "text": text
            }
            
            results.append((doc_info, float(similarity)))
        
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


def test_search():
    """Test de cerca per verificar que funciona correctament"""
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
        chunks = load_all_embedding_chunks(args.castellers_json, args.revista_json)
        index_chunks_to_supabase(chunks, rebuild=args.rebuild)
        if not args.skip_test_search:
            test_search()
        print("\n" + "=" * 60)
        print("✅ Fet. Taula 'castellers_info_chunks' a punt.")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()

