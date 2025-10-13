# load_actuacions.py
import json
import sqlite3
from datetime import datetime
import re

DB_PATH = "database.db"
JSON_PATHS = ["data_basic/castellers_data.json"] 

def parse_date_try(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except:
            pass
    m = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat()
        except:
            pass
    return s

def find_existing_colla(cur, name):
    cur.execute("SELECT id FROM colles WHERE colla_id = ? OR name = ? LIMIT 1", (name, name))
    r = cur.fetchone()
    if r:
        return r[0]
    cur.execute("SELECT id FROM colles WHERE name = ? LIMIT 1", (name,))
    r = cur.fetchone()
    return r[0] if r else None

def load_actuacions(json_path=None, db_path=DB_PATH):
    # triar fitxer disponible
    chosen = None
    if json_path:
        chosen = json_path
    else:
        import os
        for p in JSON_PATHS:
            if os.path.exists(p):
                chosen = p
                break
    if not chosen:
        raise FileNotFoundError("No s'ha trobat castellers_data.json en cap de les rutes: " + ", ".join(JSON_PATHS))

    with open(chosen, "r", encoding="utf-8") as f:
        data = json.load(f)

    # assumim que el JSON és una llista d'events
    events = data if isinstance(data, list) else data.get("events") or data.get("actuacions") or data.get("data") or [data]

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    for act in events:
        event_id = act.get("event_id") or act.get("id") or act.get("eventId")
        name = act.get("event_name") or act.get("name")
        date_iso = parse_date_try(act.get("date"))
        time = act.get("time")
        place = act.get("place")
        city = act.get("city")
        raw = act.get("raw_date_location")
        total_colles = act.get("total_colles")
        total_castells = act.get("total_castells")
        scraped_at = act.get("scraped_at")

        # Insertar event (si ja existeix s'ignora)
        cur.execute("""
            INSERT OR IGNORE INTO events (event_id, name, date, time, place, city, raw_date_location, total_colles, total_castells, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (event_id, name, date_iso, time, place, city, raw, total_colles, total_castells, scraped_at))

        # agafar l'id real de la BD
        cur.execute("SELECT id FROM events WHERE event_id = ? LIMIT 1", (event_id,))
        event_row = cur.fetchone()
        if not event_row:
            # si no té event_id o no s'ha pogut insertar, inserir amb name com a key única (no ideal)
            cur.execute("INSERT INTO events (name, date, time, place, city, raw_date_location, total_colles, total_castells, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (name, date_iso, time, place, city, raw, total_colles, total_castells, scraped_at))
            event_fk = cur.lastrowid
        else:
            event_fk = event_row[0]

        # per cada colla que participa a l'event
        for colla_obj in act.get("colles", []):
            colla_name = colla_obj.get("colla_name") or colla_obj.get("name")
            colla_id = colla_obj.get("colla_id")
            
            # buscar colla existent per colla_id o nom
            if colla_id:
                cur.execute("SELECT id FROM colles WHERE colla_id = ? LIMIT 1", (colla_id,))
            else:
                cur.execute("SELECT id FROM colles WHERE name = ? LIMIT 1", (colla_name,))
            
            row = cur.fetchone()
            if row:
                colla_fk = row[0]
            else:
                # Skip this colla if it doesn't exist and we don't have colla_id
                print(f"Skipping event colla '{colla_name}' - not found in colles table and no colla_id provided")
                continue

            # inserir relació event-colla (uniqueness evitada per la taula)
            try:
                cur.execute("INSERT OR IGNORE INTO event_colles (event_fk, colla_fk) VALUES (?, ?)", (event_fk, colla_fk))
            except:
                pass
            # agafar event_colles id
            cur.execute("SELECT id FROM event_colles WHERE event_fk = ? AND colla_fk = ? LIMIT 1", (event_fk, colla_fk))
            ec_row = cur.fetchone()
            event_colla_fk = ec_row[0]

            # inserir castells d'aquesta colla a l'event
            for castell in colla_obj.get("castells", []):
                name_cast = castell.get("castell_name") or castell.get("name") or castell.get("raw_text")
                status = castell.get("status")
                raw_text = castell.get("raw_text")
                cur.execute("""
                    INSERT INTO castells (event_colla_fk, castell_name, status, raw_text)
                    VALUES (?, ?, ?, ?)
                """, (event_colla_fk, name_cast, status, raw_text))

    conn.commit()
    conn.close()
    print("Actuacions carregades des de", chosen)

if __name__ == "__main__":
    load_actuacions()
