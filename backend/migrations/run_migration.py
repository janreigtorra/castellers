#!/usr/bin/env python3
"""
Run migration to add subscription and role columns to profiles table
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found in environment variables")
    print("Make sure you have a .env file with DATABASE_URL set")
    sys.exit(1)

def run_migration():
    """Run the migration to add subscription and role columns"""
    try:
        print("🔗 Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("📋 Checking if subscription column exists...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'profiles' 
            AND column_name = 'subscription'
        """)
        
        if not cur.fetchone():
            print("➕ Adding subscription column...")
            cur.execute("""
                ALTER TABLE public.profiles 
                ADD COLUMN subscription TEXT DEFAULT 'basic'
            """)
            print("✅ Added subscription column")
        else:
            print("✓ subscription column already exists")
        
        print("📋 Checking if role column exists...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'profiles' 
            AND column_name = 'role'
        """)
        
        if not cur.fetchone():
            print("➕ Adding role column...")
            cur.execute("""
                ALTER TABLE public.profiles 
                ADD COLUMN role TEXT DEFAULT 'user'
            """)
            print("✅ Added role column")
        else:
            print("✓ role column already exists")
        
        print("🔄 Updating existing rows with default values...")
        cur.execute("""
            UPDATE public.profiles 
            SET subscription = 'basic' 
            WHERE subscription IS NULL
        """)
        updated_sub = cur.rowcount
        
        cur.execute("""
            UPDATE public.profiles 
            SET role = 'user' 
            WHERE role IS NULL
        """)
        updated_role = cur.rowcount
        
        conn.commit()
        
        print(f"✅ Updated {updated_sub} rows for subscription")
        print(f"✅ Updated {updated_role} rows for role")
        print("\n🎉 Migration completed successfully!")
        
        cur.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()

