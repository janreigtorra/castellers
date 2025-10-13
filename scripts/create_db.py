# create_db.py
import sqlite3

DB_PATH = "database.db"

def create_tables(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # Esborrem taules prèvies per començar net (opcional)
    cur.executescript("""
    DROP TABLE IF EXISTS concurs_rankings;
    DROP TABLE IF EXISTS concurs;
    DROP TABLE IF EXISTS colles_wiki_texts;
    DROP TABLE IF EXISTS colles_wiki_info;
    DROP TABLE IF EXISTS colles_best_castells;
    DROP TABLE IF EXISTS colles_best_actuacions;
    DROP TABLE IF EXISTS castells;
    DROP TABLE IF EXISTS event_colles;
    DROP TABLE IF EXISTS events;
    DROP TABLE IF EXISTS puntuacions;
    DROP TABLE IF EXISTS colles;
    """)

    # Taula principal de colles (informació bàsica + camps JSON)
    cur.execute("""
    CREATE TABLE colles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        colla_id TEXT UNIQUE,         -- id original de la web (pot ser string)
        name TEXT,
        logo_url TEXT,
        website TEXT,
        instagram TEXT,
        facebook TEXT,
        wikipedia_url TEXT,
        wikipedia_title TEXT,
        wikipedia_description TEXT,
        scraped_at TEXT,
        detail_url TEXT,
        basic_info_json TEXT,         -- json string
        first_actuacio TEXT,
        last_actuacio TEXT,
        best_castells_json TEXT,      -- json string
        wiki_stats_json TEXT          -- json string
    );
    """)

    # Estructures orientades a RAG
    cur.execute("""
    CREATE TABLE colles_wiki_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        colla_fk INTEGER,
        key TEXT,
        value TEXT,
        FOREIGN KEY(colla_fk) REFERENCES colles(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE colles_wiki_texts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        colla_fk INTEGER,
        text TEXT,
        FOREIGN KEY(colla_fk) REFERENCES colles(id) ON DELETE CASCADE
    );
    """)

    # Millors actuacions per colla (ja venen al JSON de colles)
    cur.execute("""
    CREATE TABLE colles_best_actuacions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        colla_fk INTEGER,
        rank INTEGER,
        date TEXT,
        location TEXT,
        diada TEXT,
        actuacio TEXT,
        points INTEGER,
        FOREIGN KEY(colla_fk) REFERENCES colles(id) ON DELETE CASCADE
    );
    """)

    # Estadístiques de millors castells per colla (resum)
    cur.execute("""
    CREATE TABLE colles_best_castells (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        colla_fk INTEGER,
        castell_name TEXT,
        descarregats INTEGER,
        carregats INTEGER,
        intents INTEGER,
        intents_descarregats INTEGER,
        FOREIGN KEY(colla_fk) REFERENCES colles(id) ON DELETE CASCADE
    );
    """)

    # Events (actuacions agregades)
    cur.execute("""
    CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT UNIQUE,
        name TEXT,
        date TEXT,
        time TEXT,
        place TEXT,
        city TEXT,
        raw_date_location TEXT,
        total_colles INTEGER,
        total_castells INTEGER,
        scraped_at TEXT
    );
    """)

    # Relació event - colla (N:M)
    cur.execute("""
    CREATE TABLE event_colles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_fk INTEGER,
        colla_fk INTEGER,
        FOREIGN KEY(event_fk) REFERENCES events(id) ON DELETE CASCADE,
        FOREIGN KEY(colla_fk) REFERENCES colles(id) ON DELETE CASCADE,
        UNIQUE(event_fk, colla_fk)
    );
    """)

    # Castells de cada colla en cada event
    cur.execute("""
    CREATE TABLE castells (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_colla_fk INTEGER,
        castell_name TEXT,
        status TEXT,
        raw_text TEXT,
        FOREIGN KEY(event_colla_fk) REFERENCES event_colles(id) ON DELETE CASCADE
    );
    """)

    # Taula de puntuacions oficials
    cur.execute("""
    CREATE TABLE puntuacions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        castell_code TEXT UNIQUE,
        castell_code_external TEXT,
        punts_descarregat INTEGER,
        punts_carregat INTEGER
    );
    """)

    # Taula per concurs metadata (des de Wikipedia scraping)
    cur.execute("""
    CREATE TABLE concurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        edition TEXT UNIQUE,           -- e.g., "I", "XXII"
        title TEXT,
        date TEXT,
        location TEXT,
        -- Extracted infobox fields
        colla_guanyadora TEXT,         -- Colla guanyadora
        num_colles INTEGER,            -- Nombre de colles participants
        castells_intentats INTEGER,    -- Total castells intentats
        maxim_castell TEXT,            -- Màxim castell assolit
        espectadors TEXT,              -- Nombre d'espectadors
        plaça TEXT,                    -- Ubicació/plaça
        -- JSON fields per dades completes
        infobox_json TEXT,             -- JSON string amb dades infobox
        paragraphs_json TEXT,          -- JSON string amb paràgrafs
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Taula per concurs rankings (des de dades ranking)
    cur.execute("""
    CREATE TABLE concurs_rankings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concurs_fk INTEGER,            -- Foreign key a taula concurs
        colla_fk INTEGER,              -- Foreign key a taula colles
        position INTEGER,
        colla_name TEXT,               -- Nom original colla des de JSON
        total_points INTEGER,
        jornada TEXT,                  -- Informació jornada (e.g., "Jornada Diumenge Tarragona")
        ronda_1_json TEXT,             -- JSON amb castell i status per ronda 1
        ronda_2_json TEXT,             -- JSON amb castell i status per ronda 2
        ronda_3_json TEXT,             -- JSON amb castell i status per ronda 3
        ronda_4_json TEXT,             -- JSON amb castell i status per ronda 4
        ronda_5_json TEXT,             -- JSON amb castell i status per ronda 5
        ronda_6_json TEXT,             -- JSON amb castell i status per ronda 6
        ronda_7_json TEXT,             -- JSON amb castell i status per ronda 7
        ronda_8_json TEXT,             -- JSON amb castell i status per ronda 8
        rondes_json TEXT,              -- JSON string amb totes les rondes (per backup)
        FOREIGN KEY(concurs_fk) REFERENCES concurs(id) ON DELETE CASCADE,
        FOREIGN KEY(colla_fk) REFERENCES colles(id) ON DELETE CASCADE
    );
    """)

    # Índexs per rendiment en consultes comunes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_colles_name ON colles(name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_castells_name ON castells(castell_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_punts_code ON puntuacions(castell_code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concurs_edition ON concurs(edition);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concurs_rankings_position ON concurs_rankings(position);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concurs_rankings_colla ON concurs_rankings(colla_fk);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concurs_rankings_concurs ON concurs_rankings(concurs_fk);")

    conn.commit()
    conn.close()
    print("Taulas creades a", db_path)

if __name__ == "__main__":
    create_tables()
