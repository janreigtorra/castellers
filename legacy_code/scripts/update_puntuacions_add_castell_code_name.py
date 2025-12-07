# update_puntuacions_add_castell_code_name.py
import sqlite3

DB_PATH = "database.db"


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
    "3de6p": "3d6a", # 'p' matches 'a'
    "3de6s": "3d6s",
    "3de7": "3d7",
    "3de7p": "3d7a", # 'p' matches 'a'
    "3de7s": "3d7s",
    "3de8": "3d8",
    "3de8p": "3d8a", # 'p' matches 'a'
    "3de8s": "3d8s",
    "3de9": "3d9",
    "3de9f": "3d9f",
    "3de9fp": "3d9af", # 'fp' matches 'af'
    "4de10fm": "4d10fm",
    "4de6": "4d6",
    "4de6p": "4d6a", # 'p' matches 'a'
    "4de7": "4d7",
    "4de7p": "4d7a", # 'p' matches 'a'
    "4de8": "4d8",
    "4de8p": "4d8a", # 'p' matches 'a'
    "4de9": "4d9",
    "4de9f": "4d9f",
    "4de9fp": "4d9af", # 'fp' matches 'af'
    "5de6": "5d6",
    "5de6p": "5d6a", # 'p' matches 'a'
    "5de7": "5d7",
    "5de7p": "5d7a", # 'p' matches 'a'
    "5de8": "5d8",
    "5de8p": "5d8a", # 'p' matches 'a'
    "5de9f": "5d9f",
    "7de6": "7d6",
    "7de6p": "7d6a", # 'p' matches 'a'
    "7de7": "7d7",
    "7de7p": "7d7a", # 'p' matches 'a'
    "7de8": "7d8",
    "7de8p": "7d8a", # 'p' matches 'a'
    "7de9f": "7d9f",
    "9de6": "9d6",
    "9de7": "9d7",
    "9de8": "9d8",
    "9de9f": "9d9f",
    "Pde4": "Pd4", # Also, change 'd4' code a 'Pd4'
    "Pde5": "Pd5",
    "Pde6": "Pd6",
    "Pde7f": "Pd7f",
    "Pde8fm": "Pd8fm",
    "Pde9fmp": "Pd9fmp"
}



def update_puntuacions_table(db_path=DB_PATH):
    """
    Add castell_code_name column to puntuacions table and populate it
    using the castell_code_name_mapping dictionary
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
        # Check if the column already exists
        cur.execute("PRAGMA table_info(puntuacions)")
        columns = [column[1] for column in cur.fetchall()]
        
        if 'castell_code_name' not in columns:
            # Add the new column
            print("Adding castell_code_name column to puntuacions table...")
            cur.execute("ALTER TABLE puntuacions ADD COLUMN castell_code_name TEXT")
        else:
            print("Column 'castell_code_name' already exists, updating existing data...")
        
        # Update all existing rows with the new column value using the mapping
        print("Populating castell_code_name column using mapping...")
        
        # Create a reverse mapping for easier lookup
        reverse_mapping = {v: k for k, v in castell_code_name_mapping.items()}
        
        # Update rows where we have a mapping
        for castell_code, castell_code_name in reverse_mapping.items():
            cur.execute("""
                UPDATE puntuacions 
                SET castell_code_name = ?
                WHERE castell_code = ?
            """, (castell_code_name, castell_code))
        
        # Commit the changes
        conn.commit()
        print("Successfully added castell_code_name column and populated it")
        
        # Show some examples of the mapping
        cur.execute("""
            SELECT castell_code, castell_code_name 
            FROM puntuacions 
            WHERE castell_code_name IS NOT NULL 
            LIMIT 10
        """)
        examples = cur.fetchall()
        
        print("\nExamples of mappings:")
        for castell_code, castell_code_name in examples:
            print(f"  {castell_code} -> {castell_code_name}")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_puntuacions_table()
