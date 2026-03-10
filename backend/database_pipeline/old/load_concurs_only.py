#!/usr/bin/env python3
"""
Load Only Concurs Data to Supabase
Standalone script to load just concurs data
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
    
    # Try reverse partial match - check if colla_name contains any colla name
    cur.execute("SELECT id, name FROM colles WHERE name LIKE %s", (f"%{colla_name}%",))
    result = cur.fetchone()
    if result:
        print(f"Reverse partial match found: '{colla_name}' -> '{result[1]}' (ID: {result[0]})")
        return result[0]
    
    return None

def load_concurs_to_supabase():
    """Load concurs data from JSON files to Supabase"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("📊 Loading concurs data...")
    
    # Check if files exist
    concurs_ranking_file = "data_basic/concurs/concurs_ranking_clean.json"
    concurs_editions_file = "data_basic/concurs_de_castells_editions.json"
    
    if not os.path.exists(concurs_ranking_file):
        print(f"⚠️ File {concurs_ranking_file} not found, skipping concurs data")
        return
    
    if not os.path.exists(concurs_editions_file):
        print(f"⚠️ File {concurs_editions_file} not found, skipping concurs data")
        return
    
    # Load ranking data
    with open(concurs_ranking_file, 'r', encoding='utf-8') as f:
        ranking_data = json.load(f)
    
    # Load editions data
    with open(concurs_editions_file, 'r', encoding='utf-8') as f:
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
    
    print(f"✅ Loaded {concurs_inserted} concurs editions and {rankings_inserted} rankings.")
    if unmatched_colles:
        print(f"Unmatched colles: {sorted(unmatched_colles)}")

def main():
    """Main function to load only concurs data"""
    
    print("🚀 Loading Concurs Data to Supabase")
    print("=" * 40)
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set in .env file")
        return
    
    try:
        load_concurs_to_supabase()
        print("\n🎉 Concurs data loaded successfully!")
        
    except Exception as e:
        print(f"❌ Error loading concurs data: {e}")
        raise

if __name__ == "__main__":
    main()
