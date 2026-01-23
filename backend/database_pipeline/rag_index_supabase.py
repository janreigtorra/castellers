#!/usr/bin/env python3
"""
rag_index_supabase.py
Genera embeddings i els emmagatzema a Supabase amb pgvector.
Llegeix dades des de Supabase PostgreSQL i crea un index vectorial.
"""

import os
import json
import psycopg2
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
import numpy as np
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIGURACIÓ ----------
DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_NAME = "all-MiniLM-L6-v2"   # equilibrat i ràpid
CHUNK_SIZE_WORDS = 200            # paraules per chunk
OVERLAP_WORDS = 50                # solapament entre chunks
BATCH_SIZE = 256                  # per generar embeddings en batches
# ------------------------------------

# ---------- MODEL CACHING ----------
# Cache the SentenceTransformer model globally to avoid reloading on every request
_cached_model = None
_cached_model_name = None

def get_cached_model(model_name: str = MODEL_NAME) -> SentenceTransformer:
    """Get cached SentenceTransformer model or load it if not cached"""
    global _cached_model, _cached_model_name
    
    if _cached_model is None or _cached_model_name != model_name:
        from datetime import datetime
        model_load_start = datetime.now()
        _cached_model = SentenceTransformer(model_name)
        _cached_model_name = model_name
        model_load_time = (datetime.now() - model_load_start).total_seconds() * 1000
        print(f"[TIMING] RAG SentenceTransformer model load: {model_load_time:.2f}ms (first load)")
    
    return _cached_model

def preload_rag_model(model_name: str = MODEL_NAME):
    """
    Pre-load the RAG model at startup to avoid delay on first request.
    Call this during application startup.
    """
    print(f"[RAG] Pre-loading SentenceTransformer model: {model_name}")
    get_cached_model(model_name)
    print(f"[RAG] Model pre-loaded and cached")
# ------------------------------------

# ---------- UTILS DE TEXT ----------
def words_split(text: str) -> List[str]:
    return text.replace("\n", " ").split()

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS, overlap: int = OVERLAP_WORDS) -> List[str]:
    """
    Divideix text en chunks aproximadament de chunk_size paraules amb overlap.
    Retorna llista de strings.
    """
    if not text:
        return []
    words = words_split(text)
    if len(words) <= chunk_size:
        return [" ".join(words)]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end == len(words):
            break
        start = end - overlap
    return chunks

# ---------- CONNEXIÓ A SUPABASE ----------
def get_supabase_connection():
    """Obté una connexió a Supabase"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not set in .env file")
    return psycopg2.connect(DATABASE_URL)

def get_pooled_connection():
    """Get a connection from the shared pool (faster for repeated queries)"""
    try:
        from joc_del_mocador.db_pool import get_db_connection
        return get_db_connection()
    except ImportError:
        # Fallback to direct connection if pool not available
        return get_supabase_connection()

def enable_pgvector(conn):
    """Habilita l'extensió pgvector si no està habilitada"""
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        print("pgvector extension enabled")
    except Exception as e:
        print(f"Warning: Could not enable pgvector: {e}")
    finally:
        cur.close()

def create_embeddings_table(conn):
    """Crea la taula per emmagatzemar embeddings"""
    cur = conn.cursor()
    
    # Crear taula embeddings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id SERIAL PRIMARY KEY,
            chunk_text TEXT NOT NULL,
            embedding vector(384),  -- all-MiniLM-L6-v2 dimensions
            source_table TEXT,
            source_pk INTEGER,
            colla_fk INTEGER,
            colla_name TEXT,
            colla_id TEXT,
            event_id TEXT,
            event_name TEXT,
            date TEXT,
            place TEXT,
            city TEXT,
            category TEXT,
            chunk_index INTEGER,
            chunk_length_words INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (colla_fk) REFERENCES colles(id) ON DELETE CASCADE
        );
    """)
    
    # Crear índex per cerca vectorial
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_vector 
        ON embeddings USING ivfflat (embedding vector_cosine_ops) 
        WITH (lists = 100);
    """)
    
    # Crear altres índexos útils
    cur.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_source_table ON embeddings(source_table);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_colla_fk ON embeddings(colla_fk);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_date ON embeddings(date);")
    
    conn.commit()
    cur.close()
    print("Embeddings table created")

# ---------- EXTRACCIÓ DE DOCUMENTS DES DE SUPABASE ----------
def gather_documents_from_supabase() -> List[Dict[str, Any]]:
    """
    Extreu documents a indexar des de Supabase i els transforma en dicts.
    """
    docs = []
    conn = get_supabase_connection()
    cur = conn.cursor()

    # 1) colles_wiki_texts + colla info
    try:
        cur.execute("""
            SELECT cwt.id, cwt.colla_fk, cwt.text, c.name, c.colla_id
            FROM colles_wiki_texts cwt
            JOIN colles c ON c.id = cwt.colla_fk
        """)
        rows = cur.fetchall()
        for r in rows:
            pid, colla_fk, text, colla_name, colla_id = r
            docs.append({
                "source_table": "colles_wiki_texts",
                "pk": pid,
                "colla_fk": colla_fk,
                "colla_name": colla_name or "",
                "colla_id": colla_id or "",
                "text": text or ""
            })
    except psycopg2.OperationalError:
        pass

    # 2) colles_wiki_info + colla info
    try:
        cur.execute("""
            SELECT cwi.id, cwi.colla_fk, cwi.key, cwi.value, c.name, c.colla_id
            FROM colles_wiki_info cwi
            JOIN colles c ON c.id = cwi.colla_fk
        """)
        rows = cur.fetchall()
        for r in rows:
            pid, colla_fk, key, value, colla_name, colla_id = r
            docs.append({
                "source_table": "colles_wiki_info",
                "pk": pid,
                "colla_fk": colla_fk,
                "colla_name": colla_name or "",
                "colla_id": colla_id or "",
                "text": f"{key}: {value}"
            })
    except psycopg2.OperationalError:
        pass

    # 3) colles_best_actuacions + colla info
    try:
        cur.execute("""
            SELECT cba.id, cba.colla_fk, cba.rank, cba.date, cba.location, cba.diada, cba.actuacio, cba.points, c.name, c.colla_id
            FROM colles_best_actuacions cba
            JOIN colles c ON c.id = cba.colla_fk
        """)
        rows = cur.fetchall()
        for r in rows:
            pid, colla_fk, rank, date, location, diada, actuacio, points, colla_name, colla_id = r
            txt = f"Actuació (rank {rank}) - {date} - {location} - {diada}. Actuació: {actuacio}. Punts: {points}"
            docs.append({
                "source_table": "colles_best_actuacions",
                "pk": pid,
                "colla_fk": colla_fk,
                "colla_name": colla_name or "",
                "colla_id": colla_id or "",
                "date": date or "",
                "location": location or "",
                "diada": diada or "",
                "text": txt
            })
    except psycopg2.OperationalError:
        pass

    # 4) events + castells + colla info
    try:
        cur.execute("""
            SELECT e.id, e.event_id, e.name, e.date, e.place, e.city, ec.id as event_colles_id, ec.colla_fk, c.name, c.colla_id
            FROM events e
            JOIN event_colles ec ON ec.event_fk = e.id
            JOIN colles c ON c.id = ec.colla_fk
        """)
        rows = cur.fetchall()
        for r in rows:
            e_id, event_id, name, date, place, city, event_colles_id, colla_fk, colla_name, colla_id = r
            # recuperar castells per event_colles_id
            cur.execute("SELECT castell_name, status, raw_text FROM castells WHERE event_colla_fk = %s", (event_colles_id,))
            cast_rows = cur.fetchall()
            castells_txt = "; ".join([f"{cr[0]} ({cr[1]})" if cr[0] else (cr[2] or "") for cr in cast_rows])
            txt = f"{date} - {name} - {place or ''} {city or ''}. Castells: {castells_txt}"
            docs.append({
                "source_table": "events_castells",
                "pk": event_colles_id,
                "event_id": event_id,
                "event_name": name or "",
                "colla_fk": colla_fk,
                "colla_name": colla_name or "",
                "colla_id": colla_id or "",
                "date": date or "",
                "place": place or "",
                "city": city or "",
                "text": txt
            })
    except psycopg2.OperationalError:
        pass

    # 5) general_info
    try:
        cur.execute("SELECT id, line_number, text, category FROM general_info")
        rows = cur.fetchall()
        for r in rows:
            pid, line_number, text, category = r
            docs.append({
                "source_table": "general_info",
                "pk": pid,
                "line_number": line_number,
                "category": category or "",
                "text": text or ""
            })
    except psycopg2.OperationalError:
        pass

    # 6) concurs paragraphs
    try:
        cur.execute("""
            SELECT id, edition, title, date, colla_guanyadora, num_colles, 
                   castells_intentats, maxim_castell, plaça, paragraphs_json
            FROM concurs
            WHERE paragraphs_json IS NOT NULL AND paragraphs_json != ''
        """)
        rows = cur.fetchall()
        for r in rows:
            pid, edition, title, date, colla_guanyadora, num_colles, castells_intentats, maxim_castell, plaça, paragraphs_json = r
            try:
                paragraphs = json.loads(paragraphs_json)
                if isinstance(paragraphs, list):
                    for para_idx, para_dict in enumerate(paragraphs):
                        if isinstance(para_dict, dict):
                            for info_key, info_text in para_dict.items():
                                if isinstance(info_text, str) and len(words_split(info_text)) >= 15:
                                    docs.append({
                                        "source_table": "concurs_paragraphs",
                                        "pk": pid,
                                        "concurs_edition": edition or "",
                                        "concurs_title": title or "",
                                        "concurs_date": date or "",
                                        "concurs_colla_guanyadora": colla_guanyadora or "",
                                        "concurs_num_colles": num_colles,
                                        "concurs_castells_intentats": castells_intentats,
                                        "concurs_maxim_castell": maxim_castell or "",
                                        "concurs_plaça": plaça or "",
                                        "paragraph_index": para_idx,
                                        "info_key": info_key,
                                        "text": info_text
                                    })
                elif isinstance(paragraphs, dict):
                    for para_key, para_data in paragraphs.items():
                        if isinstance(para_data, dict):
                            for info_key, info_text in para_data.items():
                                if isinstance(info_text, str) and len(words_split(info_text)) >= 15:
                                    docs.append({
                                        "source_table": "concurs_paragraphs",
                                        "pk": pid,
                                        "concurs_edition": edition or "",
                                        "concurs_title": title or "",
                                        "concurs_date": date or "",
                                        "concurs_colla_guanyadora": colla_guanyadora or "",
                                        "concurs_num_colles": num_colles,
                                        "concurs_castells_intentats": castells_intentats,
                                        "concurs_maxim_castell": maxim_castell or "",
                                        "concurs_plaça": plaça or "",
                                        "paragraph_key": para_key,
                                        "info_key": info_key,
                                        "text": info_text
                                    })
                        elif isinstance(para_data, str) and len(words_split(para_data)) >= 15:
                            docs.append({
                                "source_table": "concurs_paragraphs",
                                "pk": pid,
                                "concurs_edition": edition or "",
                                "concurs_title": title or "",
                                "concurs_date": date or "",
                                "concurs_colla_guanyadora": colla_guanyadora or "",
                                "concurs_num_colles": num_colles,
                                "concurs_castells_intentats": castells_intentats,
                                "concurs_maxim_castell": maxim_castell or "",
                                "concurs_plaça": plaça or "",
                                "paragraph_key": para_key,
                                "info_key": "",
                                "text": para_data
                            })
            except (json.JSONDecodeError, TypeError):
                continue
    except psycopg2.OperationalError:
        pass

    conn.close()
    return docs

# ---------- INDEXACIÓ A SUPABASE ----------
def index_documents_to_supabase(docs: List[Dict[str, Any]], model_name: str = MODEL_NAME):
    """Indexa documents a Supabase amb pgvector"""
    
    # Configurar connexió
    conn = get_supabase_connection()
    enable_pgvector(conn)
    create_embeddings_table(conn)
    
    # Carregar model
    print("Carregant model d'embeddings:", model_name)
    model = SentenceTransformer(model_name)
    
    # Preparar chunks
    doc_texts = []
    doc_meta = []
    
    for doc in docs:
        text = doc.get("text") or ""
        chunks = chunk_text(text, CHUNK_SIZE_WORDS, OVERLAP_WORDS)
        for i, chunk in enumerate(chunks):
            meta = dict(doc)
            meta["chunk_index"] = i
            meta["chunk_length_words"] = len(words_split(chunk))
            doc_texts.append(chunk)
            doc_meta.append(meta)
    
    print(f"Total chunks a indexar: {len(doc_texts)}")
    if not doc_texts:
        print("No s'han trobat documents per indexar.")
        return
    
    # Netejar embeddings existents
    cur = conn.cursor()
    cur.execute("DELETE FROM embeddings")
    conn.commit()
    print("Existing embeddings cleared")
    
    # Generar i emmagatzemar embeddings en batches
    for i in tqdm(range(0, len(doc_texts), BATCH_SIZE), desc="Processing batches"):
        batch_texts = doc_texts[i:i+BATCH_SIZE]
        batch_meta = doc_meta[i:i+BATCH_SIZE]
        
        # Generar embeddings
        embeddings = model.encode(batch_texts, show_progress_bar=False, convert_to_numpy=True)
        embeddings = embeddings.astype("float32")
        
        # Normalitzar per cosinus similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0.0] = 1e-9
        embeddings = embeddings / norms
        
        # Inserir a Supabase
        for j, (text, meta, embedding) in enumerate(zip(batch_texts, batch_meta, embeddings)):
            try:
                cur.execute("""
                    INSERT INTO embeddings (
                        chunk_text, embedding, source_table, source_pk, colla_fk, 
                        colla_name, colla_id, event_id, event_name, date, place, city, 
                        category, chunk_index, chunk_length_words
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    text,
                    embedding.tolist(),  # Convert to list for PostgreSQL
                    meta.get("source_table"),
                    meta.get("pk"),
                    meta.get("colla_fk"),
                    meta.get("colla_name"),
                    meta.get("colla_id"),
                    meta.get("event_id"),
                    meta.get("event_name"),
                    meta.get("date"),
                    meta.get("place"),
                    meta.get("city"),
                    meta.get("category"),
                    meta.get("chunk_index"),
                    meta.get("chunk_length_words")
                ))
            except Exception as e:
                print(f"Error inserting chunk {i+j}: {e}")
                continue
        
        # Commit batch
        conn.commit()
    
    cur.close()
    conn.close()
    print("Embeddings indexed to Supabase successfully!")

# ---------- CERCA VECTORIAL ----------
def search_query_supabase(query: str, k: int = 5, model_name: str = MODEL_NAME) -> List[Tuple[Dict, float]]:
    """
    Cerca vectorial a Supabase amb pgvector.
    Retorna una llista de tuples (doc_info, score) on doc_info té format {"meta": {...}, "text": "..."}
    Compatible amb el format esperat per agent.py
    """
    from datetime import datetime
    
    # Get cached model (or load if first time)
    model = get_cached_model(model_name)
    
    # Generate query embedding
    embed_start = datetime.now()
    q_emb = model.encode([query], convert_to_numpy=True).astype("float32")
    q_emb = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)
    embed_time = (datetime.now() - embed_start).total_seconds() * 1000
    print(f"[TIMING] RAG query embedding generation: {embed_time:.2f}ms")
    
    # Try to use connection pool for faster connections
    conn_start = datetime.now()
    use_pool = False
    try:
        from joc_del_mocador.db_pool import get_db_connection
        use_pool = True
    except ImportError:
        pass
    
    if use_pool:
        # Use pooled connection (context manager handles return to pool)
        with get_db_connection() as conn:
            conn_time = (datetime.now() - conn_start).total_seconds() * 1000
            if conn_time > 10:
                print(f"[TIMING] RAG database connection (pooled): {conn_time:.2f}ms")
            return _execute_rag_search(conn, q_emb, k)
    else:
        # Fallback to direct connection
        conn = get_supabase_connection()
        conn_time = (datetime.now() - conn_start).total_seconds() * 1000
        if conn_time > 10:
            print(f"[TIMING] RAG database connection: {conn_time:.2f}ms")
        try:
            return _execute_rag_search(conn, q_emb, k)
        finally:
            conn.close()

def _execute_rag_search(conn, q_emb, k: int) -> List[Tuple[Dict, float]]:
    """Execute the actual RAG search query"""
    from datetime import datetime
    
    cur = conn.cursor()
    
    try:
        # Native pgvector search - only fetches top k results
        # Cast the query embedding array to vector type for pgvector operator
        db_search_start = datetime.now()
        
        # Convert embedding to list for psycopg2
        query_embedding_list = q_emb[0].tolist()
        
        # Check which column exists and use appropriate query
        # First, get ALL columns to see what we're working with
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'embeddings'
            ORDER BY column_name
        """)
        all_columns = {row[0] for row in cur.fetchall()}
        
        # Check for specific columns we need
        embedding_col = 'embedding' if 'embedding' in all_columns else ('vector' if 'vector' in all_columns else None)
        text_col = 'chunk_text' if 'chunk_text' in all_columns else ('text' if 'text' in all_columns else None)
        pk_col = 'source_pk' if 'source_pk' in all_columns else ('pk' if 'pk' in all_columns else None)
        
        if not embedding_col:
            raise Exception(f"No embedding column found. Available columns: {sorted(all_columns)}")
        if not text_col:
            raise Exception(f"No text column found. Available columns: {sorted(all_columns)}")
        
        print(f"[RAG] Using columns: embedding={embedding_col}, text={text_col}, pk={pk_col}")
        print(f"[RAG] All available columns: {sorted(all_columns)}")
        
        # Try native pgvector search first
        try:
            # Build query with proper column names
            # Use vector() constructor to convert array to vector type
            # pgvector accepts arrays and can convert them to vector
            # Handle optional pk column
            pk_select = f"{pk_col} as source_pk" if pk_col else "NULL as source_pk"
            
            query_sql = f"""
                SELECT 
                    {text_col} as chunk_text,
                    source_table, 
                    {pk_select}, 
                    colla_fk, 
                    colla_name, colla_id, event_id, event_name, date, place, city, 
                    category, chunk_index, chunk_length_words,
                    1 - ({embedding_col} <=> %s::vector) as similarity_score
                FROM embeddings 
                WHERE {embedding_col} IS NOT NULL
                ORDER BY {embedding_col} <=> %s::vector 
                LIMIT %s
            """
            
            # Pass the embedding as a string representation that pgvector understands
            # Format: '[0.1,0.2,0.3]' which PostgreSQL can cast to vector
            embedding_str = '[' + ','.join(str(x) for x in query_embedding_list) + ']'
            cur.execute(query_sql, (embedding_str, embedding_str, k))
            rows = cur.fetchall()
            db_search_time = (datetime.now() - db_search_start).total_seconds() * 1000
            print(f"[TIMING] RAG database search (pgvector native): {db_search_time:.2f}ms (rows: {len(rows)})")
            
        except Exception as vector_error:
            # Rollback the failed transaction before trying again
            conn.rollback()
            
            # Fallback: if vector search fails, check if embeddings are stored as JSON/text
            print(f"[RAG] Vector search failed: {vector_error}")
            print(f"[RAG] Falling back to check embedding storage format...")
            
            # Check the actual data type of the embedding column
            try:
                cur.execute("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'embeddings' 
                    AND column_name = %s
                """, (embedding_col,))
                col_info = cur.fetchone()
                
                if col_info:
                    col_type = col_info[0]
                    print(f"[RAG] Embedding column type: {col_type}")
                    
                    # If it's not vector type, we need to use the old method (fetch all and compute in Python)
                    # But for now, let's try to use the old rag_index.py approach
                    raise Exception(f"Embedding column is {col_type}, not vector type. Please ensure embeddings are stored as vector type or use the old search method.")
                else:
                    raise vector_error
            except Exception as e:
                raise vector_error
        
        # Format results to match expected format (doc_info with meta and text)
        results = []
        for row in rows:
            chunk_text, source_table, source_pk, colla_fk, colla_name, colla_id, event_id, event_name, date, place, city, category, chunk_index, chunk_length_words, similarity_score = row
            
            meta = {
                "source_table": source_table,
                "pk": source_pk,
                "colla_fk": colla_fk,
                "colla_name": colla_name,
                "colla_id": colla_id,
                "event_id": event_id,
                "event_name": event_name,
                "date": date,
                "place": place,
                "city": city,
                "category": category,
                "chunk_index": chunk_index,
                "chunk_length_words": chunk_length_words
            }
            
            # Format to match what agent.py expects: (doc_info, score)
            # where doc_info = {"meta": {...}, "text": "..."}
            doc_info = {
                "meta": meta,
                "text": chunk_text
            }
            
            results.append((doc_info, float(similarity_score)))
        
        return results
        
    except Exception as e:
        print(f"Error searching embeddings: {e}")
        return []
    finally:
        cur.close()
        # Note: Don't close conn here - caller handles it (pool returns, or direct closes)

# ---------- MAIN ----------
def main():
    print("Creating Supabase Vector Index")
    print("=" * 40)
    
    if not DATABASE_URL:
        print("DATABASE_URL not set in .env file")
        return
    
    try:
        print("Extracting documents from Supabase...")
        docs = gather_documents_from_supabase()
        print(f"Found {len(docs)} documents")
        
        print("Indexing documents to Supabase...")
        index_documents_to_supabase(docs, model_name=MODEL_NAME)
        
        print("\nVector index created successfully!")
        print("You can now use search_query_supabase(query, k) for vector search.")
        
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    main()
