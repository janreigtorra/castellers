import sqlite3
import psycopg2
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

def migrate_schema():
    """Create tables in Supabase using your existing schema"""
    
    # Connect to Supabase PostgreSQL
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Your existing schema from create_db.py
    schema_sql = """
    -- Enable UUID extension
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    
    -- Colles table
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
    
    -- Colles wiki info
    CREATE TABLE IF NOT EXISTS colles_wiki_info (
        id SERIAL PRIMARY KEY,
        colla_fk INTEGER REFERENCES colles(id) ON DELETE CASCADE,
        key TEXT,
        value TEXT
    );
    
    -- Colles wiki texts
    CREATE TABLE IF NOT EXISTS colles_wiki_texts (
        id SERIAL PRIMARY KEY,
        colla_fk INTEGER REFERENCES colles(id) ON DELETE CASCADE,
        text TEXT
    );
    
    -- Colles best actuacions
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
    
    -- Colles best castells
    CREATE TABLE IF NOT EXISTS colles_best_castells (
        id SERIAL PRIMARY KEY,
        colla_fk INTEGER REFERENCES colles(id) ON DELETE CASCADE,
        castell_name TEXT,
        descarregats INTEGER,
        carregats INTEGER,
        intents INTEGER,
        intents_descarregats INTEGER
    );
    
    -- General info table
    CREATE TABLE IF NOT EXISTS general_info (
        id SERIAL PRIMARY KEY,
        line_number INTEGER,
        text TEXT,
        category TEXT
    );
    
    -- Events table
    CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY,
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
    
    -- Event colles junction table
    CREATE TABLE IF NOT EXISTS event_colles (
        id SERIAL PRIMARY KEY,
        event_fk INTEGER REFERENCES events(id) ON DELETE CASCADE,
        colla_fk INTEGER REFERENCES colles(id) ON DELETE CASCADE,
        UNIQUE(event_fk, colla_fk)
    );
    
    -- Castells table
    CREATE TABLE IF NOT EXISTS castells (
        id SERIAL PRIMARY KEY,
        event_colla_fk INTEGER REFERENCES event_colles(id) ON DELETE CASCADE,
        castell_name TEXT,
        status TEXT,
        raw_text TEXT
    );
    
    -- Puntuacions table
    CREATE TABLE IF NOT EXISTS puntuacions (
        id SERIAL PRIMARY KEY,
        castell_code TEXT UNIQUE,
        castell_code_external TEXT,
        punts_descarregat INTEGER,
        punts_carregat INTEGER,
        castell_code_name TEXT
    );
    
    -- Concurs table
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
        paragraphs_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Concurs rankings table
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
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_colles_name ON colles(name);
    CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
    CREATE INDEX IF NOT EXISTS idx_castells_name ON castells(castell_name);
    CREATE INDEX IF NOT EXISTS idx_punts_code ON puntuacions(castell_code);
    CREATE INDEX IF NOT EXISTS idx_concurs_edition ON concurs(edition);
    CREATE INDEX IF NOT EXISTS idx_concurs_rankings_position ON concurs_rankings(position);
    CREATE INDEX IF NOT EXISTS idx_concurs_rankings_colla ON concurs_rankings(colla_fk);
    CREATE INDEX IF NOT EXISTS idx_concurs_rankings_concurs ON concurs_rankings(concurs_fk);
    """
    
    # Execute schema
    cur.execute(schema_sql)
    conn.commit()
    print("✅ Schema created successfully!")
    
    conn.close()

def migrate_data():
    """Migrate data from SQLite to Supabase"""
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect('database.db')
    sqlite_conn.row_factory = sqlite3.Row
    
    supabase_conn = psycopg2.connect(DATABASE_URL)
    supabase_cur = supabase_conn.cursor()
    
    try:
        # Get table counts for progress tracking
        table_counts = {}
        tables = ['colles', 'events', 'colles_wiki_info', 'colles_wiki_texts', 
                 'colles_best_actuacions', 'colles_best_castells', 'event_colles',
                 'castells', 'puntuacions', 'concurs', 'concurs_rankings', 'general_info']
        
        for table in tables:
            try:
                count = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                table_counts[table] = count
                print(f"📊 {table}: {count} records")
            except sqlite3.OperationalError:
                print(f"⚠️  Table {table} not found, skipping...")
                table_counts[table] = 0
        
        total_records = sum(table_counts.values())
        print(f"\n🚀 Starting migration of {total_records} total records...\n")
    
        # Check if colles already has data
        supabase_cur.execute("SELECT COUNT(*) FROM colles")
        existing_colles = supabase_cur.fetchone()[0]
    
    # Migrate colles
        if table_counts['colles'] > 0 and existing_colles == 0:
    print("Migrating colles...")
    colles = sqlite_conn.execute("SELECT * FROM colles").fetchall()
            for i, colla in enumerate(colles, 1):
                try:
        supabase_cur.execute("""
            INSERT INTO colles (colla_id, name, logo_url, website, instagram, facebook, 
                              wikipedia_url, wikipedia_title, wikipedia_description, 
                              scraped_at, detail_url, basic_info_json, first_actuacio, 
                              last_actuacio, best_castells_json, wiki_stats_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            colla['colla_id'], colla['name'], colla['logo_url'], colla['website'],
            colla['instagram'], colla['facebook'], colla['wikipedia_url'],
            colla['wikipedia_title'], colla['wikipedia_description'], colla['scraped_at'],
            colla['detail_url'], colla['basic_info_json'], colla['first_actuacio'],
            colla['last_actuacio'], colla['best_castells_json'], colla['wiki_stats_json']
        ))
                    if i % 10 == 0:
                        print(f"  ✅ Migrated {i}/{len(colles)} colles")
                except Exception as e:
                    print(f"  ❌ Error migrating colla {i}: {e}")
            print(f"✅ Colles migration completed: {len(colles)} records")
        else:
            print(f"⏭️  Colles already migrated ({existing_colles} records), skipping...")
    
    # Migrate events
        if table_counts['events'] > 0:
    print("Migrating events...")
    events = sqlite_conn.execute("SELECT * FROM events").fetchall()
            for i, event in enumerate(events, 1):
                try:
        supabase_cur.execute("""
            INSERT INTO events (event_id, name, date, time, place, city, 
                              raw_date_location, total_colles, total_castells, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            event['event_id'], event['name'], event['date'], event['time'],
            event['place'], event['city'], event['raw_date_location'],
            event['total_colles'], event['total_castells'], event['scraped_at']
        ))
                    if i % 100 == 0:
                        print(f"  ✅ Migrated {i}/{len(events)} events")
                except Exception as e:
                    print(f"  ❌ Error migrating event {i}: {e}")
            print(f"✅ Events migration completed: {len(events)} records")
        
        # Migrate colles_wiki_info
        if table_counts['colles_wiki_info'] > 0:
            print("Migrating colles_wiki_info...")
            wiki_info = sqlite_conn.execute("SELECT * FROM colles_wiki_info").fetchall()
            for i, info in enumerate(wiki_info, 1):
                try:
                    supabase_cur.execute("""
                        INSERT INTO colles_wiki_info (colla_fk, key, value)
                        VALUES (%s, %s, %s)
                    """, (info['colla_fk'], info['key'], info['value']))
                    if i % 50 == 0:
                        print(f"  ✅ Migrated {i}/{len(wiki_info)} wiki info records")
                except Exception as e:
                    print(f"  ❌ Error migrating wiki info {i}: {e}")
            print(f"✅ Colles wiki info migration completed: {len(wiki_info)} records")
        
        # Migrate colles_wiki_texts
        if table_counts['colles_wiki_texts'] > 0:
            print("Migrating colles_wiki_texts...")
            wiki_texts = sqlite_conn.execute("SELECT * FROM colles_wiki_texts").fetchall()
            for i, text in enumerate(wiki_texts, 1):
                try:
                    supabase_cur.execute("""
                        INSERT INTO colles_wiki_texts (colla_fk, text)
                        VALUES (%s, %s)
                    """, (text['colla_fk'], text['text']))
                    if i % 50 == 0:
                        print(f"  ✅ Migrated {i}/{len(wiki_texts)} wiki text records")
                except Exception as e:
                    print(f"  ❌ Error migrating wiki text {i}: {e}")
            print(f"✅ Colles wiki texts migration completed: {len(wiki_texts)} records")
        
        # Migrate colles_best_actuacions
        if table_counts['colles_best_actuacions'] > 0:
            print("Migrating colles_best_actuacions...")
            best_actuacions = sqlite_conn.execute("SELECT * FROM colles_best_actuacions").fetchall()
            for i, actuacio in enumerate(best_actuacions, 1):
                try:
                    supabase_cur.execute("""
                        INSERT INTO colles_best_actuacions (colla_fk, rank, date, location, diada, actuacio, points)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        actuacio['colla_fk'], actuacio['rank'], actuacio['date'], 
                        actuacio['location'], actuacio['diada'], actuacio['actuacio'], actuacio['points']
                    ))
                    if i % 50 == 0:
                        print(f"  ✅ Migrated {i}/{len(best_actuacions)} best actuacions")
                except Exception as e:
                    print(f"  ❌ Error migrating best actuacio {i}: {e}")
            print(f"✅ Colles best actuacions migration completed: {len(best_actuacions)} records")
        
        # Migrate colles_best_castells
        if table_counts['colles_best_castells'] > 0:
            print("Migrating colles_best_castells...")
            best_castells = sqlite_conn.execute("SELECT * FROM colles_best_castells").fetchall()
            for i, castell in enumerate(best_castells, 1):
                try:
                    supabase_cur.execute("""
                        INSERT INTO colles_best_castells (colla_fk, castell_name, descarregats, carregats, intents, intents_descarregats)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        castell['colla_fk'], castell['castell_name'], castell['descarregats'],
                        castell['carregats'], castell['intents'], castell['intents_descarregats']
                    ))
                    if i % 50 == 0:
                        print(f"  ✅ Migrated {i}/{len(best_castells)} best castells")
                except Exception as e:
                    print(f"  ❌ Error migrating best castell {i}: {e}")
            print(f"✅ Colles best castells migration completed: {len(best_castells)} records")
        
        # Migrate event_colles
        if table_counts['event_colles'] > 0:
            print("Migrating event_colles...")
            event_colles = sqlite_conn.execute("SELECT * FROM event_colles").fetchall()
            for i, ec in enumerate(event_colles, 1):
                try:
                    supabase_cur.execute("""
                        INSERT INTO event_colles (event_fk, colla_fk)
                        VALUES (%s, %s)
                    """, (ec['event_fk'], ec['colla_fk']))
                    if i % 100 == 0:
                        print(f"  ✅ Migrated {i}/{len(event_colles)} event_colles")
                except Exception as e:
                    print(f"  ❌ Error migrating event_colla {i}: {e}")
            print(f"✅ Event colles migration completed: {len(event_colles)} records")
        
        # Migrate castells
        if table_counts['castells'] > 0:
            print("Migrating castells...")
            castells = sqlite_conn.execute("SELECT * FROM castells").fetchall()
            for i, castell in enumerate(castells, 1):
                try:
                    supabase_cur.execute("""
                        INSERT INTO castells (event_colla_fk, castell_name, status, raw_text)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        castell['event_colla_fk'], castell['castell_name'], 
                        castell['status'], castell['raw_text']
                    ))
                    if i % 100 == 0:
                        print(f"  ✅ Migrated {i}/{len(castells)} castells")
                except Exception as e:
                    print(f"  ❌ Error migrating castell {i}: {e}")
            print(f"✅ Castells migration completed: {len(castells)} records")
        
        # Migrate puntuacions
        if table_counts['puntuacions'] > 0:
            print("Migrating puntuacions...")
            puntuacions = sqlite_conn.execute("SELECT * FROM puntuacions").fetchall()
            for i, puntuacio in enumerate(puntuacions, 1):
                try:
                    supabase_cur.execute("""
                        INSERT INTO puntuacions (castell_code, castell_code_external, punts_descarregat, punts_carregat, castell_code_name)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        puntuacio['castell_code'], puntuacio['castell_code_external'],
                        puntuacio['punts_descarregat'], puntuacio['punts_carregat'], puntuacio['castell_code_name']
                    ))
                    if i % 50 == 0:
                        print(f"  ✅ Migrated {i}/{len(puntuacions)} puntuacions")
                except Exception as e:
                    print(f"  ❌ Error migrating puntuacio {i}: {e}")
            print(f"✅ Puntuacions migration completed: {len(puntuacions)} records")
        
        # Migrate concurs
        if table_counts['concurs'] > 0:
            print("Migrating concurs...")
            concurs = sqlite_conn.execute("SELECT * FROM concurs").fetchall()
            for i, concurs_item in enumerate(concurs, 1):
                try:
                    supabase_cur.execute("""
                        INSERT INTO concurs (edition, title, date, location, colla_guanyadora, num_colles, 
                                           castells_intentats, maxim_castell, espectadors, plaça, 
                                           infobox_json, paragraphs_json)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        concurs_item['edition'], concurs_item['title'], concurs_item['date'],
                        concurs_item['location'], concurs_item['colla_guanyadora'], concurs_item['num_colles'],
                        concurs_item['castells_intentats'], concurs_item['maxim_castell'], 
                        concurs_item['espectadors'], concurs_item['plaça'],
                        concurs_item['infobox_json'], concurs_item['paragraphs_json']
                    ))
                    if i % 10 == 0:
                        print(f"  ✅ Migrated {i}/{len(concurs)} concurs records")
                except Exception as e:
                    print(f"  ❌ Error migrating concurs {i}: {e}")
            print(f"✅ Concurs migration completed: {len(concurs)} records")
        
        # Migrate concurs_rankings
        if table_counts['concurs_rankings'] > 0:
            print("Migrating concurs_rankings...")
            rankings = sqlite_conn.execute("SELECT * FROM concurs_rankings").fetchall()
            for i, ranking in enumerate(rankings, 1):
                try:
                    supabase_cur.execute("""
                        INSERT INTO concurs_rankings (concurs_fk, colla_fk, position, colla_name, total_points, 
                                                    any, jornada, ronda_1_json, ronda_2_json, ronda_3_json, 
                                                    ronda_4_json, ronda_5_json, ronda_6_json, ronda_7_json, 
                                                    ronda_8_json, rondes_json)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        ranking['concurs_fk'], ranking['colla_fk'], ranking['position'], 
                        ranking['colla_name'], ranking['total_points'], ranking['any'], ranking['jornada'],
                        ranking['ronda_1_json'], ranking['ronda_2_json'], ranking['ronda_3_json'],
                        ranking['ronda_4_json'], ranking['ronda_5_json'], ranking['ronda_6_json'],
                        ranking['ronda_7_json'], ranking['ronda_8_json'], ranking['rondes_json']
                    ))
                    if i % 50 == 0:
                        print(f"  ✅ Migrated {i}/{len(rankings)} concurs rankings")
                except Exception as e:
                    print(f"  ❌ Error migrating concurs ranking {i}: {e}")
            print(f"✅ Concurs rankings migration completed: {len(rankings)} records")
        
        # Migrate general_info
        if table_counts['general_info'] > 0:
            print("Migrating general_info...")
            general_info = sqlite_conn.execute("SELECT * FROM general_info").fetchall()
            for i, info in enumerate(general_info, 1):
                try:
                    supabase_cur.execute("""
                        INSERT INTO general_info (line_number, text, category)
                        VALUES (%s, %s, %s)
                    """, (info['line_number'], info['text'], info['category']))
                    if i % 100 == 0:
                        print(f"  ✅ Migrated {i}/{len(general_info)} general info records")
                except Exception as e:
                    print(f"  ❌ Error migrating general info {i}: {e}")
            print(f"✅ General info migration completed: {len(general_info)} records")
        
        # Commit all changes
        supabase_conn.commit()
        print(f"\n🎉 Migration completed successfully!")
        print(f"📊 Total records migrated: {total_records}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        supabase_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        supabase_conn.close()

def verify_migration():
    """Verify that the migration was successful by comparing record counts"""
    print("\n🔍 Verifying migration...")
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect('database.db')
    sqlite_conn.row_factory = sqlite3.Row
    
    supabase_conn = psycopg2.connect(DATABASE_URL)
    supabase_cur = supabase_conn.cursor()
    
    tables = ['colles', 'events', 'colles_wiki_info', 'colles_wiki_texts', 
             'colles_best_actuacions', 'colles_best_castells', 'event_colles',
             'castells', 'puntuacions', 'concurs', 'concurs_rankings', 'general_info']
    
    all_good = True
    
    for table in tables:
        try:
            # Count SQLite records
            sqlite_count = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            
            # Count Supabase records
            supabase_cur.execute(f"SELECT COUNT(*) FROM {table}")
            supabase_count = supabase_cur.fetchone()[0]
            
            if sqlite_count == supabase_count:
                print(f"✅ {table}: {sqlite_count} records (match)")
            else:
                print(f"❌ {table}: SQLite={sqlite_count}, Supabase={supabase_count} (mismatch)")
                all_good = False
                
        except Exception as e:
            print(f"⚠️  {table}: Error verifying - {e}")
            all_good = False
    
    if all_good:
        print("\n🎉 All tables verified successfully!")
    else:
        print("\n⚠️  Some tables have mismatches. Please check the migration.")
    
    sqlite_conn.close()
    supabase_conn.close()

    return all_good

def test_supabase_connection():
    """Test the Supabase connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"✅ Connected to Supabase PostgreSQL: {version}")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return False

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = ['SUPABASE_URL', 'SUPABASE_ANON_KEY', 'DATABASE_URL']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file:")
        for var in missing_vars:
            print(f"  {var}=your_value_here")
        return False
    
    print("✅ All environment variables are set")
    return True

if __name__ == "__main__":
    print("🚀 Starting Supabase Migration Process")
    print("=" * 50)
    
    # Step 1: Check environment
    if not check_environment():
        print("\n❌ Environment check failed. Please fix the issues above.")
        exit(1)
    
    # Step 2: Test connection
    if not test_supabase_connection():
        print("\n❌ Connection test failed. Please check your Supabase credentials.")
        exit(1)
    
    # Step 3: Migrate schema
    print("\n📋 Step 1: Creating database schema...")
    try:
    migrate_schema()
    except Exception as e:
        print(f"\n❌ Schema migration failed: {e}")
        exit(1)
    
    # Step 4: Migrate data
    print("\n📊 Step 2: Migrating data...")
    try:
    migrate_data()
    except Exception as e:
        print(f"\n❌ Data migration failed: {e}")
        exit(1)
    
    # Step 5: Verify migration
    print("\n🔍 Step 3: Verifying migration...")
    if verify_migration():
        print("\n🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Update your application to use the DATABASE_URL")
        print("2. Test your SQL queries with the new PostgreSQL database")
        print("3. Deploy to production")
    else:
        print("\n⚠️  Migration completed with some issues. Please review the verification results.")