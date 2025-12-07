#!/usr/bin/env python3
"""
update_database_idempotent.py
Idempotent database update script that adds new records and updates existing ones
without deleting any existing data. Safe to run multiple times.
"""

import json
import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
# Get the backend directory (parent of database_pipeline)
BACKEND_DIR = SCRIPT_DIR.parent
# Data directory is in backend/data_basic
DATA_DIR = BACKEND_DIR / "data_basic"

DATABASE_URL = os.getenv("DATABASE_URL")

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

def update_colles(colles_file_path: str):
    """Update colles data idempotently"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Updating colles...")
    
    with open(colles_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    colles = data.get("colles", data)
    
    updated_count = 0
    inserted_count = 0
    wiki_info_updated = 0
    wiki_info_inserted = 0
    wiki_texts_inserted = 0
    best_actuacions_updated = 0
    best_actuacions_inserted = 0
    best_castells_updated = 0
    best_castells_inserted = 0
    
    for colla in colles:
        try:
            # Update or insert main colla record
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
                colla.get("colla_name"),
                colla.get("logo_url"),
                colla.get("website"),
                colla.get("instagram"),
                colla.get("facebook") or (colla.get("basic_info", {}).get("facebook") if colla.get("basic_info") else None),
                colla.get("wikipedia", {}).get("url") if colla.get("wikipedia") else None,
                colla.get("wikipedia", {}).get("title") if colla.get("wikipedia") else None,
                colla.get("wikipedia", {}).get("description") if colla.get("wikipedia") else None,
                colla.get("scraped_at"),
                colla.get("detail_url"),
                json.dumps(colla.get("basic_info", {}), ensure_ascii=False),
                colla.get("performance", {}).get("first_actuacio") if colla.get("performance") else None,
                colla.get("performance", {}).get("last_actuacio") if colla.get("performance") else None,
                json.dumps(colla.get("best_castells", []), ensure_ascii=False),
                json.dumps(colla.get("wikipedia", {}).get("wiki_stats", {}) if colla.get("wikipedia") else {}, ensure_ascii=False)
            ))
            
            if cur.rowcount > 0:
                # Check if it was an insert or update
                cur.execute("SELECT id FROM colles WHERE colla_id = %s", (colla.get("colla_id"),))
                existing = cur.fetchone()
                if existing:
                    # Check if this was just inserted (no previous record)
                    cur.execute("""
                        SELECT COUNT(*) FROM colles WHERE colla_id = %s
                    """, (colla.get("colla_id"),))
                    # For simplicity, we'll count based on whether name changed
                    # Actually, ON CONFLICT always updates, so we can't easily distinguish
                    # We'll just count total operations
                    updated_count += 1
            
            # Get colla ID for related tables
            colla_id = colla.get("colla_id")
            if not colla_id:
                continue
                
            cur.execute("SELECT id FROM colles WHERE colla_id = %s", (colla_id,))
            colla_row = cur.fetchone()
            if not colla_row:
                continue
            colla_fk = colla_row[0]
            
            # Update wiki_stats into colles_wiki_info (key-value pairs)
            wiki = colla.get("wikipedia", {})
            wiki_stats = wiki.get("wiki_stats", {})
            if wiki_stats and colla_fk:
                for k, v in wiki_stats.items():
                    try:
                        # Check if this key already exists for this colla
                        cur.execute("""
                            SELECT id, value FROM colles_wiki_info 
                            WHERE colla_fk = %s AND key = %s
                        """, (colla_fk, str(k)))
                        existing = cur.fetchone()
                        
                        if existing:
                            # Update if value changed
                            if existing[1] != str(v):
                                cur.execute("""
                                    UPDATE colles_wiki_info 
                                    SET value = %s 
                                    WHERE colla_fk = %s AND key = %s
                                """, (str(v), colla_fk, str(k)))
                                wiki_info_updated += 1
                        else:
                            # Insert new
                            cur.execute("""
                                INSERT INTO colles_wiki_info (colla_fk, key, value)
                                VALUES (%s, %s, %s)
                            """, (colla_fk, str(k), str(v)))
                            wiki_info_inserted += 1
                    except Exception as e:
                        print(f"Error updating wiki_info for {colla.get('colla_name', 'Unknown')}: {e}")
            
            # Update info_wikipedia into colles_wiki_texts (array of texts)
            info_wiki_list = wiki.get("info_wikipedia", []) or []
            if colla_fk:
                # Get existing texts for this colla
                cur.execute("SELECT text FROM colles_wiki_texts WHERE colla_fk = %s", (colla_fk,))
                existing_texts = {row[0] for row in cur.fetchall()}
                
                for txt in info_wiki_list:
                    if txt and txt.strip():
                        txt_clean = txt.strip()
                        if txt_clean not in existing_texts:
                            try:
                                cur.execute("""
                                    INSERT INTO colles_wiki_texts (colla_fk, text)
                                    VALUES (%s, %s)
                                """, (colla_fk, txt_clean))
                                wiki_texts_inserted += 1
                            except Exception as e:
                                print(f"Error inserting wiki_text for {colla.get('colla_name', 'Unknown')}: {e}")
            
            # Update best_actuacions
            perf = colla.get("performance", {})
            best_actuacions = perf.get("best_actuacions", []) or []
            
            # Get existing best actuacions for this colla
            cur.execute("""
                SELECT rank, date, location, diada, actuacio, points 
                FROM colles_best_actuacions 
                WHERE colla_fk = %s
            """, (colla_fk,))
            existing_actuacions = {
                (row[0], row[1], row[2]): (row[3], row[4], row[5]) 
                for row in cur.fetchall()
            }
            
            for act in best_actuacions:
                try:
                    rank = act.get("rank")
                    date = act.get("date")
                    location = act.get("location")
                    diada = act.get("diada")
                    actuacio = act.get("actuacio")
                    points = act.get("points")
                    
                    key = (rank, date, location)
                    existing_values = existing_actuacions.get(key)
                    
                    if existing_values:
                        # Check if values changed
                        if existing_values != (diada, actuacio, points):
                            cur.execute("""
                                UPDATE colles_best_actuacions 
                                SET diada = %s, actuacio = %s, points = %s
                                WHERE colla_fk = %s AND rank = %s AND date = %s AND location = %s
                            """, (diada, actuacio, points, colla_fk, rank, date, location))
                            best_actuacions_updated += 1
                    else:
                        # Insert new
                        cur.execute("""
                            INSERT INTO colles_best_actuacions (colla_fk, rank, date, location, diada, actuacio, points)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (colla_fk, rank, date, location, diada, actuacio, points))
                        best_actuacions_inserted += 1
                except Exception as e:
                    print(f"Error updating best_actuacio for {colla.get('colla_name', 'Unknown')}: {e}")
            
            # Update best_castells (statistics)
            # JSON has: castell_name, descarregats, carregats, intents, intents_descarregats
            # Table should have: colla_fk, castell_name, descarregats, carregats, intents, intents_descarregats
            best_castells = perf.get("best_castells", []) or []
            
            # Get existing best castells for this colla
            # Try to get columns that match what the load function uses
            try:
                cur.execute("""
                    SELECT castell_name, descarregats, carregats, intents, intents_descarregats 
                    FROM colles_best_castells 
                    WHERE colla_fk = %s
                """, (colla_fk,))
                existing_castells = {
                    row[0]: (row[1], row[2], row[3], row[4]) 
                    for row in cur.fetchall()
                }
            except Exception as e:
                # If columns don't exist, try alternative schema (rank, date, location, diada, points)
                print(f"Warning: Could not fetch best_castells with statistics columns, trying alternative schema: {e}")
                try:
                    cur.execute("""
                        SELECT castell_name, rank, date, location, diada, points 
                        FROM colles_best_castells 
                        WHERE colla_fk = %s
                    """, (colla_fk,))
                    existing_castells = {
                        row[0]: (row[1], row[2], row[3], row[4], row[5]) 
                        for row in cur.fetchall()
                    }
                except:
                    existing_castells = {}
            
            for bc in best_castells:
                try:
                    castell_name = bc.get("castell_name") or bc.get("castell") or bc.get("name")
                    if not castell_name:
                        continue
                    
                    # Try statistics columns first (descarregats, carregats, intents, intents_descarregats)
                    descarregats = bc.get("descarregats")
                    carregats = bc.get("carregats")
                    intents = bc.get("intents")
                    intents_descarregats = bc.get("intents_descarregats")
                    
                    existing_values = existing_castells.get(castell_name)
                    
                    if existing_values:
                        # Check if values changed
                        new_values = (descarregats, carregats, intents, intents_descarregats)
                        if existing_values != new_values:
                            try:
                                cur.execute("""
                                    UPDATE colles_best_castells 
                                    SET descarregats = %s, carregats = %s, intents = %s, intents_descarregats = %s
                                    WHERE colla_fk = %s AND castell_name = %s
                                """, (descarregats, carregats, intents, intents_descarregats, colla_fk, castell_name))
                                best_castells_updated += 1
                            except Exception as e:
                                # If statistics columns don't exist, try alternative schema
                                print(f"Warning: Could not update with statistics columns, trying alternative: {e}")
                                rank = bc.get("rank")
                                date = bc.get("date")
                                location = bc.get("location")
                                diada = bc.get("diada")
                                points = bc.get("points")
                                cur.execute("""
                                    UPDATE colles_best_castells 
                                    SET rank = %s, date = %s, location = %s, diada = %s, points = %s
                                    WHERE colla_fk = %s AND castell_name = %s
                                """, (rank, date, location, diada, points, colla_fk, castell_name))
                                best_castells_updated += 1
                    else:
                        # Insert new - try statistics columns first
                        try:
                            cur.execute("""
                                INSERT INTO colles_best_castells (colla_fk, castell_name, descarregats, carregats, intents, intents_descarregats)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (colla_fk, castell_name, descarregats, carregats, intents, intents_descarregats))
                            best_castells_inserted += 1
                        except Exception as e:
                            # If statistics columns don't exist, try alternative schema
                            print(f"Warning: Could not insert with statistics columns, trying alternative: {e}")
                            rank = bc.get("rank")
                            date = bc.get("date")
                            location = bc.get("location")
                            diada = bc.get("diada")
                            points = bc.get("points")
                            cur.execute("""
                                INSERT INTO colles_best_castells (colla_fk, castell_name, rank, date, location, diada, points)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (colla_fk, castell_name, rank, date, location, diada, points))
                            best_castells_inserted += 1
                except Exception as e:
                    print(f"Error updating best_castell for {colla.get('colla_name', 'Unknown')}: {e}")
                    
        except Exception as e:
            print(f"Error with colla {colla.get('colla_name', 'Unknown')}: {e}")
    
    conn.commit()
    conn.close()
    print(f"Colles updated: {updated_count} records updated")
    print(f"  - Wiki info: {wiki_info_inserted} inserted, {wiki_info_updated} updated")
    print(f"  - Wiki texts: {wiki_texts_inserted} inserted")
    print(f"  - Best actuacions: {best_actuacions_inserted} inserted, {best_actuacions_updated} updated")
    print(f"  - Best castells: {best_castells_inserted} inserted, {best_castells_updated} updated")

def update_actuacions(actuacions_file_path: str):
    """Update actuacions data idempotently"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Updating actuacions...")
    
    with open(actuacions_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    events = data.get("events", data)
    
    events_updated = 0
    events_inserted = 0
    event_colles_inserted = 0
    castells_inserted = 0
    castells_updated = 0
    
    # Process events in batches to avoid timeouts
    batch_size = 100
    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]
        
        for event in batch:
            try:
                # Update or insert event
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
                    event.get("event_name"),
                    event.get("date"),
                    event.get("place"),
                    event.get("city"),
                    event.get("scraped_at")
                ))
                
                # Check if this was insert or update (simplified - always counts as update due to ON CONFLICT)
                events_updated += 1
                
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
                    
                    # Insert event-colla relationship (idempotent)
                    cur.execute("""
                        INSERT INTO event_colles (event_fk, colla_fk)
                        VALUES (%s, %s)
                        ON CONFLICT (event_fk, colla_fk) DO NOTHING
                    """, (event_id, colla_id))
                    
                    if cur.rowcount > 0:
                        event_colles_inserted += 1
                    
                    # Get event_colla_id for castells
                    cur.execute("""
                        SELECT id FROM event_colles 
                        WHERE event_fk = %s AND colla_fk = %s
                    """, (event_id, colla_id))
                    event_colla_row = cur.fetchone()
                    if not event_colla_row:
                        continue
                    event_colla_id = event_colla_row[0]
                    
                    # Update castells (use ON CONFLICT for idempotency)
                    castells = colla.get("castells", [])
                    for castell in castells:
                        castell_name = castell.get("castell_name")
                        status = castell.get("status")
                        raw_text = castell.get("raw_text")
                        
                        cur.execute("""
                            INSERT INTO castells (event_colla_fk, castell_name, status, raw_text)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (event_colla_fk, castell_name) DO UPDATE SET
                                status = EXCLUDED.status,
                                raw_text = EXCLUDED.raw_text
                        """, (event_colla_id, castell_name, status, raw_text))
                        
                        # Check if it was insert or update
                        if cur.rowcount > 0:
                            # We can't easily distinguish, but we'll count operations
                            castells_inserted += 1
                
            except Exception as e:
                print(f"Error with event {event.get('event_name', 'Unknown')}: {e}")
                conn.rollback()
                continue
        
        # Commit batch
        conn.commit()
        print(f"Processed batch {i//batch_size + 1}/{(len(events) + batch_size - 1)//batch_size}")
    
    conn.close()
    print(f"Actuacions updated: {events_updated} events")
    print(f"  - Event-colles relationships: {event_colles_inserted} inserted")
    print(f"  - Castells: {castells_inserted} inserted/updated")

def update_puntuacions(puntuacions_file_path: str):
    """Update puntuacions data idempotently"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Updating puntuacions...")
    
    with open(puntuacions_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    punts = data.get("puntuacions", data)
    
    # Castell code name mapping
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
        "3de6p": "3d6a",
        "3de6s": "3d6s",
        "3de7": "3d7",
        "3de7p": "3d7a",
        "3de7s": "3d7s",
        "3de8": "3d8",
        "3de8p": "3d8a",
        "3de8s": "3d8s",
        "3de9": "3d9",
        "3de9f": "3d9f",
        "3de9fp": "3d9af",
        "4de10fm": "4d10fm",
        "4de6": "4d6",
        "4de6p": "4d6a",
        "4de7": "4d7",
        "4de7p": "4d7a",
        "4de8": "4d8",
        "4de8p": "4d8a",
        "4de9": "4d9",
        "4de9f": "4d9f",
        "4de9fp": "4d9af",
        "5de6": "5d6",
        "5de6p": "5d6a",
        "5de7": "5d7",
        "5de7p": "5d7a",
        "5de8": "5d8",
        "5de8p": "5d8a",
        "5de9f": "5d9f",
        "7de6": "7d6",
        "7de6p": "7d6a",
        "7de7": "7d7",
        "7de7p": "7d7a",
        "7de8": "7d8",
        "7de8p": "7d8a",
        "7de9f": "7d9f",
        "9de6": "9d6",
        "9de7": "9d7",
        "9de8": "9d8",
        "9de9f": "9d9f",
        "Pde4": "Pd4",
        "Pde5": "Pd5",
        "Pde6": "Pd6",
        "Pde7f": "Pd7f",
        "Pde8fm": "Pd8fm",
        "Pde9fmp": "Pd9fmp"
    }
    
    updated_count = 0
    
    for castell_code, scores in punts.items():
        descarregat = scores.get("descarregat") or scores.get("descarregats") or None
        carregat = scores.get("carregat") or scores.get("carregats") or None
        castell_code_external = castell_code.replace('d', 'de') if castell_code else None
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
            updated_count += 1
        except Exception as e:
            print(f"Error with puntuacio {castell_code}: {e}")
    
    conn.commit()
    conn.close()
    print(f"Puntuacions updated: {updated_count} records")

def update_concurs(concurs_ranking_file_path: str, concurs_editions_file_path: str):
    """Update concurs data idempotently"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Updating concurs data...")
    
    # Load ranking data
    with open(concurs_ranking_file_path, 'r', encoding='utf-8') as f:
        ranking_data = json.load(f)
    
    # Load editions data
    with open(concurs_editions_file_path, 'r', encoding='utf-8') as f:
        editions_data = json.load(f)
    
    # Create a mapping of editions for quick lookup
    editions_map = {edition['edicio']: edition for edition in editions_data}
    
    concurs_updated = 0
    rankings_inserted = 0
    rankings_updated = 0
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
        
        # Update or insert concurs metadata
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
        concurs_updated += 1
        
        # Get concurs ID
        cur.execute("SELECT id FROM concurs WHERE edition = %s", (edition,))
        concurs_row = cur.fetchone()
        if concurs_row:
            concurs_id = concurs_row[0]
        else:
            continue
        
        # Update rankings
        for result in edition_data['results']:
            colla_name = result['colla']
            position = result['position']
            total_points_raw = result['punts']
            jornada = result.get('jornada', '')
            rondes_data = result.get('rondes', {})
            rondes_json = json.dumps(rondes_data, ensure_ascii=False)
            
            # Handle total_points
            try:
                total_points = int(total_points_raw) if total_points_raw else None
            except (ValueError, TypeError):
                total_points = None
            
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
                # Check if ranking already exists
                cur.execute("""
                    SELECT id FROM concurs_rankings 
                    WHERE concurs_fk = %s AND colla_fk = %s
                """, (concurs_id, colla_id))
                existing_ranking = cur.fetchone()
                
                # Build the columns and values
                columns = ["concurs_fk", "colla_fk", "position", "colla_name", "total_points", "\"any\"", "jornada"] + ronda_columns + ["rondes_json"]
                placeholders = ["%s"] * len(columns)
                values = [concurs_id, colla_id, position, colla_name, total_points, year, jornada] + ronda_values + [rondes_json]
                
                if existing_ranking:
                    # Update existing ranking
                    set_clauses = [f"{col} = %s" for col in columns[2:]]  # Skip concurs_fk and colla_fk
                    update_values = values[2:]  # Skip concurs_fk and colla_fk
                    update_values.append(concurs_id)  # For WHERE clause
                    update_values.append(colla_id)   # For WHERE clause
                    
                    query = f"""
                        UPDATE concurs_rankings 
                        SET {', '.join(set_clauses)}
                        WHERE concurs_fk = %s AND colla_fk = %s
                    """
                    cur.execute(query, update_values)
                    rankings_updated += 1
                else:
                    # Insert new ranking
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
    
    print(f"Concurs updated: {concurs_updated} editions")
    print(f"  - Rankings: {rankings_inserted} inserted, {rankings_updated} updated")
    if unmatched_colles:
        print(f"Unmatched colles: {sorted(unmatched_colles)}")

def update_general_info(general_info_file_path: str):
    """Update general info data idempotently"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Updating general info...")
    
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
    updated_count = 0
    
    # Get existing records
    cur.execute("SELECT line_number, category, text FROM general_info")
    existing_records = {(row[0], row[1]): row[2] for row in cur.fetchall()}
    
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
        
        # If we have a category and the line is not empty, insert/update it
        if current_category and line and not line.startswith(tuple(categories.values())):
            key = (line_number, current_category)
            existing_text = existing_records.get(key)
            
            if existing_text:
                # Update if text changed
                if existing_text != line:
                    cur.execute("""
                        UPDATE general_info 
                        SET text = %s 
                        WHERE line_number = %s AND category = %s
                    """, (line, line_number, current_category))
                    updated_count += 1
            else:
                # Insert new
                cur.execute("""
                    INSERT INTO general_info (line_number, text, category)
                    VALUES (%s, %s, %s)
                """, (line_number, line, current_category))
                inserted_count += 1
    
    conn.commit()
    conn.close()
    print(f"General info updated: {inserted_count} inserted, {updated_count} updated")

def main():
    """Main function to update database idempotently"""
    
    print("Idempotent Database Update")
    print("=" * 50)
    
    if not DATABASE_URL:
        print("DATABASE_URL not set in .env file")
        return
    
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
        # Update data in order (respecting foreign key dependencies)
        print("\nUpdating data...")
        
        # 1. Update colles first (referenced by other tables)
        update_colles(str(local_files["colles_castelleres.json"]))
        
        # 2. Update puntuacions (independent)
        update_puntuacions(str(local_files["puntuacions.json"]))
        
        # 3. Update actuacions (references colles)
        update_actuacions(str(local_files["castellers_data.json"]))
        
        # 4. Update concurs data (references colles)
        update_concurs(
            str(local_files["concurs/concurs_ranking_clean.json"]),
            str(local_files["concurs_de_castells_editions.json"])
        )
        
        # 5. Update general info (independent)
        update_general_info(str(local_files["castellers_info_basic.txt"]))
        
        print("\n✅ Database update completed successfully!")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")
        raise

if __name__ == "__main__":
    main()

