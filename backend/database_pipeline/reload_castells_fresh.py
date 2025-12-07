#!/usr/bin/env python3
"""
reload_castells_fresh.py
Simple script that deletes everything from castells table and reloads it fresh.
Downloads actuacions data from Supabase Storage and reloads castells cleanly.
"""

import json
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

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

def reload_castells_fresh():
    """Delete everything from castells table and reload it fresh"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Reloading castells table fresh...")
    
    # First, check current count
    cur.execute("SELECT COUNT(*) FROM castells")
    current_count = cur.fetchone()[0]
    print(f"Current castells count: {current_count}")
    
    # Delete everything from castells table
    print("Deleting all castells...")
    cur.execute("DELETE FROM castells")
    deleted_count = cur.rowcount
    print(f"Deleted {deleted_count} castells")
    
    # Reset the sequence to start from 1
    cur.execute("ALTER SEQUENCE castells_id_seq RESTART WITH 1")
    print("Castells sequence reset")
    
    conn.commit()
    
    # Use local file instead of downloading from storage
    print("Using local actuacions data...")
    actuacions_file = "data_basic/castellers_data.json"
    
    if not os.path.exists(actuacions_file):
        print(f"Error: Local file {actuacions_file} not found")
        return
    
    try:
        print("Loading actuacions fresh...")
        
        with open(actuacions_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        events = data.get("events", data)
        
        # Process events in batches to avoid timeouts
        batch_size = 100
        total_castells_inserted = 0
        
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
                        event.get("name"),
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
                        
                        # Insert castells fresh (no conflicts, no duplicates)
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
                            total_castells_inserted += 1
                    
                except Exception as e:
                    print(f"Error with event {event.get('name', 'Unknown')}: {e}")
                    conn.rollback()
                    continue
            
            # Commit batch
            conn.commit()
            print(f"Processed batch {i//batch_size + 1}/{(len(events) + batch_size - 1)//batch_size}")
        
        # Final count
        cur.execute("SELECT COUNT(*) FROM castells")
        final_count = cur.fetchone()[0]
        
        conn.close()
        
        print(f"Castells reload completed!")
        print(f"Events processed: {len(events)}")
        print(f"Total castells inserted: {total_castells_inserted}")
        print(f"Final castells count: {final_count}")
        
    except Exception as e:
        print(f"Error loading actuacions: {e}")
        conn.close()
        raise

def main():
    """Main function to reload castells fresh"""
    
    print("Reloading Castells Fresh")
    print("=" * 25)
    
    if not DATABASE_URL:
        print("DATABASE_URL not set in .env file")
        return
    
    try:
        reload_castells_fresh()
        print("\nCastells reload completed successfully!")
        
    except Exception as e:
        print(f"Error reloading castells: {e}")
        raise

if __name__ == "__main__":
    main()
