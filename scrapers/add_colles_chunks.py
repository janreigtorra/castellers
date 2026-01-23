"""
Script to add chunks for each colla from colles_castelleres.json
to castellers_info_chunks.json
"""

import json
import re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
COLLES_PATH = SCRIPT_DIR / "../backend/data_basic/colles_castelleres.json"
CHUNKS_PATH = SCRIPT_DIR / "../backend/data_basic/castellers_info_chunks.json"


def clean_text(text):
    """Clean up text by removing extra whitespace and references."""
    if not text:
        return ""
    text = re.sub(r'\[\d+\]', '', text)  # Remove [1], [2], etc.
    text = re.sub(r'\[cal citació\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def create_id(name, suffix):
    """Create a clean ID from colla name."""
    clean_name = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
    return f"colla_{clean_name}_{suffix}"


def build_wiki_stats_paragraph(wiki_stats, colla_name):
    """Build a natural paragraph from wiki_stats."""
    if not wiki_stats:
        return ""
    
    parts = [f"{colla_name}:"]
    
    # Map fields to Catalan text
    field_templates = {
        "Sobrenom": "El sobrenom és {value}",
        "Tipus": "És una {value}",
        "Color camisa": "El color de camisa és {value}",
        "Creació": "Va ser creada l'any {value}",
        "Bateig": "El bateig va ser {value}",
        "Diada destacada": "La seva diada destacada és {value}",
        "Millors castells": "Els seus millors castells són {value}",
        "Millor actuació": "La seva millor actuació va ser {value}",
        "Concurs": "Al Concurs de Castells: {value}",
        "Local": "El local és a {value}",
        "Presidència": "La presidència: {value}",
        "Cap de colla": "El cap de colla és {value}",
        "Lloc web": "Lloc web: {value}",
        "Data de dissolució o abolició": "Es va dissoldre l'any {value}",
    }
    
    for field, template in field_templates.items():
        if field in wiki_stats and wiki_stats[field]:
            value = clean_text(str(wiki_stats[field]))
            if value:
                parts.append(template.format(value=value) + ".")
    
    return " ".join(parts)


def create_chunks_for_colla(colla):
    """Create two chunks for a colla."""
    colla_name = colla.get("colla_name", "")
    wikipedia = colla.get("wikipedia", {})
    
    if not wikipedia:
        return []
    
    chunks = []
    
    # === CHUNK 1: Description + Info Wikipedia ===
    description = clean_text(wikipedia.get("description", ""))
    info_wiki = wikipedia.get("info_wikipedia", [])
    
    # Join info_wikipedia paragraphs
    if isinstance(info_wiki, list):
        info_text = " ".join(clean_text(p) for p in info_wiki if p and not p.startswith("##"))
    else:
        info_text = clean_text(info_wiki)
    
    # Combine description and info
    text_1 = description
    if info_text and info_text != description:
        text_1 = f"{description} {info_text}" if description else info_text
    
    if text_1:
        chunk_1 = {
            "id": create_id(colla_name, "info"),
            "title": f"{colla_name} - Informació general",
            "category": "colles",
            "years": [],
            "year_ranges": [],
            "colles": [colla_name],
            "places": [],
            "keywords": [colla_name.lower(), "colla castellera"],
            "text": text_1,
            "source": "colles_castelleres"
        }
        chunks.append(chunk_1)
    
    # === CHUNK 2: Best Castells + Wiki Stats ===
    best_castells = wikipedia.get("best_castells_wiki", [])
    wiki_stats = wikipedia.get("wiki_stats", {})
    
    text_parts = []
    
    # Best castells intro
    if best_castells:
        castells_list = ", ".join(best_castells)
        text_parts.append(f"Els millors castells de {colla_name} són: {castells_list}.")
    
    # Wiki stats as paragraph
    stats_paragraph = build_wiki_stats_paragraph(wiki_stats, colla_name)
    if stats_paragraph:
        text_parts.append(stats_paragraph)
    
    text_2 = " ".join(text_parts)
    
    if text_2:
        chunk_2 = {
            "id": create_id(colla_name, "stats"),
            "title": f"{colla_name} - Estadístiques i dades",
            "category": "colles",
            "years": [],
            "year_ranges": [],
            "colles": [colla_name],
            "places": [],
            "keywords": [colla_name.lower(), "estadístiques", "millors castells"],
            "text": text_2,
            "source": "colles_castelleres"
        }
        chunks.append(chunk_2)
    
    return chunks


def main():
    print("Loading colles data...")
    with open(COLLES_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
        # Fix trailing commas in JSON (common issue)
        content = re.sub(r',(\s*[\]\}])', r'\1', content)
        colles_data = json.loads(content)
    
    print("Loading existing chunks...")
    with open(CHUNKS_PATH, 'r', encoding='utf-8') as f:
        chunks_data = json.load(f)
    
    # Get existing chunk IDs
    existing_ids = {chunk['id'] for chunk in chunks_data['chunks']}
    
    # Create chunks for each colla
    new_chunks = []
    colles = colles_data.get("colles", [])
    
    print(f"Processing {len(colles)} colles...")
    
    for colla in colles:
        colla_name = colla.get("colla_name", "Unknown")
        colla_chunks = create_chunks_for_colla(colla)
        
        for chunk in colla_chunks:
            if chunk['id'] not in existing_ids:
                new_chunks.append(chunk)
                existing_ids.add(chunk['id'])
        
        if colla_chunks:
            print(f"  + {colla_name}: {len(colla_chunks)} chunks")
    
    # Add new chunks
    chunks_data['chunks'].extend(new_chunks)
    chunks_data['metadata']['total_chunks'] = len(chunks_data['chunks'])
    chunks_data['metadata']['last_colles_update'] = datetime.now().isoformat()
    
    # Save
    with open(CHUNKS_PATH, 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nAdded {len(new_chunks)} new chunks. Total: {len(chunks_data['chunks'])}")


if __name__ == "__main__":
    main()

