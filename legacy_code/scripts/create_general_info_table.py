#!/usr/bin/env python3
"""
create_general_info_table.py
Creates a table for general castellers information and loads content from castellers_info_basic.txt
"""

import sqlite3
import os

DB_PATH = "database.db"
TEXT_FILE_PATH = "data_basic/castellers_info_basic.txt"

def create_general_info_table(db_path=DB_PATH):
    """Create the general_info table for storing general castellers information"""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()
    
    # Create table for general castellers information
    cur.execute("""
    CREATE TABLE IF NOT EXISTS general_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        line_number INTEGER,
        text TEXT,
        category TEXT,  -- e.g., "history", "technique", "music", etc.
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    conn.commit()
    conn.close()
    print("Table 'general_info' created successfully.")

def load_general_info(text_file_path=TEXT_FILE_PATH, db_path=DB_PATH):
    """Load general castellers information from text file into database"""
    if not os.path.exists(text_file_path):
        print(f"Error: File {text_file_path} not found.")
        return
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Clear existing data
    cur.execute("DELETE FROM general_info")
    
    with open(text_file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Define categories based on content patterns
    categories = {
        "introduction": ["Que son els castells"],
        "history": ["HISTÒRIA", "ELS ORÍGENS", "PRIMERES COLLES", "ÈPOCA D'OR", "DECADÈNCIA", "RENAIXENÇA", "FRANQUISME", "RECUPERACIÓ", "BOOM", "AVUI"],
        "technique": ["LA TÈCNICA", "Parts d'un castell", "TIPUS DE CASTELL", "ESTRUCTURES"],
        "music": ["MÚSICA", "ELS INSTRUMENTS", "EL TOC DE CASTELLS"],
        "events": ["ACTUACIÓ", "ON I QUAN", "DIADES", "COM FUNCIONEN", "CONCURS"],
        "values": ["VALORS", "AMATEURISME", "TREBALL EN EQUIP", "COHESIÓ", "TRADICIÓ"],
        "colles": ["LES COLLES", "ORGANITZEN", "INDUMENTÀRIA"],
        "unesco": ["UNESCO", "PATRIMONI"],
        "safety": ["CONSELLS", "SEGURETAT", "RISCS"],
        "other": []  # Default category
    }
    
    def categorize_text(text):
        """Categorize text based on content"""
        text_upper = text.upper()
        for category, keywords in categories.items():
            if category == "other":
                continue
            for keyword in keywords:
                if keyword in text_upper:
                    return category
        return "other"
    
    inserted_count = 0
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if line:  # Only insert non-empty lines
            category = categorize_text(line)
            cur.execute("""
                INSERT INTO general_info (line_number, text, category)
                VALUES (?, ?, ?)
            """, (line_num, line, category))
            inserted_count += 1
    
    conn.commit()
    conn.close()
    print(f"Loaded {inserted_count} lines of general castellers information into database.")

def main():
    print("Creating general_info table...")
    create_general_info_table()
    
    print("Loading general castellers information...")
    load_general_info()
    
    print("Done!")

if __name__ == "__main__":
    main()
