# load_colles.py
import json
import sqlite3
import re
from datetime import datetime

DB_PATH = "database.db"
JSON_PATH = "data_basic/colles_castelleres.json"

def parse_date_try(s):
    if not s:
        return None
    s = s.strip()
    # intents de formats habituals
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except:
            pass
    # buscar seqüència dd/mm/yyyy dins la cadena
    m = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat()
        except:
            pass
    return s  # si no es pot parsejar deixem l'original

def upsert_colla(cur, colla):
    colla_id = colla.get("colla_id")
    name = colla.get("colla_name")
    wiki = colla.get("wikipedia", {})
    perf = colla.get("performance", {})

    # Only create colla entry if we have a colla_id
    if not colla_id:
        print(f"Skipping colla '{name}' - no colla_id provided")
        return None

    # Inserció inicial si no existeix (INSERT OR IGNORE)
    cur.execute("""
    INSERT OR IGNORE INTO colles (
        colla_id, name, logo_url, website, instagram, facebook,
        wikipedia_url, wikipedia_title, wikipedia_description, scraped_at,
        detail_url, basic_info_json, first_actuacio, last_actuacio,
        best_castells_json, wiki_stats_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        colla_id,
        name,
        colla.get("logo_url"),
        colla.get("website"),
        colla.get("instagram"),
        (colla.get("basic_info") or {}).get("facebook") if colla.get("basic_info") else None,
        wiki.get("url"),
        wiki.get("title"),
        wiki.get("description"),
        colla.get("scraped_at"),
        colla.get("detail_url"),
        json.dumps(colla.get("basic_info", {}), ensure_ascii=False),
        parse_date_try(perf.get("first_actuacio")),
        parse_date_try(perf.get("last_actuacio")),
        json.dumps(perf.get("best_actuacions", []), ensure_ascii=False),
        json.dumps(wiki.get("wiki_stats", {}), ensure_ascii=False)
    ))

    # Recuperar id
    cur.execute("SELECT id FROM colles WHERE colla_id = ? LIMIT 1", (colla_id,))
    row = cur.fetchone()
    if row:
        return row[0]
    else:
        # fallback: buscar per nom només
        cur.execute("SELECT id FROM colles WHERE name = ? LIMIT 1", (name,))
        r = cur.fetchone()
        return r[0] if r else None

def load_json_to_db(db_path=DB_PATH, json_path=JSON_PATH):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    colles_list = data.get("colles", [])
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    conn.execute("PRAGMA foreign_keys = ON;")

    for colla in colles_list:
        colla_fk = upsert_colla(cur, colla)
        
        # Skip processing if colla_fk is None (no colla_id provided)
        if not colla_fk:
            continue

        # inserir wiki_stats (clau-valor)
        wiki = colla.get("wikipedia", {})
        wiki_stats = wiki.get("wiki_stats", {})
        if wiki_stats and colla_fk:
            for k, v in wiki_stats.items():
                cur.execute("""
                    INSERT INTO colles_wiki_info (colla_fk, key, value) VALUES (?, ?, ?)
                """, (colla_fk, str(k), str(v)))

        # inserir info_wikipedia (texts per RAG)
        info_wiki_list = wiki.get("info_wikipedia", []) or []
        if colla_fk:
            for txt in info_wiki_list:
                if txt and txt.strip():
                    cur.execute("""
                        INSERT INTO colles_wiki_texts (colla_fk, text) VALUES (?, ?)
                    """, (colla_fk, txt.strip()))

        # inserir best_actuacions
        perf = colla.get("performance", {})
        for act in perf.get("best_actuacions", []):
            cur.execute("""
                INSERT INTO colles_best_actuacions (colla_fk, rank, date, location, diada, actuacio, points)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                colla_fk,
                act.get("rank"),
                parse_date_try(act.get("date")),
                act.get("location"),
                act.get("diada"),
                act.get("actuacio"),
                act.get("points")
            ))

        # inserir best_castells (estadístiques)
        for bc in perf.get("best_castells", []):
            # els keys poden variar, així que fem get amb safeguards
            cur.execute("""
                INSERT INTO colles_best_castells (colla_fk, castell_name, descarregats, carregats, intents, intents_descarregats)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                colla_fk,
                bc.get("castell_name") or bc.get("castell") or bc.get("name"),
                bc.get("descarregats") or bc.get("descarregats", 0) or bc.get("descarregat"),
                bc.get("carregats") or bc.get("carregat"),
                bc.get("intents") or bc.get("intents", 0),
                bc.get("intents_descarregats") or bc.get("intents_desmuntats") or bc.get("intents_descarregats", 0)
            ))

    conn.commit()
    conn.close()
    print("Colles carregades des de", json_path)

if __name__ == "__main__":
    load_json_to_db()
