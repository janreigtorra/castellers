#!/usr/bin/env python3
"""
clean_all_tables.py
Deletes all data from all tables in the correct order (respecting foreign keys)
Use this before running create_complete_supabase.py for a fresh reload
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def clean_all_tables():
    """Delete all data from all tables in the correct order"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Cleaning all tables...")
    print("=" * 50)
    
    # Delete in reverse dependency order (children first, then parents)
    # Tables with foreign keys first, then independent tables
    
    tables_to_clean = [
        # Child tables (have foreign keys)
        ("castells", "castells_id_seq"),
        ("event_colles", None),
        ("concurs_rankings", None),
        ("colles_wiki_info", None),
        ("colles_wiki_texts", None),
        ("colles_best_actuacions", None),
        ("colles_best_castells", None),
        # Parent tables (referenced by others)
        ("events", "events_id_seq"),
        ("concurs", "concurs_id_seq"),
        ("colles", "colles_id_seq"),
        # Independent tables
        ("puntuacions", None),
        ("general_info", "general_info_id_seq"),
    ]
    
    total_deleted = 0
    
    for table_name, sequence_name in tables_to_clean:
        try:
            # Get count before deletion
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            
            if count > 0:
                # Delete all rows
                cur.execute(f"DELETE FROM {table_name}")
                deleted = cur.rowcount
                total_deleted += deleted
                print(f"✅ Deleted {deleted} rows from {table_name}")
                
                # Reset sequence if specified
                if sequence_name:
                    cur.execute(f"ALTER SEQUENCE {sequence_name} RESTART WITH 1")
                    print(f"   ↳ Reset sequence {sequence_name}")
            else:
                print(f"⏭️  {table_name} is already empty")
                
        except Exception as e:
            print(f"⚠️  Error cleaning {table_name}: {e}")
            # Continue with other tables
    
    conn.commit()
    conn.close()
    
    print("=" * 50)
    print(f"🎉 Cleanup complete! Deleted {total_deleted} total rows")
    print("\n💡 You can now run create_complete_supabase.py for a fresh reload")

def main():
    """Main function"""
    
    print("🚀 Clean All Tables")
    print("=" * 50)
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set in .env file")
        return
    
    try:
        clean_all_tables()
        print("\n✅ All tables cleaned successfully!")
        
    except Exception as e:
        print(f"❌ Error cleaning tables: {e}")
        raise

if __name__ == "__main__":
    main()

