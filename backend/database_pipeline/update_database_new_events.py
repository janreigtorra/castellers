#!/usr/bin/env python3
"""
update_database_new_events.py
Database update script that ONLY adds NEW events.
Does NOT modify existing events, even if they're incomplete.
Safe to run multiple times - only inserts new data.
"""

import json
import psycopg2
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
# Get the backend directory (parent of database_pipeline)
BACKEND_DIR = SCRIPT_DIR.parent
# Data directory is in backend/data_basic
DATA_DIR = BACKEND_DIR / "data_basic"

# Add backend directory to path for imports
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DATABASE_URL = os.getenv("DATABASE_URL")

# FROM_DATE: Only process events from this date onwards (format: DD/MM/YYYY)
FROM_DATE = "01/12/2025"  # Change this to the date you want to start from

def parse_date(date_str):
    """Parse date string in DD/MM/YYYY format to datetime object"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        return None

def date_greater_or_equal(date1_str, date2_str):
    """Check if date1 >= date2 (both in DD/MM/YYYY format)"""
    d1 = parse_date(date1_str)
    d2 = parse_date(date2_str)
    if not d1 or not d2:
        return False
    return d1 >= d2

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

# Import update functions from the original file
def update_colles(colles_file_path: str):
    """Update colles data idempotently - OPTIMIZED VERSION"""
    from database_pipeline.update_database_idempotent import update_colles as _update_colles
    return _update_colles(colles_file_path)

def update_puntuacions(puntuacions_file_path: str):
    """Update puntuacions data idempotently"""
    from database_pipeline.update_database_idempotent import update_puntuacions as _update_puntuacions
    return _update_puntuacions(puntuacions_file_path)

def update_concurs(concurs_ranking_file_path: str, concurs_editions_file_path: str):
    """Update concurs data idempotently"""
    from database_pipeline.update_database_idempotent import update_concurs as _update_concurs
    return _update_concurs(concurs_ranking_file_path, concurs_editions_file_path)

def update_general_info(general_info_file_path: str):
    """Update general info data idempotently"""
    from database_pipeline.update_database_idempotent import update_general_info as _update_general_info
    return _update_general_info(general_info_file_path)

def update_actuacions_new_only(actuacions_file_path: str, from_date: str = None):
    """Update actuacions data - ONLY NEW EVENTS, NO UPDATES TO EXISTING EVENTS
    
    Args:
        actuacions_file_path: Path to the JSON file with events
        from_date: Only process events from this date onwards (DD/MM/YYYY format). 
                   If None, uses the FROM_DATE global variable.
    """
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Updating actuacions (NEW EVENTS ONLY)...")
    
    # Use parameter or global variable
    cutoff_date = from_date or FROM_DATE
    if cutoff_date:
        print(f"📅 Filtering events from {cutoff_date} onwards...")
    
    with open(actuacions_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    all_events = data.get("events", data)
    
    # Filter events by date if FROM_DATE is set
    if cutoff_date:
        events = [
            event for event in all_events 
            if event.get("date") and date_greater_or_equal(event.get("date"), cutoff_date)
        ]
        print(f"📊 Filtered to {len(events)} events from {cutoff_date} onwards (out of {len(all_events)} total)")
    else:
        events = all_events
        print(f"📊 Processing all {len(events)} events (no date filter)")
    
    # PERFORMANCE OPTIMIZATION 1: Pre-load existing events by CONTENT ONLY (not ID)
    # We ignore IDs completely and only match by (name, date, city) for flexibility
    print("Loading existing events from database (content-based matching)...")
    cur.execute("SELECT name, date, city FROM events")
    existing_events_by_content = set()
    for row in cur.fetchall():
        name, date, city = row
        # Create content-based key: (name, date, city) - normalize for matching
        if name and date:
            # Normalize: strip whitespace, handle None values, case-insensitive name
            content_key = (
                str(name).strip().lower(),  # Case-insensitive name matching
                str(date).strip(), 
                str(city).strip().lower() if city else ""  # Case-insensitive city
            )
            existing_events_by_content.add(content_key)
    
    print(f"Found {len(existing_events_by_content)} existing events in database (by content: name+date+city)")
    
    # PERFORMANCE OPTIMIZATION 2: Pre-load all colla IDs into cache
    print("Loading colla IDs into cache...")
    cur.execute("SELECT id, name FROM colles")
    colla_id_cache = {}
    for row in cur.fetchall():
        colla_id_cache[row[1]] = row[0]
        # Also cache normalized names
        normalized = normalize_colla_name(row[1])
        if normalized != row[1]:
            colla_id_cache[normalized] = row[0]
    print(f"Cached {len(colla_id_cache)} colla name mappings")
    
    events_inserted = 0
    event_colles_inserted = 0
    castells_inserted = 0
    
    # Filter to ONLY new events (not in database)
    # ONLY check by content (name, date, city) - IGNORE IDs completely for flexibility
    new_events = []
    skipped_by_content = 0
    
    for event in events:
        event_id_str = event.get("event_id")
        if not event_id_str:
            continue
        
        event_name = event.get("event_name", "").strip()
        event_date = event.get("date", "").strip()
        event_city = (event.get("city", "") or "").strip()
        
        # Skip if missing essential data
        if not event_name or not event_date:
            continue
        
        # Check if event exists by content (name, date, city) - case-insensitive
        # This is the ONLY check we do - we ignore IDs completely
        event_content_key = (
            event_name.lower(),  # Case-insensitive
            event_date,
            event_city.lower() if event_city else ""  # Case-insensitive
        )
        
        if event_content_key in existing_events_by_content:
            skipped_by_content += 1
            continue
        
        # Only process truly new events
        new_events.append(event)
    
    print(f"Found {len(new_events)} NEW events to process (after date filter)")
    print(f"  - Skipped {skipped_by_content} events (matched by content: name+date+city)")
    if new_events:
        print(f"  - First new event: '{new_events[0].get('event_name')}' on {new_events[0].get('date')}")
    
    if not new_events:
        print("No new events to process!")
        conn.close()
        return
    
    # Process events in batches to avoid timeouts
    batch_size = 100
    for i in range(0, len(new_events), batch_size):
        batch = new_events[i:i+batch_size]
        
        for event in batch:
            try:
                original_event_id = event.get("event_id")
                event_name = event.get("event_name")
                event_date = event.get("date")
                event_place = event.get("place")
                event_city = event.get("city")
                event_scraped_at = event.get("scraped_at")
                
                # Since we're matching by content (not ID), generate a stable event_id from content
                # This ensures we don't have ID conflicts
                import hashlib
                content_for_hash = f"{event_name}|{event_date}|{event_city}".encode('utf-8')
                content_hash = hashlib.md5(content_for_hash).hexdigest()[:12]
                stable_event_id = f"event_{content_hash}"
                
                # Check if this stable ID already exists
                cur.execute("SELECT id FROM events WHERE event_id = %s", (stable_event_id,))
                existing_event = cur.fetchone()
                
                if existing_event:
                    # Event already exists with this stable ID (shouldn't happen since we checked by content)
                    # But just in case, skip it
                    print(f"⚠️  Event already exists with stable ID {stable_event_id}: '{event_name}' on {event_date}")
                    continue
                
                # Insert new event with the stable ID
                cur.execute("""
                    INSERT INTO events (event_id, name, date, place, city, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    stable_event_id,
                    event_name,
                    event_date,
                    event_place,
                    event_city,
                    event_scraped_at
                ))
                
                result = cur.fetchone()
                if not result:
                    print(f"Warning: Failed to insert event {stable_event_id}")
                    continue
                
                event_id = result[0]
                events_inserted += 1
                
                if stable_event_id != original_event_id:
                    print(f"✓ Using stable ID {stable_event_id} (original was {original_event_id}) for '{event_name}' on {event_date}")
                
                # Process colles for this event
                colles = event.get("colles", [])
                for colla in colles:
                    colla_name = colla.get("colla_name")
                    if not colla_name:
                        continue
                    
                    # Use cached colla ID
                    colla_id = colla_id_cache.get(colla_name)
                    if not colla_id:
                        # Fallback to find_colla_id if not in cache
                        colla_id = find_colla_id(colla_name, cur)
                        if colla_id:
                            # Add to cache for next time
                            colla_id_cache[colla_name] = colla_id
                    
                    if not colla_id:
                        print(f"Warning: Could not find colla '{colla_name}' in database")
                        continue
                    
                    # Insert event-colla relationship (idempotent) with RETURNING
                    cur.execute("""
                        INSERT INTO event_colles (event_fk, colla_fk)
                        VALUES (%s, %s)
                        ON CONFLICT (event_fk, colla_fk) DO NOTHING
                        RETURNING id
                    """, (event_id, colla_id))
                    
                    result = cur.fetchone()
                    if result:
                        event_colla_id = result[0]
                        event_colles_inserted += 1
                    else:
                        # Already exists, get the ID
                        cur.execute("""
                            SELECT id FROM event_colles 
                            WHERE event_fk = %s AND colla_fk = %s
                        """, (event_id, colla_id))
                        event_colla_row = cur.fetchone()
                        if not event_colla_row:
                            continue
                        event_colla_id = event_colla_row[0]
                    
                    # Insert castells for this event-colla
                    castells = colla.get("castells", [])
                    if not castells:
                        continue
                    
                    # Bulk load existing castells for this event_colla to avoid duplicates
                    cur.execute("""
                        SELECT castell_name, status, raw_text FROM castells 
                        WHERE event_colla_fk = %s
                    """, (event_colla_id,))
                    existing_castells = {(row[0], row[1], row[2]) for row in cur.fetchall()}
                    
                    # Insert only new castells
                    for castell in castells:
                        castell_name = castell.get("castell_name")
                        status = castell.get("status")
                        raw_text = castell.get("raw_text")
                        
                        signature = (castell_name, status, raw_text)
                        if signature not in existing_castells:
                            cur.execute("""
                                INSERT INTO castells (event_colla_fk, castell_name, status, raw_text)
                                VALUES (%s, %s, %s, %s)
                            """, (event_colla_id, castell_name, status, raw_text))
                            castells_inserted += 1
                            # Add to set to avoid duplicate inserts in same batch
                            existing_castells.add(signature)
                
            except Exception as e:
                print(f"Error with event {event.get('event_name', 'Unknown')}: {e}")
                import traceback
                traceback.print_exc()
                conn.rollback()
                continue
        
        # Commit batch
        conn.commit()
        print(f"Processed batch {i//batch_size + 1}/{(len(new_events) + batch_size - 1)//batch_size} "
              f"({events_inserted} new events, {castells_inserted} castells)")
    
    conn.close()
    print(f"Actuacions updated: {events_inserted} new events inserted")
    print(f"  - Event-colles relationships: {event_colles_inserted} inserted")
    print(f"  - Castells: {castells_inserted} inserted")

def main():
    """Main function to update database with NEW EVENTS ONLY"""
    
    print("Database Update - NEW EVENTS ONLY")
    print("=" * 50)
    print("⚠️  This pipeline ONLY adds new events.")
    print("⚠️  Existing events will NOT be modified, even if incomplete.")
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
        
        # 3. Update actuacions - NEW EVENTS ONLY (references colles)
        # Pass FROM_DATE as parameter (or None to use global variable)
        update_actuacions_new_only(str(local_files["castellers_data.json"]), from_date=FROM_DATE)
        
        # 4. Update concurs data (references colles)
        update_concurs(
            str(local_files["concurs/concurs_ranking_clean.json"]),
            str(local_files["concurs_de_castells_editions.json"])
        )
        
        # 5. Update general info (independent)
        update_general_info(str(local_files["castellers_info_basic.txt"]))
        
        print("\n✅ Database update completed successfully!")
        print("   (Only new events were added, existing events were not modified)")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")
        raise

if __name__ == "__main__":
    main()

