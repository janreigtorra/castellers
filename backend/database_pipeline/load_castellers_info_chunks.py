#!/usr/bin/env python3
"""
load_castellers_info_chunks.py
Carrega els chunks de castellers_info_chunks.json a Supabase amb embeddings optimitzats.

Utilitza:
- OpenAI text-embedding-3-small (512 dimensions) - lightweight, no local model needed
- Embeddings combinats: 0.2 * title + 0.8 * text (ponderat)
- Taula dedicada amb estructura optimitzada per cerca híbrida
"""

import os
import json
import psycopg2
from typing import List, Dict, Any, Tuple
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
EMBEDDING_DIM = 512  # Reduced dimensions for faster search
TITLE_WEIGHT = 0.2
TEXT_WEIGHT = 0.8
BATCH_SIZE = 64  # Smaller batches for stability
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data_basic", "castellers_info_chunks.json")

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


def create_castellers_info_chunks_table(conn):
    """
    Crea la taula dedicada per castellers_info_chunks amb estructura optimitzada.
    Inclou columnes per metadata i embeddings.
    """
    cur = conn.cursor()
    
    # Drop existing table if exists (clean slate)
    cur.execute("DROP TABLE IF EXISTS castellers_info_chunks CASCADE;")
    print("✓ Dropped existing castellers_info_chunks table (if any)")
    
    # Create dedicated table matching JSON structure
    cur.execute(f"""
        CREATE TABLE castellers_info_chunks (
            -- Primary key from JSON
            chunk_id TEXT PRIMARY KEY,
            
            -- Core content
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            category TEXT NOT NULL,
            
            -- Arrays for filtering (stored as PostgreSQL arrays)
            years INTEGER[],
            year_ranges TEXT[],
            colles TEXT[],
            places TEXT[],
            keywords TEXT[],
            castells TEXT[],
            
            -- Embeddings (384 dimensions for multilingual MiniLM)
            title_embedding vector({EMBEDDING_DIM}),
            text_embedding vector({EMBEDDING_DIM}),
            combined_embedding vector({EMBEDDING_DIM}),
            
            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print(f"✓ Created castellers_info_chunks table with vector({EMBEDDING_DIM})")
    
    # Create IVFFlat index for fast vector similarity search
    # Note: For small datasets (<1000 rows), lists=50 is reasonable
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cic_combined_embedding 
        ON castellers_info_chunks 
        USING ivfflat (combined_embedding vector_cosine_ops) 
        WITH (lists = 50);
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cic_title_embedding 
        ON castellers_info_chunks 
        USING ivfflat (title_embedding vector_cosine_ops) 
        WITH (lists = 50);
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cic_text_embedding 
        ON castellers_info_chunks 
        USING ivfflat (text_embedding vector_cosine_ops) 
        WITH (lists = 50);
    """)
    print("✓ Created IVFFlat indexes for vector search")
    
    # GIN indexes for array filtering (hybrid search)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cic_years ON castellers_info_chunks USING GIN (years);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cic_year_ranges ON castellers_info_chunks USING GIN (year_ranges);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cic_colles ON castellers_info_chunks USING GIN (colles);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cic_places ON castellers_info_chunks USING GIN (places);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cic_keywords ON castellers_info_chunks USING GIN (keywords);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cic_castells ON castellers_info_chunks USING GIN (castells);")
    print("✓ Created GIN indexes for array filtering")
    
    # B-tree index for category filtering
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cic_category ON castellers_info_chunks(category);")
    print("✓ Created B-tree index for category")
    
    conn.commit()
    cur.close()


def load_json_chunks(json_path: str) -> List[Dict[str, Any]]:
    """Carrega els chunks del fitxer JSON"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chunks = data.get("chunks", [])
    metadata = data.get("metadata", {})
    
    print(f"✓ Loaded {len(chunks)} chunks from JSON")
    print(f"  Source: {metadata.get('source', 'unknown')}")
    print(f"  Description: {metadata.get('description', 'N/A')}")
    
    return chunks


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


def index_chunks_to_supabase(chunks: List[Dict[str, Any]]):
    """
    Indexa els chunks a Supabase amb embeddings ponderats using OpenAI.
    """
    # Setup connection
    conn = get_supabase_connection()
    enable_pgvector(conn)
    create_castellers_info_chunks_table(conn)
    
    # Verify OpenAI API key
    print(f"\n📥 Using OpenAI embeddings: {EMBEDDING_MODEL}")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in .env file")
    print(f"✓ OpenAI configured (embedding dimension: {EMBEDDING_DIM})")
    
    cur = conn.cursor()
    
    # Process chunks in batches
    print(f"\n🔄 Processing {len(chunks)} chunks...")
    
    inserted = 0
    errors = 0
    chunk_counter = 0  # Use numeric ID to avoid duplicates
    
    for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc="Indexing batches"):
        batch = chunks[i:i+BATCH_SIZE]
        
        for chunk in batch:
            try:
                chunk_counter += 1
                chunk_id = str(chunk_counter)  # Simple numeric ID
                title = chunk.get("title", "")
                text = chunk.get("text", "")
                category = chunk.get("category", "")
                
                # Skip empty chunks (but still increment counter)
                if not text:
                    continue
                
                # Get arrays (use empty list if not present)
                years = chunk.get("years", []) or []
                year_ranges = chunk.get("year_ranges", []) or []
                colles = chunk.get("colles", []) or []
                places = chunk.get("places", []) or []
                keywords = chunk.get("keywords", []) or []
                castells = chunk.get("castells", []) or []
                
                # Generate embeddings with OpenAI
                title_emb, text_emb, combined_emb = create_weighted_embedding(
                    title, text, TITLE_WEIGHT, TEXT_WEIGHT
                )
                
                # Insert into database (using numeric ID, no conflicts possible)
                cur.execute("""
                    INSERT INTO castellers_info_chunks (
                        chunk_id, title, text, category,
                        years, year_ranges, colles, places, keywords, castells,
                        title_embedding, text_embedding, combined_embedding
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s
                    )
                """, (
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
                    combined_emb.tolist()
                ))
                
                inserted += 1
                
            except Exception as e:
                errors += 1
                print(f"\n⚠️  Error inserting chunk #{chunk_counter} '{title[:30]}...': {e}")
                continue
        
        # Commit each batch
        conn.commit()
    
    # Verify actual count in database
    cur.execute("SELECT COUNT(*) FROM castellers_info_chunks;")
    actual_count = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    print(f"\n✅ Indexing complete!")
    print(f"   Inserted: {inserted} chunks")
    print(f"   Errors: {errors}")
    print(f"   🔍 Verified DB count: {actual_count} rows")
    
    if actual_count != inserted:
        print(f"   ⚠️  MISMATCH! Script counted {inserted} but DB has {actual_count}")


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
    
    # Connect to database
    print(f"[RAG Search] Step 3: Connecting to database...", flush=True)
    print(f"[RAG Search] DATABASE_URL: {DATABASE_URL[:50] if DATABASE_URL else 'None'}...", flush=True)
    conn_start = datetime.now()
    conn = get_supabase_connection()
    conn_time = (datetime.now() - conn_start).total_seconds() * 1000
    print(f"[RAG Search] Database connected in {conn_time:.2f}ms", flush=True)
    cur = conn.cursor()
    
    try:
        # Format embedding for pgvector
        embedding_str = '[' + ','.join(str(x) for x in q_emb.tolist()) + ']'
        
        # Set IVFFlat probes to search more clusters for better recall
        # With 314 chunks and 50 lists, we need high probes to find all relevant results
        # For small datasets, set probes = lists to get exact results
        cur.execute("SET ivfflat.probes = 50;")
        
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
        return []
    finally:
        cur.close()
        conn.close()


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


def main():
    print("="*60)
    print("🏰 Castellers Info Chunks - Embedding Indexer")
    print("="*60)
    print(f"\n📊 Configuration:")
    print(f"   Model: {EMBEDDING_MODEL}")
    print(f"   Embedding dimensions: {EMBEDDING_DIM}")
    print(f"   Weights: title={TITLE_WEIGHT}, text={TEXT_WEIGHT}")
    print(f"   JSON file: {JSON_FILE_PATH}")
    
    if not DATABASE_URL:
        print("\n❌ DATABASE_URL not set in .env file")
        return
    
    try:
        # Load chunks from JSON
        chunks = load_json_chunks(JSON_FILE_PATH)
        
        # Index to Supabase
        index_chunks_to_supabase(chunks)
        
        # Test search
        test_search()
        
        print("\n" + "="*60)
        print("✅ All done! Table 'castellers_info_chunks' ready for queries.")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()

