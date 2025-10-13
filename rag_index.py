"""
rag_index.py
Genera embeddings i index FAISS a partir de la base de dades SQLite 'database.db'.

Sortida per defecte a: ./rag_index/
"""

import os
import json
import sqlite3
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
from tqdm import tqdm

# ---------- CONFIGURACIÓ ----------
DB_PATH = "database.db"
OUTPUT_DIR = "rag_index"
MODEL_NAME = "all-MiniLM-L6-v2"   # equilibrat i ràpid
CHUNK_SIZE_WORDS = 200            # paraules per chunk (ajusta segons necessitats)
OVERLAP_WORDS = 50                # solapament entre chunks
BATCH_SIZE = 256                  # per generar embeddings en batches
# ------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

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
def gather_documents(db_path: str) -> List[Dict[str, Any]]:
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
    conn = sqlite3.connect(db_path)
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
    except sqlite3.OperationalError:
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
    except sqlite3.OperationalError:
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
    except sqlite3.OperationalError:
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
            cur.execute("SELECT castell_name, status, raw_text FROM castells WHERE event_colla_fk = ?", (event_colles_id,))
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
    except sqlite3.OperationalError:
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
    except sqlite3.OperationalError:
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
    except sqlite3.OperationalError:
        pass

    conn.close()
    return docs

# ---------- INDEXACIÓ ----------
def index_documents(docs: List[Dict[str, Any]], model_name: str = MODEL_NAME, output_dir: str = OUTPUT_DIR):
    # carregar model
    print("Carregant model d'embeddings:", model_name)
    model = SentenceTransformer(model_name)

    # preparar llistes finals (per a doc_map)
    doc_texts = []
    doc_meta = []

    # dividir cada doc en chunks
    for doc in docs:
        text = doc.get("text") or ""
        chunks = chunk_text(text, CHUNK_SIZE_WORDS, OVERLAP_WORDS)
        for i, chunk in enumerate(chunks):
            meta = dict(doc)  # copia
            meta["chunk_index"] = i
            meta["chunk_length_words"] = len(words_split(chunk))
            doc_texts.append(chunk)
            doc_meta.append(meta)

    print(f"Total chunks a indexar: {len(doc_texts)}")
    # si no hi ha documents
    if not doc_texts:
        print("No s'han trobat documents per indexar. Sortida.")
        return

    # generar embeddings en batches
    embeddings = []
    for i in tqdm(range(0, len(doc_texts), BATCH_SIZE), desc="Embedding batches"):
        batch_texts = doc_texts[i:i+BATCH_SIZE]
        emb = model.encode(batch_texts, show_progress_bar=False, convert_to_numpy=True)
        embeddings.append(emb)
    embeddings = np.vstack(embeddings).astype("float32")

    # normalitzar L2 per fer IndexFlatIP (cosinus)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0.0] = 1e-9
    embeddings = embeddings / norms

    # crear index FAISS (IndexFlatIP)
    d = embeddings.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(embeddings)  # afegir vectors

    # escriure index a disc
    faiss_index_path = os.path.join(output_dir, "faiss_index.bin")
    faiss.write_index(index, faiss_index_path)
    print("Index FAISS guardat a:", faiss_index_path)

    # guardar doc_map.json (mapa d'id -> metadades i text)
    # nota: la id serà la posició dins l'index (0..N-1)
    doc_map = {}
    for idx, meta in enumerate(doc_meta):
        doc_map[idx] = {
            "meta": meta,
            "text": doc_texts[idx]
        }

    doc_map_path = os.path.join(output_dir, "doc_map.json")
    with open(doc_map_path, "w", encoding="utf-8") as f:
        json.dump(doc_map, f, ensure_ascii=False, indent=2)
    print("doc_map guardat a:", doc_map_path)

    # opcional: embbedings npy
    emb_path = os.path.join(output_dir, "embeddings.npy")
    np.save(emb_path, embeddings)
    print("Embeddings (numpy) guardat a:", emb_path)

    # metadata sobre la indexació
    meta_info = {
        "model": model_name,
        "n_chunks": len(doc_texts),
        "dim": d,
    }
    with open(os.path.join(output_dir, "rag_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta_info, f, ensure_ascii=False, indent=2)
    print("Metadata guardada.")

# ---------- EXEMPLE DE CONSULTA (funció utilitària) ----------
def search_query(query: str, k: int = 5, model_name: str = MODEL_NAME, output_dir: str = OUTPUT_DIR) -> List[Tuple[Dict, float]]:
    """
    Consulta d'exemple: embeddar la pregunta i cercar top-k documents.
    Retorna una llista de tuples (doc_meta, score)
    """
    # carregar index i doc_map
    faiss_index_path = os.path.join(output_dir, "faiss_index.bin")
    doc_map_path = os.path.join(output_dir, "doc_map.json")
    if not os.path.exists(faiss_index_path) or not os.path.exists(doc_map_path):
        raise FileNotFoundError("Index o doc_map no existents. Executa primer rag_index.py per crear-los.")

    index = faiss.read_index(faiss_index_path)
    with open(doc_map_path, "r", encoding="utf-8") as f:
        doc_map = json.load(f)

    model = SentenceTransformer(model_name)
    q_emb = model.encode([query], convert_to_numpy=True).astype("float32")
    q_emb = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)

    D, I = index.search(q_emb, k)
    results = []
    for score, idx in zip(D[0], I[0]):
        if int(idx) < 0:
            continue
        meta = doc_map.get(str(int(idx))) or doc_map.get(int(idx))
        results.append((meta, float(score)))
    return results

# ---------- MAIN ----------
def main():
    print("Extracció de documents...")
    docs = gather_documents(DB_PATH)
    print(f"{len(docs)} documents originals trobats (abans de chunking).")
    index_documents(docs, model_name=MODEL_NAME, output_dir=OUTPUT_DIR)
    print("Fet. Pots fer consultes amb search_query(query, k).")

if __name__ == "__main__":
    main()
