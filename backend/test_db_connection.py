#!/usr/bin/env python3
"""
Script robust per provar connexió a Supabase (Postgres).
"""
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
import socket
import psycopg2

load_dotenv()

def debug_print(msg):
    print(msg)

def convert_to_pooler_url(database_url: str) -> str:
    """Convert direct connection URL to Session Pooler URL (IPv4 compatible)"""
    parsed = urlparse(database_url)
    
    # Build new URL with pooler port (6543) and pgbouncer mode
    # The hostname stays the same, just change port
    pooler_url = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:6543{parsed.path}"
    
    # Add query parameters if they exist, otherwise add pgbouncer=true
    if parsed.query:
        pooler_url += f"?{parsed.query}&pgbouncer=true"
    else:
        pooler_url += "?pgbouncer=true"
    
    return pooler_url

def test_connection():
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            debug_print("❌ ERROR: la variable DATABASE_URL no està definida o és buida.")
            debug_print("🔎 Assegura't que .env està en el mateix directori i que has fet load_dotenv().")
            return False

        database_url = database_url.strip().strip('"').strip("'")
        debug_print(f"🔎 DATABASE_URL (raw): {database_url}")

        # Si l'usuari va posar directament un hostname en lloc d'una URL, ho tractem:
        if database_url.startswith("postgres") or database_url.startswith("postgresql://"):
            parsed = urlparse(database_url)
        else:
            # Potser només han posat el hostname (ex: db.xyz.supabase.co)
            parsed = urlparse("postgresql://" + database_url)

        hostname = parsed.hostname
        debug_print(f"📌 Parsed hostname: {hostname}")
        debug_print(f"📌 Parsed username: {parsed.username}")
        debug_print(f"📌 Parsed port: {parsed.port}")
        debug_print(f"📌 Parsed database: {parsed.path}")

        if not hostname:
            debug_print("❌ ERROR: No s'ha pogut extreure el hostname de DATABASE_URL.")
            return False

        # Try direct connection first (port 5432, requires IPv6)
        port = parsed.port or 5432
        debug_print(f"\n🔍 Attempting direct connection (port {port})...")
        debug_print("   ℹ️  Direct connections require IPv6. If this fails, we'll try Session Pooler.")
        
        # Paràmetres de connexió directa
        conn_params = {
            'host': hostname,
            'port': port,
            'database': parsed.path.lstrip('/') or 'postgres',
            'user': parsed.username or os.getenv('DB_USER') or 'postgres',
            'password': parsed.password or os.getenv('DB_PASSWORD'),
            'connect_timeout': 10,
            'sslmode': 'require'
        }

        if not conn_params['password']:
            debug_print("⚠️  No s'ha detectat contrasenya en la URL ni a DB_PASSWORD (env). Això pot fallar si la contrasenya no és proporcionada.")

        # Try direct connection first
        try:
            debug_print(f"🔒 Intentant connexió directa: host={conn_params['host']} port={conn_params['port']} database={conn_params['database']} user={conn_params['user']}")
            conn = psycopg2.connect(**conn_params)
            cur = conn.cursor()
            cur.execute("SELECT version();")
            version = cur.fetchone()
            debug_print(f"✅ Connexió directa exitosa! PostgreSQL version: {version[0]}")
            
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """)
            tables = cur.fetchall()
            debug_print(f"📋 Available tables: {[t[0] for t in tables]}")
            
            conn.close()
            return True
            
        except (psycopg2.OperationalError, socket.gaierror) as e:
            error_msg = str(e).lower()
            debug_print(f"❌ Connexió directa fallida: {e}")
            
            # Check if it's an IPv6/DNS issue
            if any(keyword in error_msg for keyword in ['could not translate host name', 'nodename', 'name or service not known', 'no answer']):
                debug_print("\n🔄 Switching to Session Pooler (IPv4 compatible, port 6543)...")
                debug_print("   ℹ️  Session Pooler is free and works on IPv4 networks!")
                
                # Convert to pooler URL
                pooler_url = convert_to_pooler_url(database_url)
                debug_print(f"🔎 Pooler URL: {pooler_url.replace(parsed.password or '', '***') if parsed.password else pooler_url}")
                
                # Parse pooler URL
                pooler_parsed = urlparse(pooler_url)
                
                # Connection parameters for pooler
                pooler_params = {
                    'host': pooler_parsed.hostname,
                    'port': 6543,
                    'database': pooler_parsed.path.lstrip('/') or 'postgres',
                    'user': pooler_parsed.username or os.getenv('DB_USER') or 'postgres',
                    'password': pooler_parsed.password or os.getenv('DB_PASSWORD'),
                    'connect_timeout': 10,
                    'sslmode': 'require'
                }
                
                # Test DNS resolution for pooler
                try:
                    infos = socket.getaddrinfo(pooler_params['host'], None, socket.AF_INET)
                    addresses = sorted({item[4][0] for item in infos})
                    debug_print(f"✅ IPv4 DNS resolution successful: {pooler_params['host']} -> {addresses}")
                except socket.gaierror as dns_e:
                    debug_print(f"❌ DNS Resolution failed for pooler: {dns_e}")
                    debug_print("\n" + "="*60)
                    debug_print("⚠️  PROBLEMA CRÍTIC: El hostname no es pot resoldre")
                    debug_print("="*60)
                    debug_print("\n📋 PASOS PER ARREGLAR-HO:")
                    debug_print("\n1️⃣  Verifica que el teu projecte Supabase estigui ACTIU:")
                    debug_print("   → Obre https://supabase.com/dashboard")
                    debug_print("   → Selecciona el teu projecte")
                    debug_print("   → Si veus 'Project is paused', clica 'Restore project'")
                    debug_print("   → Espera 1-2 minuts que el projecte s'activin")
                    debug_print("\n2️⃣  Obtingues les connexions correctes:")
                    debug_print("   → Dashboard → Settings → Database")
                    debug_print("   → Connection string → URI (Session mode) ← USA AQUESTA!")
                    debug_print("   → Copia la URL completa amb port 6543")
                    debug_print("\n3️⃣  Actualitza el teu .env:")
                    debug_print("   → DATABASE_URL=<nou_valor_amb_port_6543>")
                    debug_print("\n4️⃣  Si el projecte estava pausat, espera 2-3 minuts i torna a provar")
                    debug_print("\n💡 El Session Pooler (port 6543) funciona amb IPv4 i és GRATUÏT!")
                    debug_print("="*60)
                    return False
                
                # Try pooler connection
                try:
                    debug_print(f"🔒 Intentant connexió amb Session Pooler: host={pooler_params['host']} port={pooler_params['port']} database={pooler_params['database']} user={pooler_params['user']}")
                    conn = psycopg2.connect(pooler_url)
                    cur = conn.cursor()
                    cur.execute("SELECT version();")
                    version = cur.fetchone()
                    debug_print(f"✅ Connexió amb Session Pooler exitosa! PostgreSQL version: {version[0]}")
                    
                    cur.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        ORDER BY table_name;
                    """)
                    tables = cur.fetchall()
                    debug_print(f"📋 Available tables: {[t[0] for t in tables]}")
                    
                    debug_print("\n💡 TIP: Update your DATABASE_URL to use Session Pooler (port 6543) for IPv4 compatibility!")
                    debug_print(f"   Pooler URL: {pooler_url.replace(parsed.password or '', '***') if parsed.password else 'Check .env'}")
                    
                    conn.close()
                    return True
                    
                except psycopg2.OperationalError as pooler_e:
                    debug_print(f"❌ Connexió amb Session Pooler fallida: {pooler_e}")
                    debug_print("\n💡 Possible solutions:")
                    debug_print("   1. Check your Supabase project is not paused")
                    debug_print("   2. Verify your DATABASE_URL in Supabase dashboard")
                    debug_print("   3. Get the Session Pooler connection string from Supabase dashboard")
                    debug_print("      (Settings → Database → Connection Pooling → Session mode)")
                    return False
            else:
                # Other error, not DNS related
                raise

    except psycopg2.OperationalError as e:
        debug_print(f"❌ Database connection failed (OperationalError): {e}")
        return False
    except Exception as e:
        debug_print(f"❌ Unexpected error: {e}")
        import traceback
        debug_print(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("🔍 Testing Supabase database connection...")
    print("=" * 50)
    success = test_connection()
    print("=" * 50)
    if success:
        print("🎉 Database connection is working!")
    else:
        print("⚠️  Database connection failed. Revisa els missatges anteriors.")
