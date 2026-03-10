#!/usr/bin/env python3
"""
add_new_actuacions_only.py
Adds ONLY new events to the database. Does NOT update existing events.
Fast script for adding scraped events without touching anything else.
"""

import json
import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent
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
        return result[0]
    
    return None

def add_new_actuacions(actuacions_file_path: str):
    """Add ONLY new events - skip existing ones entirely"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Adding new actuacions (insert only, no updates)...")
    
    with open(actuacions_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    events = data.get("events", data)
    total_events = len(events)
    
    # Get existing event_ids from database
    print("Fetching existing event IDs from database...")
    cur.execute("SELECT event_id FROM events")
    existing_event_ids = {row[0] for row in cur.fetchall()}
    print(f"Found {len(existing_event_ids)} existing events in database")
    
    # Filter to only new events
    new_events = [e for e in events if e.get("event_id") not in existing_event_ids]
    print(f"Found {len(new_events)} new events to add (out of {total_events} total)")
    
    if not new_events:
        print("✅ No new events to add. Database is up to date!")
        conn.close()
        return
    
    events_inserted = 0
    event_colles_inserted = 0
    castells_inserted = 0
    
    # Process only new events in batches
    batch_size = 100
    for i in range(0, len(new_events), batch_size):
        batch = new_events[i:i+batch_size]
        
        for event in batch:
            try:
                # Insert new event (no ON CONFLICT - we already filtered)
                cur.execute("""
                    INSERT INTO events (event_id, name, date, place, city, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    event.get("event_id"),
                    event.get("event_name"),
                    event.get("date"),
                    event.get("place"),
                    event.get("city"),
                    event.get("scraped_at")
                ))
                events_inserted += 1
                
                # Get event ID
                cur.execute("SELECT id FROM events WHERE event_id = %s", (event.get("event_id"),))
                event_row = cur.fetchone()
                if not event_row:
                    continue
                event_id = event_row[0]
                
                # Process colles for this event
                colles = event.get("colles", [])
                for colla in colles:
                    colla_name = colla.get("colla_name")
                    if not colla_name:
                        continue
                    
                    # Find colla ID
                    colla_id = find_colla_id(colla_name, cur)
                    if not colla_id:
                        print(f"  Warning: Could not find colla '{colla_name}'")
                        continue
                    
                    # Insert event-colla relationship
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
                    
                    # Insert castells
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
                        castells_inserted += 1
                
            except Exception as e:
                print(f"Error with event {event.get('event_name', 'Unknown')}: {e}")
                conn.rollback()
                continue
        
        # Commit batch
        conn.commit()
        print(f"Processed batch {i//batch_size + 1}/{(len(new_events) + batch_size - 1)//batch_size}")
    
    conn.close()
    
    print("\n" + "=" * 50)
    print("✅ Done!")
    print(f"   - New events inserted: {events_inserted}")
    print(f"   - Event-colla relationships: {event_colles_inserted}")
    print(f"   - Castells inserted: {castells_inserted}")

def main():
    print("Add New Actuacions Only")
    print("=" * 50)
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set in .env file")
        return
    
    actuacions_file = DATA_DIR / "castellers_data.json"
    
    if not actuacions_file.exists():
        print(f"❌ File not found: {actuacions_file}")
        return
    
    print(f"📂 Reading from: {actuacions_file}")
    add_new_actuacions(str(actuacions_file))

if __name__ == "__main__":
    main()
