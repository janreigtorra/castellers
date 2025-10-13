#!/usr/bin/env python3
"""
create_concurs_tables.py
Creates tables for concurs information and loads data from concurs_ranking_clean.json and concurs_de_castells_editions.json
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = "database.db"
CONCURS_RANKING_FILE = "data_basic/concurs/concurs_ranking_clean.json"
CONCURS_EDITIONS_FILE = "data_basic/concurs_de_castells_editions.json"

def create_concurs_tables(db_path=DB_PATH):
    """Create tables for concurs information"""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()
    
    # Drop existing tables if they exist
    cur.executescript("""
    DROP TABLE IF EXISTS concurs_rankings;
    DROP TABLE IF EXISTS concurs;
    """)
    
    # Table for concurs metadata (from Wikipedia scraping)
    cur.execute("""
    CREATE TABLE concurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        edition TEXT UNIQUE,           -- e.g., "I", "XXII"
        title TEXT,
        date TEXT,
        location TEXT,
        -- Extracted infobox fields
        colla_guanyadora TEXT,         -- Winning colla
        num_colles INTEGER,            -- Number of participating colles
        castells_intentats INTEGER,    -- Total castles attempted
        maxim_castell TEXT,            -- Maximum castle achieved
        espectadors TEXT,              -- Number of spectators
        plaça TEXT,                    -- Location/plaza
        -- JSON fields for complete data
        infobox_json TEXT,             -- JSON string with infobox data
        paragraphs_json TEXT,          -- JSON string with paragraphs
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Table for concurs rankings (from ranking data)
    cur.execute("""
    CREATE TABLE concurs_rankings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concurs_fk INTEGER,            -- Foreign key to concurs table
        colla_fk INTEGER,              -- Foreign key to colles table
        position INTEGER,
        colla_name TEXT,               -- Original colla name from JSON
        total_points INTEGER,
        any INTEGER,                   -- Year from the JSON data
        jornada TEXT,                  -- Jornada information (e.g., "Jornada Diumenge Tarragona")
        ronda_1_json TEXT,             -- JSON with castell and status for ronda 1
        ronda_2_json TEXT,             -- JSON with castell and status for ronda 2
        ronda_3_json TEXT,             -- JSON with castell and status for ronda 3
        ronda_4_json TEXT,             -- JSON with castell and status for ronda 4
        ronda_5_json TEXT,             -- JSON with castell and status for ronda 5
        ronda_6_json TEXT,             -- JSON with castell and status for ronda 6
        ronda_7_json TEXT,             -- JSON with castell and status for ronda 7
        ronda_8_json TEXT,             -- JSON with castell and status for ronda 8
        rondes_json TEXT,              -- JSON string with all rounds data (for backup)
        FOREIGN KEY(concurs_fk) REFERENCES concurs(id) ON DELETE CASCADE,
        FOREIGN KEY(colla_fk) REFERENCES colles(id) ON DELETE CASCADE
    );
    """)
    
    # Create indexes for better performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concurs_edition ON concurs(edition);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concurs_rankings_position ON concurs_rankings(position);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concurs_rankings_colla ON concurs_rankings(colla_fk);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concurs_rankings_concurs ON concurs_rankings(concurs_fk);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concurs_rankings_any ON concurs_rankings(any);")
    
    conn.commit()
    conn.close()
    print("Concurs tables created successfully.")

def normalize_colla_name(name):
    """Normalize colla names to match database entries"""
    if not name:
        return name
    
    # Common variations and mappings
    mappings = {
        "Colla Nova dels Xiquets de Valls": "Colla Joves Xiquets de Valls",
        "Colla Nova dels Xiquets de Tarragona": "Colla Nova dels Xiquets de Tarragona",
        "Colla Vella dels Xiquets de Tarragona": "Colla Vella dels Xiquets de Tarragona", 
        "Colla Vella dels Xiquets de Valls": "Colla Vella dels Xiquets de Valls",
        "Mirons del Vendrell": "Mirons del Vendrell",
        "Nens del Vendrell": "Nens del Vendrell",
        "Muixerra de Valls": "Muixerra de Valls",
        "Nova de Tarragona": "Colla Nova dels Xiquets de Tarragona",
        "Vella de Tarragona": "Colla Vella dels Xiquets de Tarragona",
        "Colla Nova de Valls": "Colla Joves Xiquets de Valls"
    }
    
    return mappings.get(name, name)

def find_colla_id(colla_name, cur):
    """Find colla ID by name, trying different variations"""
    # Try exact match first
    cur.execute("SELECT id FROM colles WHERE name = ?", (colla_name,))
    result = cur.fetchone()
    if result:
        return result[0]
    
    # Try normalized name
    normalized_name = normalize_colla_name(colla_name)
    cur.execute("SELECT id FROM colles WHERE name = ?", (normalized_name,))
    result = cur.fetchone()
    if result:
        return result[0]
    
    # Try partial matches
    cur.execute("SELECT id, name FROM colles WHERE name LIKE ?", (f"%{colla_name}%",))
    result = cur.fetchone()
    if result:
        print(f"Partial match found: '{colla_name}' -> '{result[1]}' (ID: {result[0]})")
        return result[0]
    
    # Try reverse partial match
    cur.execute("SELECT id, name FROM colles WHERE ? LIKE '%' || name || '%'", (colla_name,))
    result = cur.fetchone()
    if result:
        print(f"Reverse partial match found: '{colla_name}' -> '{result[1]}' (ID: {result[0]})")
        return result[0]
    
    return None

def load_concurs_data(db_path=DB_PATH):
    """Load concurs data from JSON files"""
    if not os.path.exists(CONCURS_RANKING_FILE):
        print(f"Error: File {CONCURS_RANKING_FILE} not found.")
        return
    
    if not os.path.exists(CONCURS_EDITIONS_FILE):
        print(f"Error: File {CONCURS_EDITIONS_FILE} not found.")
        return
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Load ranking data
    with open(CONCURS_RANKING_FILE, 'r', encoding='utf-8') as f:
        ranking_data = json.load(f)
    
    # Load editions data
    with open(CONCURS_EDITIONS_FILE, 'r', encoding='utf-8') as f:
        editions_data = json.load(f)
    
    # Create a mapping of editions for quick lookup
    editions_map = {edition['edicio']: edition for edition in editions_data}
    
    concurs_inserted = 0
    rankings_inserted = 0
    unmatched_colles = set()
    
    for edition_data in ranking_data:
        edition = edition_data['edition']
        title = edition_data['title']
        year = edition_data['any']
        
        # Get additional info from editions data
        edition_info = editions_map.get(edition, {})
        infobox = edition_info.get('infobox', {})
        infobox_json = json.dumps(infobox, ensure_ascii=False)
        paragraphs_json = json.dumps(edition_info.get('paragraphs', []), ensure_ascii=False)
        date = edition_info.get('date', str(year))
        location = edition_info.get('location', '')
        
        # Extract infobox fields
        colla_guanyadora = infobox.get('Colla guanyadora', '') or infobox.get('Colles guanyadores', '')
        num_colles = infobox.get('Colles', '')
        castells_intentats = infobox.get('Castells intentats', '')
        maxim_castell = infobox.get('Màxim castell', '')
        espectadors = infobox.get('Espectadors', '')
        plaça = infobox.get('Plaça', '')
        
        # Convert numeric fields
        try:
            num_colles = int(num_colles) if num_colles else None
        except (ValueError, TypeError):
            num_colles = None
            
        try:
            castells_intentats = int(castells_intentats) if castells_intentats else None
        except (ValueError, TypeError):
            castells_intentats = None
        
        # Insert concurs metadata
        cur.execute("""
            INSERT INTO concurs (edition, title, date, location, colla_guanyadora, num_colles, 
                               castells_intentats, maxim_castell, espectadors, plaça, 
                               infobox_json, paragraphs_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (edition, title, date, location, colla_guanyadora, num_colles, 
              castells_intentats, maxim_castell, espectadors, plaça, 
              infobox_json, paragraphs_json))
        
        concurs_id = cur.lastrowid
        concurs_inserted += 1
        
        # Insert rankings
        for result in edition_data['results']:
            colla_name = result['colla']
            position = result['position']
            total_points = result['punts']
            jornada = result.get('jornada', '')
            rondes_data = result.get('rondes', {})
            rondes_json = json.dumps(rondes_data, ensure_ascii=False)
            
            # Prepare individual ronda columns
            ronda_columns = []
            ronda_values = []
            
            for i in range(1, 9):  # 8 rondes maximum
                ronda_key = f"{i}a"
                if ronda_key in rondes_data:
                    ronda_info = rondes_data[ronda_key]
                    ronda_json = json.dumps(ronda_info, ensure_ascii=False)
                else:
                    ronda_json = None
                
                ronda_columns.append(f"ronda_{i}_json")
                ronda_values.append(ronda_json)
            
            # Find colla ID
            colla_id = find_colla_id(colla_name, cur)
            
            if colla_id:
                # Build the INSERT query with all ronda columns
                columns = ["concurs_fk", "colla_fk", "position", "colla_name", "total_points", "any", "jornada"] + ronda_columns + ["rondes_json"]
                placeholders = ["?"] * len(columns)
                values = [concurs_id, colla_id, position, colla_name, total_points, year, jornada] + ronda_values + [rondes_json]
                
                query = f"""
                    INSERT INTO concurs_rankings 
                    ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                """
                
                cur.execute(query, values)
                rankings_inserted += 1
            else:
                unmatched_colles.add(colla_name)
                print(f"Warning: Could not find colla '{colla_name}' in database")
    
    conn.commit()
    conn.close()
    
    print(f"Loaded {concurs_inserted} concurs editions and {rankings_inserted} rankings.")
    if unmatched_colles:
        print(f"Unmatched colles: {sorted(unmatched_colles)}")

def main():
    print("Creating concurs tables...")
    create_concurs_tables()
    
    print("Loading concurs data...")
    load_concurs_data()
    
    print("Done!")

if __name__ == "__main__":
    main()
