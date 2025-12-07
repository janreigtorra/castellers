"""
rag_index.py
Genera embeddings i els emmagatzema a Supabase PostgreSQL amb pgvector.

Aquest script llegeix documents de Supabase i crea embeddings que es guarden directament a la base de dades.
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
CHUNK_SIZE_WORDS = 200            # paraules per chunk (ajusta segons necessitats)
OVERLAP_WORDS = 50                # solapament entre chunks
BATCH_SIZE = 256                  # per generar embeddings en batches
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

# ---------- EXTRACCIÓ DE DOCUMENTS DES DE LA BD ----------
def gather_documents_from_supabase() -> List[Dict[str, Any]]:
    """
    Extreu documents a indexar des de diferents taules i els transforma en dicts:
    {
      "source_table": "...",
      "pk": 123,
      "colla_fk": ... (foreign key),
      "colla_name": "...", (nom de la colla)
      "colla_id": "...", (id original de la web)
      "event_id": ... (si aplica),
      "event_name": "...", (nom de l'event)
      "date": ...,
      "place": "...", (lloc de l'event)
      "city": "...", (ciutat de l'event)
      "diada": "...", (nom de la diada)
      "location": "...", (ubicació de l'actuació)
      "line_number": ... (per general_info),
      "category": "...", (categoria per general_info: history, technique, music, etc.)
      "text": "text a indexar"
    }
    """
    docs = []
    conn = psycopg2.connect(DATABASE_URL)
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
    except psycopg2.errors.UndefinedTable:
        # taula no existeix
        pass

    # 2) colles_wiki_info + colla info -> convertir key/value en text
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
    except psycopg2.errors.UndefinedTable:
        pass

    # 3) colles_best_actuacions + colla info -> cada actuació com a doc
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
    except psycopg2.errors.UndefinedTable:
        pass

    # 4) events + castells + colla info -> agrupar per event+colla i fer un text resum
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
    except psycopg2.errors.UndefinedTable:
        pass

    # 5) general_info -> informació general sobre castells (història, tècnica, etc.)
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
    except psycopg2.errors.UndefinedTable:
        pass

    # 6) concurs paragraphs -> extraure paràgrafs de cada edició de concurs
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
                    # Handle list of dictionaries structure
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
                    # Handle dictionary structure (fallback)
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
                # Skip invalid JSON
                continue
    except psycopg2.errors.UndefinedTable:
        pass

    conn.close()
    return docs

# ---------- FUNCIONS DE SUPABASE ----------
def enable_pgvector_extension():
    """Enable pgvector extension in Supabase"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        print("pgvector extension enabled")
    except Exception as e:
        print(f"Warning: Could not enable pgvector extension: {e}")
    finally:
        conn.close()

def create_embeddings_table():
    """Create embeddings table with vector column"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Create embeddings table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id SERIAL PRIMARY KEY,
                source_table TEXT,
                pk INTEGER,
                colla_fk INTEGER,
                colla_name TEXT,
                colla_id TEXT,
                event_id TEXT,
                event_name TEXT,
                date TEXT,
                place TEXT,
                city TEXT,
                diada TEXT,
                location TEXT,
                line_number INTEGER,
                category TEXT,
                chunk_index INTEGER,
                chunk_length_words INTEGER,
                text TEXT,
                vector vector(384),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create index for vector similarity search
        cur.execute("""
            CREATE INDEX IF NOT EXISTS embeddings_vector_idx 
            ON embeddings USING ivfflat (vector vector_cosine_ops) 
            WITH (lists = 100);
        """)
        
        conn.commit()
        print("Embeddings table created successfully")
    except Exception as e:
        print(f"Error creating embeddings table: {e}")
        conn.rollback()
    finally:
        conn.close()

def index_documents_to_supabase(docs: List[Dict[str, Any]], model_name: str = MODEL_NAME):
    """Index documents to Supabase using pgvector"""
    # Enable pgvector extension
    enable_pgvector_extension()
    
    # Create embeddings table
    create_embeddings_table()
    
    # Load model
    print("Loading embedding model:", model_name)
    model = SentenceTransformer(model_name)
    
    # Prepare lists for chunking
    doc_texts = []
    doc_meta = []
    
    # Divide each doc into chunks
    for doc in docs:
        text = doc.get("text") or ""
        chunks = chunk_text(text, CHUNK_SIZE_WORDS, OVERLAP_WORDS)
        for i, chunk in enumerate(chunks):
            meta = dict(doc)  # copy
            meta["chunk_index"] = i
            meta["chunk_length_words"] = len(words_split(chunk))
            doc_texts.append(chunk)
            doc_meta.append(meta)
    
    print(f"Total chunks to index: {len(doc_texts)}")
    if not doc_texts:
        print("No documents found to index. Exiting.")
        return
    
    # Generate embeddings in batches
    embeddings = []
    for i in tqdm(range(0, len(doc_texts), BATCH_SIZE), desc="Generating embeddings"):
        batch_texts = doc_texts[i:i+BATCH_SIZE]
        emb = model.encode(batch_texts, show_progress_bar=False, convert_to_numpy=True)
        embeddings.append(emb)
    embeddings = np.vstack(embeddings).astype("float32")
    
    # Normalize L2 for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0.0] = 1e-9
    embeddings = embeddings / norms
    
    # Insert embeddings into Supabase
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Clear existing embeddings
        cur.execute("DELETE FROM embeddings")
        print("Cleared existing embeddings")
        
        # Insert new embeddings in batches
        for i in tqdm(range(0, len(doc_texts), BATCH_SIZE), desc="Inserting to Supabase"):
            batch_texts = doc_texts[i:i+BATCH_SIZE]
            batch_meta = doc_meta[i:i+BATCH_SIZE]
            batch_embeddings = embeddings[i:i+BATCH_SIZE]
            
            for j, (text, meta, embedding) in enumerate(zip(batch_texts, batch_meta, batch_embeddings)):
                cur.execute("""
                    INSERT INTO embeddings (
                        source_table, pk, colla_fk, colla_name, colla_id,
                        event_id, event_name, date, place, city, diada, location,
                        line_number, category, chunk_index, chunk_length_words, text, vector
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
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
                    meta.get("diada"),
                    meta.get("location"),
                    meta.get("line_number"),
                    meta.get("category"),
                    meta.get("chunk_index"),
                    meta.get("chunk_length_words"),
                    text,
                    embedding.tolist()
                ))
            
            conn.commit()
        
        print(f"Successfully indexed {len(doc_texts)} chunks to Supabase")
        
    except Exception as e:
        print(f"Error inserting embeddings: {e}")
        conn.rollback()
    finally:
        conn.close()

def search_query_supabase(query: str, k: int = 5, model_name: str = MODEL_NAME) -> List[Tuple[Dict, float]]:
    """
    Search for similar documents in Supabase using cosine similarity.
    Returns a list of tuples (doc_meta, score)
    """
    import json
    import numpy as np
    from datetime import datetime
    
    # Load model
    model_load_start = datetime.now()
    model = SentenceTransformer(model_name)
    model_load_time = (datetime.now() - model_load_start).total_seconds() * 1000
    print(f"[TIMING] RAG SentenceTransformer model load: {model_load_time:.2f}ms")
    
    # Generate query embedding
    embed_start = datetime.now()
    q_emb = model.encode([query], convert_to_numpy=True).astype("float32")
    q_emb = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)
    embed_time = (datetime.now() - embed_start).total_seconds() * 1000
    print(f"[TIMING] RAG query embedding generation: {embed_time:.2f}ms")
    
    # Search in Supabase
    conn_start = datetime.now()
    conn = psycopg2.connect(DATABASE_URL)
    conn_time = (datetime.now() - conn_start).total_seconds() * 1000
    if conn_time > 10:
        print(f"[TIMING] RAG database connection: {conn_time:.2f}ms")
    
    cur = conn.cursor()
    
    try:
        # Get all embeddings and compute similarity in Python
        db_fetch_start = datetime.now()
        cur.execute("""
            SELECT 
                id, source_table, source_pk, colla_fk, colla_name, colla_id,
                event_id, event_name, date, place, city, category,
                chunk_index, chunk_length_words, chunk_text, embedding
            FROM embeddings
        """)
        
        rows = cur.fetchall()
        db_fetch_time = (datetime.now() - db_fetch_start).total_seconds() * 1000
        print(f"[TIMING] RAG database fetch (all embeddings): {db_fetch_time:.2f}ms (rows: {len(rows)})")
        
        # Compute similarity
        similarity_start = datetime.now()
        results = []
        
        for row in rows:
            (id, source_table, source_pk, colla_fk, colla_name, colla_id,
             event_id, event_name, date, place, city, category,
             chunk_index, chunk_length_words, chunk_text, embedding_str) = row
            
            # Parse embedding from JSON string
            try:
                doc_embedding = np.array(json.loads(embedding_str), dtype=np.float32)
                doc_embedding = doc_embedding / np.linalg.norm(doc_embedding)
                
                # Compute cosine similarity
                similarity = np.dot(q_emb[0], doc_embedding)
                
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
                
                doc_info = {
                    "meta": meta,
                    "text": chunk_text
                }
                
                results.append((doc_info, float(similarity)))
                
            except (json.JSONDecodeError, ValueError) as e:
                # Skip invalid embeddings
                continue
        
        similarity_time = (datetime.now() - similarity_start).total_seconds() * 1000
        print(f"[TIMING] RAG similarity computation (Python loop): {similarity_time:.2f}ms")
        
        # Sort by similarity and return top k
        sort_start = datetime.now()
        results.sort(key=lambda x: x[1], reverse=True)
        sorted_results = results[:k]
        sort_time = (datetime.now() - sort_start).total_seconds() * 1000
        if sort_time > 10:
            print(f"[TIMING] RAG sorting: {sort_time:.2f}ms")
        
        return sorted_results
        
    except Exception as e:
        print(f"Error searching embeddings: {e}")
        return []
    finally:
        conn.close()

# ---------- MAIN ----------
def main():
    print("Extracting documents from Supabase...")
    docs = gather_documents_from_supabase()
    print(f"{len(docs)} original documents found (before chunking).")
    index_documents_to_supabase(docs, model_name=MODEL_NAME)
    print("Done. You can now search with search_query_supabase(query, k).")

if __name__ == "__main__":
    main()
