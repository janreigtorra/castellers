#!/usr/bin/env python3
"""
load_colles_related_tables.py
Standalone script to populate colles-related tables:
- colles_wiki_info
- colles_wiki_texts
- colles_best_actuacions
- colles_best_castells

This script reads from the colles JSON file and populates these tables
for colles that already exist in the database.
"""

import json
import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
# Get the backend directory (parent of database_pipeline)
BACKEND_DIR = SCRIPT_DIR.parent
# Data directory is in backend/data_basic
DATA_DIR = BACKEND_DIR / "data_basic"

def load_colles_related_tables():
    """Load colles-related tables from JSON file to Supabase"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("📊 Loading colles-related tables...")
    
    # Check if file exists
    colles_file = DATA_DIR / "colles_castelleres.json"
    
    if not colles_file.exists():
        print(f"⚠️  File {colles_file} not found, skipping")
        return
    
    # Load JSON data
    with open(colles_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    colles = data.get("colles", data)
    
    # Delete existing data from related tables for fresh reload
    print("🧹 Clearing related colles tables...")
    cur.execute("DELETE FROM colles_wiki_info")
    deleted_wiki_info = cur.rowcount
    cur.execute("DELETE FROM colles_wiki_texts")
    deleted_wiki_texts = cur.rowcount
    cur.execute("DELETE FROM colles_best_actuacions")
    deleted_best_actuacions = cur.rowcount
    cur.execute("DELETE FROM colles_best_castells")
    deleted_best_castells = cur.rowcount
    conn.commit()
    print(f"✅ Cleared: {deleted_wiki_info} wiki_info, {deleted_wiki_texts} wiki_texts, "
          f"{deleted_best_actuacions} best_actuacions, {deleted_best_castells} best_castells")
    
    # Reset sequences
    try:
        cur.execute("ALTER SEQUENCE colles_wiki_info_id_seq RESTART WITH 1")
        cur.execute("ALTER SEQUENCE colles_wiki_texts_id_seq RESTART WITH 1")
        cur.execute("ALTER SEQUENCE colles_best_actuacions_id_seq RESTART WITH 1")
        cur.execute("ALTER SEQUENCE colles_best_castells_id_seq RESTART WITH 1")
        conn.commit()
        print("✅ Sequences reset")
    except Exception as e:
        print(f"⚠️  Warning resetting sequences: {e}")
    
    wiki_info_count = 0
    wiki_texts_count = 0
    best_actuacions_count = 0
    best_castells_count = 0
    colles_processed = 0
    colles_not_found = 0
    
    print(f"\n📝 Processing {len(colles)} colles...")
    
    for colla in colles:
        colla_id = colla.get("colla_id")
        colla_name = colla.get("colla_name", "Unknown")
        
        if not colla_id:
            print(f"⚠️  Skipping colla without colla_id: {colla_name}")
            continue
        
        # Find colla in database
        cur.execute("SELECT id FROM colles WHERE colla_id = %s", (colla_id,))
        colla_row = cur.fetchone()
        
        if not colla_row:
            colles_not_found += 1
            if colles_not_found <= 5:  # Only print first 5 to avoid spam
                print(f"⚠️  Colla not found in database: {colla_name} (colla_id: {colla_id})")
            continue
        
        colla_fk = colla_row[0]
        colles_processed += 1
        
        try:
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
                        print(f"❌ Error inserting wiki_info for {colla_name}: {e}")
                        conn.rollback()
                        break
            
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
                            print(f"❌ Error inserting wiki_text for {colla_name}: {e}")
                            conn.rollback()
                            break
            
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
                    print(f"❌ Error inserting best_actuacio for {colla_name}: {e}")
                    conn.rollback()
                    break
            
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
                    print(f"❌ Error inserting best_castell for {colla_name}: {e}")
                    conn.rollback()  # Rollback on error to continue processing
                    break  # Break out of best_castells loop for this colla
            
            # Commit after each colla to avoid transaction issues
            conn.commit()
                    
        except Exception as e:
            print(f"❌ Error processing colla {colla_name}: {e}")
            conn.rollback()
            continue
    
    # Final commit
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("✅ Load completed!")
    print(f"📊 Colles processed: {colles_processed}")
    if colles_not_found > 0:
        print(f"⚠️  Colles not found in database: {colles_not_found}")
    print(f"\n📈 Records inserted:")
    print(f"   - Wiki info: {wiki_info_count}")
    print(f"   - Wiki texts: {wiki_texts_count}")
    print(f"   - Best actuacions: {best_actuacions_count}")
    print(f"   - Best castells: {best_castells_count}")

def main():
    """Main function to load colles-related tables"""
    
    print("🚀 Loading Colles-Related Tables to Supabase")
    print("=" * 50)
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set in .env file")
        return
    
    try:
        load_colles_related_tables()
        print("\n🎉 Colles-related tables loaded successfully!")
        
    except Exception as e:
        print(f"❌ Error loading colles-related tables: {e}")
        raise

if __name__ == "__main__":
    main()

