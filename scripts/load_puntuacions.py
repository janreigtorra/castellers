# load_puntuacions.py
import json
import sqlite3

DB_PATH = "database.db"
JSON_PATH = "data_basic/puntuacions.json"

def load_puntuacions(db_path=DB_PATH, json_path=JSON_PATH):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    punts = data.get("puntuacions", data)  # si el fitxer té directament l'objecte
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    for castell_code, scores in punts.items():
        descarregat = scores.get("descarregat") or scores.get("descarregats") or None
        carregat = scores.get("carregat") or scores.get("carregats") or None
        # Create external code by replacing 'd' with 'de'
        castell_code_external = castell_code.replace('d', 'de') if castell_code else None
        cur.execute("""
            INSERT OR REPLACE INTO puntuacions (castell_code, castell_code_external, punts_descarregat, punts_carregat)
            VALUES (?, ?, ?, ?)
        """, (castell_code, castell_code_external, descarregat, carregat))

    conn.commit()
    conn.close()
    print("Puntuacions carregades des de", json_path)

if __name__ == "__main__":
    load_puntuacions()
