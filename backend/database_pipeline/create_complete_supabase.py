#!/usr/bin/env python3
"""
create_complete_supabase.py
Creates the complete Supabase database directly from JSON files stored in Supabase Storage.
Downloads JSON files from Supabase Storage bucket 'data-basic' and processes them.
"""

import json
import psycopg2
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
# Get the backend directory (parent of database_pipeline)
BACKEND_DIR = SCRIPT_DIR.parent
# Data directory is in backend/data_basic
DATA_DIR = BACKEND_DIR / "data_basic"

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

# Initialize Supabase client for storage
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def download_json_from_storage(file_path: str) -> str:
    """Download JSON file from Supabase Storage and return local path"""
    try:
        # Download file from storage
        response = supabase.storage.from_('data-basic').download(file_path)
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json', encoding='utf-8')
        temp_file.write(response.decode('utf-8'))
        temp_file.close()
        
        print(f"Downloaded {file_path} to {temp_file.name}")
        return temp_file.name
        
    except Exception as e:
        print(f"Error downloading {file_path}: {e}")
        raise

def cleanup_temp_files(temp_files: list):
    """Clean up temporary files"""
    for temp_file in temp_files:
        try:
            os.unlink(temp_file)
            print(f"Cleaned up {temp_file}")
        except Exception as e:
            print(f"Error cleaning up {temp_file}: {e}")

def normalize_colla_name(name):
    """Normalize colla names to match database entries"""
    if not name:
        return name
    
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
    cur.execute("SELECT id FROM colles WHERE name = %s", (colla_name,))
    result = cur.fetchone()
    if result:
        return result[0]
    
    # Try normalized name
    normalized_name = normalize_colla_name(colla_name)
    cur.execute("SELECT id FROM colles WHERE name = %s", (normalized_name,))
    result = cur.fetchone()
    if result:
        return result[0]
    
    # Try partial matches
    cur.execute("SELECT id, name FROM colles WHERE name LIKE %s", (f"%{colla_name}%",))
    result = cur.fetchone()
    if result:
        print(f"Partial match found: '{colla_name}' -> '{result[1]}' (ID: {result[0]})")
        return result[0]
    
    return None

def create_supabase_schema():
    """Create the complete database schema in Supabase"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Creating Supabase database schema...")
    
    # Create tables (same schema as SQLite but PostgreSQL syntax)
    
    # Main colles table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS colles (
            id SERIAL PRIMARY KEY,
            colla_id TEXT UNIQUE,
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
            basic_info_json TEXT,
            first_actuacio TEXT,
            last_actuacio TEXT,
            best_castells_json TEXT,
            wiki_stats_json TEXT
        );
    """)
    
    # Events table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            event_id TEXT UNIQUE,
            name TEXT,
            date TEXT,
            place TEXT,
            city TEXT,
            scraped_at TEXT
        );
    """)
    
    # Event-Colles junction table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS event_colles (
            id SERIAL PRIMARY KEY,
            event_fk INTEGER REFERENCES events(id) ON DELETE CASCADE,
            colla_fk INTEGER REFERENCES colles(id) ON DELETE CASCADE,
            UNIQUE(event_fk, colla_fk)
        );
    """)
    
    # Castells table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS castells (
            id SERIAL PRIMARY KEY,
            event_colla_fk INTEGER REFERENCES event_colles(id) ON DELETE CASCADE,
            castell_name TEXT,
            status TEXT,
            raw_text TEXT,
            UNIQUE(event_colla_fk, castell_name)
        );
    """)
    
    # Puntuacions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS puntuacions (
            castell_code TEXT PRIMARY KEY,
            castell_code_external TEXT,
            punts_descarregat INTEGER,
            punts_carregat INTEGER,
            castell_code_name TEXT
        );
    """)
    
    # Concurs table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS concurs (
            id SERIAL PRIMARY KEY,
            edition TEXT UNIQUE,
            title TEXT,
            date TEXT,
            location TEXT,
            colla_guanyadora TEXT,
            num_colles INTEGER,
            castells_intentats INTEGER,
            maxim_castell TEXT,
            espectadors TEXT,
            plaça TEXT,
            infobox_json TEXT,
            paragraphs_json TEXT
        );
    """)
    
    # Concurs rankings table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS concurs_rankings (
            id SERIAL PRIMARY KEY,
            concurs_fk INTEGER REFERENCES concurs(id) ON DELETE CASCADE,
            colla_fk INTEGER REFERENCES colles(id) ON DELETE CASCADE,
            position INTEGER,
            colla_name TEXT,
            total_points INTEGER,
            "any" INTEGER,
            jornada TEXT,
            ronda_1_json TEXT,
            ronda_2_json TEXT,
            ronda_3_json TEXT,
            ronda_4_json TEXT,
            ronda_5_json TEXT,
            ronda_6_json TEXT,
            ronda_7_json TEXT,
            ronda_8_json TEXT,
            rondes_json TEXT
        );
    """)
    
    # Colles wiki info table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS colles_wiki_info (
            id SERIAL PRIMARY KEY,
            colla_fk INTEGER REFERENCES colles(id) ON DELETE CASCADE,
            key TEXT,
            value TEXT
        );
    """)
    
    # Colles wiki texts table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS colles_wiki_texts (
            id SERIAL PRIMARY KEY,
            colla_fk INTEGER REFERENCES colles(id) ON DELETE CASCADE,
            text TEXT
        );
    """)
    
    # Colles best actuacions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS colles_best_actuacions (
            id SERIAL PRIMARY KEY,
            colla_fk INTEGER REFERENCES colles(id) ON DELETE CASCADE,
            rank INTEGER,
            date TEXT,
            location TEXT,
            diada TEXT,
            actuacio TEXT,
            points INTEGER
        );
    """)
    
    # Colles best castells table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS colles_best_castells (
            id SERIAL PRIMARY KEY,
            colla_fk INTEGER REFERENCES colles(id) ON DELETE CASCADE,
            rank INTEGER,
            castell_name TEXT,
            date TEXT,
            location TEXT,
            diada TEXT,
            points INTEGER
        );
    """)
    
    # General info table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS general_info (
            id SERIAL PRIMARY KEY,
            line_number INTEGER,
            text TEXT,
            category TEXT
        );
    """)
    
    # Create indexes for performance (with IF NOT EXISTS)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_colles_name ON colles(name);",
        "CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);",
        "CREATE INDEX IF NOT EXISTS idx_castells_name ON castells(castell_name);",
        "CREATE INDEX IF NOT EXISTS idx_punts_code ON puntuacions(castell_code);",
        "CREATE INDEX IF NOT EXISTS idx_concurs_edition ON concurs(edition);",
        "CREATE INDEX IF NOT EXISTS idx_concurs_rankings_position ON concurs_rankings(position);",
        "CREATE INDEX IF NOT EXISTS idx_concurs_rankings_colla ON concurs_rankings(colla_fk);",
        "CREATE INDEX IF NOT EXISTS idx_concurs_rankings_concurs ON concurs_rankings(concurs_fk);",
        "CREATE INDEX IF NOT EXISTS idx_concurs_rankings_any ON concurs_rankings(\"any\");"
    ]
    
    for index_sql in indexes:
        try:
            cur.execute(index_sql)
        except Exception as e:
            print(f"Index creation warning: {e}")
    
    conn.commit()
    conn.close()
    print("Supabase schema created successfully!")

def load_colles_to_supabase(colles_file_path: str):
    """Load colles data from JSON file to Supabase"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Loading colles...")
    
    with open(colles_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    colles = data.get("colles", data)
    
    # Delete existing data from related tables for fresh reload
    print("Clearing related colles tables...")
    cur.execute("DELETE FROM colles_wiki_info")
    cur.execute("DELETE FROM colles_wiki_texts")
    cur.execute("DELETE FROM colles_best_actuacions")
    cur.execute("DELETE FROM colles_best_castells")
    conn.commit()
    print("Related tables cleared")
    
    wiki_info_count = 0
    wiki_texts_count = 0
    best_actuacions_count = 0
    best_castells_count = 0
    
    for colla in colles:
        try:
            # Insert main colla record
            cur.execute("""
                INSERT INTO colles (
                    colla_id, name, logo_url, website, instagram, facebook,
                    wikipedia_url, wikipedia_title, wikipedia_description, scraped_at,
                    detail_url, basic_info_json, first_actuacio, last_actuacio,
                    best_castells_json, wiki_stats_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT (colla_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    logo_url = EXCLUDED.logo_url,
                    website = EXCLUDED.website,
                    instagram = EXCLUDED.instagram,
                    facebook = EXCLUDED.facebook,
                    wikipedia_url = EXCLUDED.wikipedia_url,
                    wikipedia_title = EXCLUDED.wikipedia_title,
                    wikipedia_description = EXCLUDED.wikipedia_description,
                    scraped_at = EXCLUDED.scraped_at,
                    detail_url = EXCLUDED.detail_url,
                    basic_info_json = EXCLUDED.basic_info_json,
                    first_actuacio = EXCLUDED.first_actuacio,
                    last_actuacio = EXCLUDED.last_actuacio,
                    best_castells_json = EXCLUDED.best_castells_json,
                    wiki_stats_json = EXCLUDED.wiki_stats_json
            """, (
                colla.get("colla_id"),
                colla.get("colla_name"),  # JSON has "colla_name", not "name"
                colla.get("logo_url"),
                colla.get("website"),
                colla.get("instagram"),
                colla.get("facebook") or (colla.get("basic_info", {}).get("facebook") if colla.get("basic_info") else None),  # Check basic_info for facebook
                colla.get("wikipedia", {}).get("url") if colla.get("wikipedia") else None,  # JSON has wikipedia.url
                colla.get("wikipedia", {}).get("title") if colla.get("wikipedia") else None,  # JSON has wikipedia.title
                colla.get("wikipedia", {}).get("description") if colla.get("wikipedia") else None,  # JSON has wikipedia.description
                colla.get("scraped_at"),
                colla.get("detail_url"),
                json.dumps(colla.get("basic_info", {}), ensure_ascii=False),
                colla.get("performance", {}).get("first_actuacio") if colla.get("performance") else None,  # JSON has performance.first_actuacio
                colla.get("performance", {}).get("last_actuacio") if colla.get("performance") else None,  # JSON has performance.last_actuacio
                json.dumps(colla.get("best_castells", []), ensure_ascii=False),  # JSON has best_castells as array
                json.dumps(colla.get("wikipedia", {}).get("wiki_stats", {}) if colla.get("wikipedia") else {}, ensure_ascii=False)  # JSON has wikipedia.wiki_stats
            ))
            
            # Get colla ID for related tables
            colla_id = colla.get("colla_id")
            if not colla_id:
                continue
                
            cur.execute("SELECT id FROM colles WHERE colla_id = %s", (colla_id,))
            colla_row = cur.fetchone()
            if not colla_row:
                continue
            colla_fk = colla_row[0]
            
            # Insert wiki_stats into colles_wiki_info (key-value pairs)
            wiki = colla.get("wikipedia", {})
            wiki_stats = wiki.get("wiki_stats", {})
            if wiki_stats and colla_fk:
                for k, v in wiki_stats.items():
                    try:
                        cur.execute("""
                            INSERT INTO colles_wiki_info (colla_fk, key, value)
                            VALUES (%s, %s, %s)
                        """, (colla_fk, str(k), str(v)))
                        wiki_info_count += 1
                    except Exception as e:
                        print(f"Error inserting wiki_info for {colla.get('colla_name', 'Unknown')}: {e}")
            
            # Insert info_wikipedia into colles_wiki_texts (array of texts)
            info_wiki_list = wiki.get("info_wikipedia", []) or []
            if colla_fk:
                for txt in info_wiki_list:
                    if txt and txt.strip():
                        try:
                            cur.execute("""
                                INSERT INTO colles_wiki_texts (colla_fk, text)
                                VALUES (%s, %s)
                            """, (colla_fk, txt.strip()))
                            wiki_texts_count += 1
                        except Exception as e:
                            print(f"Error inserting wiki_text for {colla.get('colla_name', 'Unknown')}: {e}")
            
            # Insert best_actuacions
            perf = colla.get("performance", {})
            best_actuacions = perf.get("best_actuacions", []) or []
            for act in best_actuacions:
                try:
                    cur.execute("""
                        INSERT INTO colles_best_actuacions (colla_fk, rank, date, location, diada, actuacio, points)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        colla_fk,
                        act.get("rank"),
                        act.get("date"),
                        act.get("location"),
                        act.get("diada"),
                        act.get("actuacio"),
                        act.get("points")
                    ))
                    best_actuacions_count += 1
                except Exception as e:
                    print(f"Error inserting best_actuacio for {colla.get('colla_name', 'Unknown')}: {e}")
            
            # Insert best_castells (statistics)
            # JSON has: castell_name, descarregats, carregats, intents, intents_descarregats
            # Table should have: colla_fk, castell_name, descarregats, carregats, intents, intents_descarregats
            best_castells = perf.get("best_castells", []) or []
            for bc in best_castells:
                try:
                    castell_name = bc.get("castell_name") or bc.get("castell") or bc.get("name")
                    if not castell_name:
                        continue
                    
                    # Insert with statistics from JSON
                    cur.execute("""
                        INSERT INTO colles_best_castells (colla_fk, castell_name, descarregats, carregats, intents, intents_descarregats)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        colla_fk,
                        castell_name,
                        bc.get("descarregats"),
                        bc.get("carregats"),
                        bc.get("intents"),
                        bc.get("intents_descarregats")
                    ))
                    best_castells_count += 1
                except Exception as e:
                    print(f"Error inserting best_castell for {colla.get('colla_name', 'Unknown')}: {e}")
                    
        except Exception as e:
            print(f"Error with colla {colla.get('colla_name', 'Unknown')}: {e}")
    
    conn.commit()
    conn.close()
    print(f"Colles loaded: {len(colles)} records")
    print(f"  - Wiki info: {wiki_info_count} records")
    print(f"  - Wiki texts: {wiki_texts_count} records")
    print(f"  - Best actuacions: {best_actuacions_count} records")
    print(f"  - Best castells: {best_castells_count} records")

def load_actuacions_to_supabase(actuacions_file_path: str):
    """Load actuacions data from JSON file to Supabase"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Loading actuacions...")
    
    with open(actuacions_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    events = data.get("events", data)
    
    # Process events in batches to avoid timeouts
    batch_size = 100
    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]
        
        for event in batch:
            try:
                # Insert event
                cur.execute("""
                    INSERT INTO events (event_id, name, date, place, city, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        date = EXCLUDED.date,
                        place = EXCLUDED.place,
                        city = EXCLUDED.city,
                        scraped_at = EXCLUDED.scraped_at
                """, (
                    event.get("event_id"),
                    event.get("event_name"),  # JSON has "event_name", not "name"
                    event.get("date"),
                    event.get("place"),
                    event.get("city"),
                    event.get("scraped_at")
                ))
                
                # Get event ID
                cur.execute("SELECT id FROM events WHERE event_id = %s", (event.get("event_id"),))
                event_row = cur.fetchone()
                if event_row:
                    event_id = event_row[0]
                else:
                    continue
                
                # Process colles for this event
                colles = event.get("colles", [])
                for colla in colles:
                    colla_name = colla.get("colla_name")
                    if not colla_name:
                        continue
                    
                    # Find colla ID
                    colla_id = find_colla_id(colla_name, cur)
                    if not colla_id:
                        print(f"Warning: Could not find colla '{colla_name}' in database")
                        continue
                    
                    # Insert event-colla relationship
                    cur.execute("""
                        INSERT INTO event_colles (event_fk, colla_fk)
                        VALUES (%s, %s)
                        ON CONFLICT (event_fk, colla_fk) DO NOTHING
                    """, (event_id, colla_id))
                    
                    # Get event_colla_id for castells
                    cur.execute("""
                        SELECT id FROM event_colles 
                        WHERE event_fk = %s AND colla_fk = %s
                    """, (event_id, colla_id))
                    event_colla_row = cur.fetchone()
                    if not event_colla_row:
                        continue
                    event_colla_id = event_colla_row[0]
                    
                    # Insert castells fresh (no conflicts, no duplicates - table was cleared)
                    castells = colla.get("castells", [])
                    for castell in castells:
                        cur.execute("""
                            INSERT INTO castells (event_colla_fk, castell_name, status, raw_text)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            event_colla_id,
                            castell.get("castell_name"),
                            castell.get("status"),
                            castell.get("raw_text")
                        ))
                
            except Exception as e:
                print(f"Error with event {event.get('event_name', 'Unknown')}: {e}")
                conn.rollback()
                continue
        
        # Commit batch
        conn.commit()
        print(f"Processed batch {i//batch_size + 1}/{(len(events) + batch_size - 1)//batch_size}")
    
    conn.close()
    print(f"Actuacions loaded: {len(events)} events")

def load_puntuacions_to_supabase(puntuacions_file_path: str):
    """Load puntuacions data from JSON file to Supabase"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Loading puntuacions...")
    
    with open(puntuacions_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    punts = data.get("puntuacions", data)
    
    # Castell code name mapping from update_puntuacions_add_castell_code_name.py
    castell_code_name_mapping = {
        "2de6": "2d6",
        "2de6s": "2d6s", 
        "2de7": "2d7",
        "2de8": "2d8",
        "2de8f": "2d8f",
        "2de9f": "2d9f",
        "2de9fm": "2d9fm",
        "3de10fm": "3d10fm",
        "3de6": "3d6",
        "3de6p": "3d6a", # 'p' matches 'a'
        "3de6s": "3d6s",
        "3de7": "3d7",
        "3de7p": "3d7a", # 'p' matches 'a'
        "3de7s": "3d7s",
        "3de8": "3d8",
        "3de8p": "3d8a", # 'p' matches 'a'
        "3de8s": "3d8s",
        "3de9": "3d9",
        "3de9f": "3d9f",
        "3de9fp": "3d9af", # 'fp' matches 'af'
        "4de10fm": "4d10fm",
        "4de6": "4d6",
        "4de6p": "4d6a", # 'p' matches 'a'
        "4de7": "4d7",
        "4de7p": "4d7a", # 'p' matches 'a'
        "4de8": "4d8",
        "4de8p": "4d8a", # 'p' matches 'a'
        "4de9": "4d9",
        "4de9f": "4d9f",
        "4de9fp": "4d9af", # 'fp' matches 'af'
        "5de6": "5d6",
        "5de6p": "5d6a", # 'p' matches 'a'
        "5de7": "5d7",
        "5de7p": "5d7a", # 'p' matches 'a'
        "5de8": "5d8",
        "5de8p": "5d8a", # 'p' matches 'a'
        "5de9f": "5d9f",
        "7de6": "7d6",
        "7de6p": "7d6a", # 'p' matches 'a'
        "7de7": "7d7",
        "7de7p": "7d7a", # 'p' matches 'a'
        "7de8": "7d8",
        "7de8p": "7d8a", # 'p' matches 'a'
        "7de9f": "7d9f",
        "9de6": "9d6",
        "9de7": "9d7",
        "9de8": "9d8",
        "9de9f": "9d9f",
        "Pde4": "Pd4", # Also, change 'd4' code a 'Pd4'
        "Pde5": "Pd5",
        "Pde6": "Pd6",
        "Pde7f": "Pd7f",
        "Pde8fm": "Pd8fm",
        "Pde9fmp": "Pd9fmp"
    }
    
    for castell_code, scores in punts.items():
        descarregat = scores.get("descarregat") or scores.get("descarregats") or None
        carregat = scores.get("carregat") or scores.get("carregats") or None
        castell_code_external = castell_code.replace('d', 'de') if castell_code else None
        # Use the exact mapping from update_puntuacions_add_castell_code_name.py
        castell_code_name = castell_code_name_mapping.get(castell_code_external, castell_code)
        
        try:
            cur.execute("""
                INSERT INTO puntuacions (castell_code, castell_code_external, punts_descarregat, punts_carregat, castell_code_name)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (castell_code) DO UPDATE SET
                    castell_code_external = EXCLUDED.castell_code_external,
                    punts_descarregat = EXCLUDED.punts_descarregat,
                    punts_carregat = EXCLUDED.punts_carregat,
                    castell_code_name = EXCLUDED.castell_code_name
            """, (castell_code, castell_code_external, descarregat, carregat, castell_code_name))
        except Exception as e:
            print(f"Error with puntuacio {castell_code}: {e}")
    
    conn.commit()
    conn.close()
    print(f"Puntuacions loaded: {len(punts)} records")

def load_concurs_to_supabase(concurs_ranking_file_path: str, concurs_editions_file_path: str):
    """Load concurs data from JSON files to Supabase"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Loading concurs data...")
    
    # Load ranking data
    with open(concurs_ranking_file_path, 'r', encoding='utf-8') as f:
        ranking_data = json.load(f)
    
    # Load editions data
    with open(concurs_editions_file_path, 'r', encoding='utf-8') as f:
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (edition) DO UPDATE SET
                title = EXCLUDED.title,
                date = EXCLUDED.date,
                location = EXCLUDED.location,
                colla_guanyadora = EXCLUDED.colla_guanyadora,
                num_colles = EXCLUDED.num_colles,
                castells_intentats = EXCLUDED.castells_intentats,
                maxim_castell = EXCLUDED.maxim_castell,
                espectadors = EXCLUDED.espectadors,
                plaça = EXCLUDED.plaça,
                infobox_json = EXCLUDED.infobox_json,
                paragraphs_json = EXCLUDED.paragraphs_json
        """, (edition, title, date, location, colla_guanyadora, num_colles, 
              castells_intentats, maxim_castell, espectadors, plaça, 
              infobox_json, paragraphs_json))
        
        # Get concurs ID
        cur.execute("SELECT id FROM concurs WHERE edition = %s", (edition,))
        concurs_row = cur.fetchone()
        if concurs_row:
            concurs_id = concurs_row[0]
        else:
            concurs_id = cur.lastrowid
        concurs_inserted += 1
        
        # Insert rankings
        for result in edition_data['results']:
            colla_name = result['colla']
            position = result['position']
            total_points_raw = result['punts']
            jornada = result.get('jornada', '')
            rondes_data = result.get('rondes', {})
            rondes_json = json.dumps(rondes_data, ensure_ascii=False)
            
            # Handle total_points - convert to integer if possible, otherwise NULL
            try:
                total_points = int(total_points_raw) if total_points_raw else None
            except (ValueError, TypeError):
                total_points = None  # Set to NULL for non-numeric values like "Desqualificada"
            
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
                # Build the INSERT query with all ronda columns (escape "any" column)
                columns = ["concurs_fk", "colla_fk", "position", "colla_name", "total_points", "\"any\"", "jornada"] + ronda_columns + ["rondes_json"]
                placeholders = ["%s"] * len(columns)
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

def load_general_info_to_supabase(general_info_file_path: str):
    """Load general info data from text file to Supabase"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Loading general info...")
    
    # Delete all existing general_info for fresh reload
    print("Deleting all general_info for fresh reload...")
    cur.execute("DELETE FROM general_info")
    deleted_count = cur.rowcount
    print(f"Deleted {deleted_count} general_info records")
    
    # Reset the sequence to start from 1
    cur.execute("ALTER SEQUENCE general_info_id_seq RESTART WITH 1")
    print("General info sequence reset")
    
    conn.commit()
    
    with open(general_info_file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Split content into categories
    categories = {
        "history": "HISTÒRIA",
        "technique": "TÈCNICA",
        "music": "MÚSICA",
        "traditions": "TRADICIONS",
        "glossary": "GLOSSARI"
    }
    
    current_category = None
    line_number = 0
    inserted_count = 0
    
    for line in content.split('\n'):
        line_number += 1
        line = line.strip()
        
        if not line:
            continue
        
        # Check if this line starts a new category
        for cat_key, cat_header in categories.items():
            if line.startswith(cat_header):
                current_category = cat_key
                break
        
        # If we have a category and the line is not empty, insert it
        if current_category and line and not line.startswith(tuple(categories.values())):
            cur.execute("""
                INSERT INTO general_info (line_number, text, category)
                VALUES (%s, %s, %s)
            """, (line_number, line, current_category))
            inserted_count += 1
    
    conn.commit()
    conn.close()
    print(f"General info loaded: {inserted_count} records")

def main():
    """Main function to create complete Supabase database from local files"""
    
    print("Creating Complete Supabase Database from Local Files")
    print("=" * 50)
    
    if not DATABASE_URL:
        print("DATABASE_URL not set in .env file")
        return
    
    # Use local files instead of downloading from Supabase Storage
    print(f"Using local data files from {DATA_DIR}...")
    
    local_files = {
        "colles_castelleres.json": DATA_DIR / "colles_castelleres.json",
        "castellers_data.json": DATA_DIR / "castellers_data.json",
        "puntuacions.json": DATA_DIR / "puntuacions.json",
        "concurs/concurs_ranking_clean.json": DATA_DIR / "concurs" / "concurs_ranking_clean.json",
        "concurs_de_castells_editions.json": DATA_DIR / "concurs_de_castells_editions.json",
        "castellers_info_basic.txt": DATA_DIR / "castellers_info_basic.txt"
    }
    
    # Check if all files exist
    missing_files = []
    for key, file_path in local_files.items():
        if not file_path.exists():
            missing_files.append(str(file_path))
    
    if missing_files:
        print(f"❌ Error: Missing local files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        print("\n💡 Make sure all files exist in data_basic/ directory")
        return
    
    print("✅ All local files found")
    
    try:
        
        # Create schema
        print("\nCreating database schema...")
        create_supabase_schema()
        
        # Load data in order (respecting foreign key dependencies)
        print("\nLoading data...")
        
        # 1. Load colles first (referenced by other tables)
        load_colles_to_supabase(str(local_files["colles_castelleres.json"]))
        
        # 2. Load puntuacions (independent)
        load_puntuacions_to_supabase(str(local_files["puntuacions.json"]))
        
        # 3. Load actuacions (references colles)
        load_actuacions_to_supabase(str(local_files["castellers_data.json"]))
        
        # 4. Load concurs data (references colles)
        load_concurs_to_supabase(
            str(local_files["concurs/concurs_ranking_clean.json"]),
            str(local_files["concurs_de_castells_editions.json"])
        )
        
        # 5. Load general info (independent)
        load_general_info_to_supabase(str(local_files["castellers_info_basic.txt"]))
        
        print("\nDatabase creation completed successfully!")
        
    except Exception as e:
        print(f"Error creating database: {e}")
        raise

if __name__ == "__main__":
    main()