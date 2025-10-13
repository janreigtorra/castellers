"""
utility_functions.py
Utility functions for fuzzy matching entities in questions.
"""

import sqlite3
import re
from typing import List, Optional
from fuzzywuzzy import fuzz
from pydantic import BaseModel
from typing import Literal
from dataclasses import dataclass

# Database path
DB_PATH = "database.db"


language_names = {
    "en": "anglès",
    "es": "espanyol", 
    "fr": "francès",
    "de": "alemany",
    "it": "italià",
    "pt": "portuguès",
    "ru": "rus",
    "zh": "xinès",
    "ja": "japonès",
    "ko": "coreà",
    "ar": "àrab",
    "hi": "hindi",
    "nl": "neerlandès",
    "sv": "suec",
    "no": "noruec",
    "da": "danès",
    "fi": "finès",
    "pl": "polonès",
    "tr": "turc",
    "he": "hebreu",
    "th": "tailandès",
    "vi": "vietnamita"
}

@dataclass
class Castell:
    castell_code: str
    status: Optional[str] = None  # Descarregat, Carregat, Intent, Intent desmuntat, or None


class FirstCallResponseFormat(BaseModel):
    tools: Literal["direct", "rag", "sql", "hybrid"]
    sql_query_type: Literal["millor_diada", "millor_castell", "castell_historia", "location_actuations", "first_castell", "castell_statistics", "year_summary", "concurs_ranking", "concurs_history", "custom"] = "custom"
    direct_response: str
    colla: list[str]
    castells: list[Castell]
    anys: list[str]
    llocs: list[str]
    diades: list[str]
    editions: list[str] = []
    jornades: list[str] = []
    positions: list[int] = []


def get_all_colla_options() -> list[str]:
    """
    Get all colles from the database.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT name FROM colles WHERE name IS NOT NULL")
    colles_names = [row[0] for row in cur.fetchall()]
    conn.close()
    return colles_names
    
def get_all_castell_options() -> list[str]:
    """
    Get all castells from the database.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT castell_code FROM puntuacions WHERE castell_code IS NOT NULL")
    castells_codes = [row[0] for row in cur.fetchall()]
    conn.close()
    return castells_codes
    
def get_all_any_options() -> list[str]:
    """
    Get all years from the database by extracting them from event dates.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT date FROM events WHERE date IS NOT NULL")
    dates = [row[0] for row in cur.fetchall()]
    conn.close()
    
    # Extract years from dates
    years = set()
    for date in dates:
        if date:
            # Extract year from date (assuming format YYYY-MM-DD or similar)
            year_match = re.search(r'\b(19|20)\d{2}\b', str(date))
            if year_match:
                years.add(year_match.group())
    
    return sorted(list(years))
    
def get_all_lloc_options() -> list[str]:
    """
    Get all llocs from the database.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT city FROM events WHERE city IS NOT NULL")
    llocs = [row[0] for row in cur.fetchall()]
    conn.close()
    return llocs
    
def get_all_diada_options() -> list[str]:
    """
    Get all diades from the database.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT name FROM events WHERE name IS NOT NULL")
    diades = [row[0] for row in cur.fetchall()]
    conn.close()
    return diades



def clean_text_for_matching(text: str, words_to_remove: List[str]) -> str:
    """
    Clean text by removing common words and numbers for better fuzzy matching.
    """
    text_clean = text.lower()
    
    # Remove common words
    for word in words_to_remove:
        text_clean = re.sub(r'\b' + word + r'\b', '', text_clean)
    
    # Remove numbers
    text_clean = re.sub(r'\d+', '', text_clean)
    
    # Clean up extra spaces
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()
    
    return text_clean

def get_colles_castelleres_subset(question: str, top_n: int = 5) -> str:
    """
    Get all colles castelleres from the database and calculate fuzzy matching with the question.
    Return the list of colles that have a similarity score greater than 0.5.
    Exclude common words like "castellera", "Castellers", "colla".
    """
    # Get all colles from database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM colles WHERE name IS NOT NULL")
    colles_names = [row[0] for row in cur.fetchall()]
    conn.close()
    
    if not colles_names:
        return ""
    
    # Clean the question
    words_to_remove = ['castellera', 'castellers', 'colla', 'colles', 'de', 'del', 'dels', 'la', 'el', 'les', 'els', 'xiquets']
    question_clean = clean_text_for_matching(question, words_to_remove)
    
    matching_colles = []
    
    for colla_name in colles_names:
        if not colla_name:
            continue
            
        # Clean colla name for comparison
        colla_clean = clean_text_for_matching(colla_name, words_to_remove)
        
        # Calculate fuzzy match score
        score = fuzz.partial_ratio(question_clean, colla_clean)
        
        if score >= 85:  # 0.8 * 100 for fuzzywuzzy scoring
            matching_colles.append({
                'name': colla_name,
                'score': score,
                'clean_name': colla_clean
            })
    
    # Sort by score (highest first) and return as comma-separated string
    matching_colles.sort(key=lambda x: x['score'], reverse=True)
    
    if matching_colles:
        return ", ".join([colla['name'] for colla in matching_colles[:top_n]])
    else:
        return ""

def parse_castell_code_from_text(text: str) -> str:
    """
    Parse castell codes from text by identifying patterns like:
    - 'dos de set' -> 2d7
    - '3 de 9 amb folre' -> 3d9f
    - 'torre de 6' -> 2d6
    - 'pilar de 5' -> Pd5
    - '3 de 7 amb agulla' -> 3d7a
    - '3 de 7 per sota' -> 3d7s
    """
    import re
    
    # Normalize text to lowercase and clean
    text = text.lower().strip()
    
    # Number word mappings
    number_words = {
        'zero': '0', 'un': '1', 'dos': '2', 'tres': '3', 'quatre': '4', 'cinc': '5',
        'sis': '6', 'set': '7', 'vuit': '8', 'nou': '9', 'deu': '10',
        'una': '1', 'dues': '2'
    }
    
    # Special castell types
    special_types = {
        'torre': '2',  # torre de X = 2dX
        'pilar': 'P'   # pilar de X = PdX
    }
    
    # Modifier mappings
    modifiers = {
        'folre': 'f',
        'manilles': 'm', 
        'per sota': 's',
        'amb agulla': 'a',
        'amb pilar': 'a',
        'agulla': 'a',
        'pilar': 'a',  # when used as modifier
        'puntals': 'p'
    }
    
    # Pattern 1: Direct code format (3d7, 2d6f, etc.)
    direct_pattern = r'\b([0-9P]+d[0-9]+[afms]*)\b'
    direct_matches = re.findall(direct_pattern, text)
    if direct_matches:
        return direct_matches[0]
    
    # Pattern 2: Torre de X
    torre_pattern = r'torre\s+de\s+([0-9]+)'
    torre_match = re.search(torre_pattern, text)
    if torre_match:
        height = torre_match.group(1)
        return f"2d{height}"
    
    # Pattern 3: Pilar de X
    pilar_pattern = r'pilar\s+de\s+([0-9]+)'
    pilar_match = re.search(pilar_pattern, text)
    if pilar_match:
        height = pilar_match.group(1)
        return f"Pd{height}"
    
    # Pattern 4: Number word de number word (dos de set, tres de nou, etc.)
    word_de_word_pattern = r'([a-z]+)\s+de\s+([a-z]+)'
    word_match = re.search(word_de_word_pattern, text)
    if word_match:
        first_word = word_match.group(1)
        second_word = word_match.group(2)
        
        # Check if first word is a number
        if first_word in number_words:
            width = number_words[first_word]
            height = number_words.get(second_word, second_word)
            
            # Check for modifiers after the pattern
            remaining_text = text[word_match.end():].strip()
            modifier_codes = []
            
            # Sort modifiers by length (longest first) to avoid partial matches
            sorted_modifiers = sorted(modifiers.items(), key=lambda x: len(x[0]), reverse=True)
            
            for mod_word, mod_code in sorted_modifiers:
                if mod_word in remaining_text:
                    modifier_codes.append(mod_code)
                    # Remove the found modifier from text to avoid double matching
                    remaining_text = remaining_text.replace(mod_word, '', 1)
            
            # Sort modifier codes with special ordering: folre -> manilles -> puntals
            # Order: f, m, p, a, s (folre, manilles, puntals, agulla, per sota)
            modifier_order = {'f': 0, 'm': 1, 'p': 2, 'a': 3, 's': 4}
            modifier_codes.sort(key=lambda x: modifier_order.get(x, 5))
            
            # Validate modifier hierarchy:
            # 1. manilles can only appear with folre
            if 'm' in modifier_codes and 'f' not in modifier_codes:
                modifier_codes.remove('m')  # Remove manilles if folre is not present
            
            # 2. puntals can only appear with manilles (which requires folre)
            if 'p' in modifier_codes and 'm' not in modifier_codes:
                modifier_codes.remove('p')  # Remove puntals if manilles is not present
            
            modifier_code = ''.join(modifier_codes)
            
            return f"{width}d{height}{modifier_code}"
    
    # Pattern 5: Number de number (3 de 7, 2 de 6, etc.)
    num_de_num_pattern = r'([0-9]+)\s+de\s+([0-9]+)'
    num_match = re.search(num_de_num_pattern, text)
    if num_match:
        width = num_match.group(1)
        height = num_match.group(2)
        
        # Check for modifiers after the pattern
        remaining_text = text[num_match.end():].strip()
        modifier_codes = []
        
        # Sort modifiers by length (longest first) to avoid partial matches
        sorted_modifiers = sorted(modifiers.items(), key=lambda x: len(x[0]), reverse=True)
        
        for mod_word, mod_code in sorted_modifiers:
            if mod_word in remaining_text:
                modifier_codes.append(mod_code)
                # Remove the found modifier from text to avoid double matching
                remaining_text = remaining_text.replace(mod_word, '', 1)
        
        # Sort modifier codes alphabetically for consistency
        modifier_codes.sort()
        modifier_code = ''.join(modifier_codes)
        
        return f"{width}d{height}{modifier_code}"
    
    # Pattern 6: Special cases with modifiers
    # Look for any number followed by modifiers
    special_pattern = r'([0-9]+)\s+([a-z\s]+)'
    special_match = re.search(special_pattern, text)
    if special_match:
        number = special_match.group(1)
        rest = special_match.group(2).strip()
        
        # Try to extract height and modifiers
        height_match = re.search(r'([0-9]+)', rest)
        if height_match:
            height = height_match.group(1)
            modifier_codes = []
            
            # Sort modifiers by length (longest first) to avoid partial matches
            sorted_modifiers = sorted(modifiers.items(), key=lambda x: len(x[0]), reverse=True)
            
            for mod_word, mod_code in sorted_modifiers:
                if mod_word in rest:
                    modifier_codes.append(mod_code)
                    # Remove the found modifier from text to avoid double matching
                    rest = rest.replace(mod_word, '', 1)
            
            # Sort modifier codes with special ordering: folre -> manilles -> puntals
            # Order: f, m, p, a, s (folre, manilles, puntals, agulla, per sota)
            modifier_order = {'f': 0, 'm': 1, 'p': 2, 'a': 3, 's': 4}
            modifier_codes.sort(key=lambda x: modifier_order.get(x, 5))
            
            # Validate modifier hierarchy:
            # 1. manilles can only appear with folre
            if 'm' in modifier_codes and 'f' not in modifier_codes:
                modifier_codes.remove('m')  # Remove manilles if folre is not present
            
            # 2. puntals can only appear with manilles (which requires folre)
            if 'p' in modifier_codes and 'm' not in modifier_codes:
                modifier_codes.remove('p')  # Remove puntals if manilles is not present
            
            modifier_code = ''.join(modifier_codes)
            
            return f"{number}d{height}{modifier_code}"
    
    return ""

def get_castells_subset(question: str, top_n: int = 3) -> str:
    """
    Get all castells from the database and calculate fuzzy matching with the question.
    Return the list of castells that have a similarity score greater than 0.5.
    Exclude common words like "castell", "castells".
    """
    # First try to parse castell code directly from text
    parsed_code = parse_castell_code_from_text(question)
    if parsed_code:
        return parsed_code
    
    # Get all castells from database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT castell_code FROM puntuacions WHERE castell_code_name IS NOT NULL")
    castells_codes = [row[0] for row in cur.fetchall()]
    conn.close()
    
    if not castells_codes:
        return ""
    
    matching_castells = []
    
    for castell_code in castells_codes:
        if not castell_code:
            continue
            
        # Calculate fuzzy match score
        score = fuzz.partial_ratio(question, castell_code)
        
        if score >= 30:  # 0.3 * 100 for fuzzywuzzy scoring
            matching_castells.append({
                'name': castell_code,
                'score': score
            })
    
    # Sort by score (highest first) and return as comma-separated string
    matching_castells.sort(key=lambda x: x['score'], reverse=True)
    
    if matching_castells:
        return ", ".join([castell['name'] for castell in matching_castells[:top_n]])
    else:
        return ""

def get_anys_subset(question: str, top_n: int = 5) -> str:
    """
    Extract years from the question text and return them.
    Handles patterns like:
    - 2023, 1998 (direct 4-digit years)
    - del 23 (meaning 2023)
    - del 96 (meaning 1996)
    - any 2023, anys 2023-2024
    """
    import re
    
    # Normalize text to lowercase
    text = question.lower().strip()
    
    found_years = set()
    
    # Pattern 1: Direct 4-digit years (1900-2099)
    four_digit_pattern = r'\b(19|20)\d{2}\b'
    four_digit_matches = re.findall(four_digit_pattern, text)
    for match in four_digit_matches:
        # Find the full year
        full_year_match = re.search(r'\b' + match + r'\d{2}\b', text)
        if full_year_match:
            found_years.add(full_year_match.group())
    
    # Pattern 2: "del XX" or "dels XX" (2-digit years)
    two_digit_pattern = r'del?\s+(\d{2})\b'
    two_digit_matches = re.findall(two_digit_pattern, text)
    for match in two_digit_matches:
        year_2digit = int(match)
        # Convert 2-digit to 4-digit year
        if year_2digit >= 0 and year_2digit <= 99:
            # Assume years 00-30 are 2000s, 31-99 are 1900s
            if year_2digit <= 30:
                full_year = f"20{year_2digit:02d}"
            else:
                full_year = f"19{year_2digit:02d}"
            found_years.add(full_year)
    
    # Pattern 3: Look for years in ranges like "2023-2024"
    range_pattern = r'\b(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}\b'
    range_matches = re.findall(range_pattern, text)
    for match in range_matches:
        # Extract the full range
        full_range_match = re.search(r'\b' + match[0] + r'\d{2}\s*[-–]\s*' + match[1] + r'\d{2}\b', text)
        if full_range_match:
            range_text = full_range_match.group()
            # Extract both years from the range
            years_in_range = re.findall(r'(19|20)\d{2}', range_text)
            for year_prefix in years_in_range:
                full_year_match = re.search(r'\b' + year_prefix + r'\d{2}\b', range_text)
                if full_year_match:
                    found_years.add(full_year_match.group())
    
    # Convert set to sorted list
    years_list = sorted(list(found_years))
    
    if years_list:
        return ", ".join(years_list[:top_n])
    else:
        return ""

def get_llocs_subset(question: str, top_n: int = 3) -> str:
    """
    Get all cities from the database and calculate fuzzy matching with the question.
    Return the list of cities that have a similarity score greater than 0.5.
    Exclude common words like "lloc", "llocs".
    """
    # Get all cities from database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT city FROM events WHERE city IS NOT NULL")
    cities = [row[0] for row in cur.fetchall()]
    conn.close()    
    
    # Use only cities
    locations = [city for city in cities if city]  # Remove None/empty values
    
    if not locations:
        return ""
    
    # Clean the question
    words_to_remove = ['lloc', 'llocs', 'ciutat', 'ciutats', 'població', 'poblacions', 'de', 'del', 'dels', 'la', 'el', 'les', 'els']
    question_clean = clean_text_for_matching(question, words_to_remove)
    
    matching_locations = []
    
    for location in locations:
        if not location:
            continue
            
        # Clean location name for comparison
        location_clean = clean_text_for_matching(location, words_to_remove)
        
        # Calculate fuzzy match score
        score = fuzz.partial_ratio(question_clean, location_clean)
        
        if score >= 50:  # 0.5 * 100 for fuzzywuzzy scoring
            matching_locations.append({
                'name': location,
                'score': score,
                'clean_name': location_clean
            })
    
    # Sort by score (highest first) and return as comma-separated string
    matching_locations.sort(key=lambda x: x['score'], reverse=True)
    
    if matching_locations:
        return ", ".join([location['name'] for location in matching_locations[:top_n]])
    else:
        return ""

def get_diades_subset(question: str, top_n: int = 4) -> str:
    """
    Get all diades (events) from the database and calculate fuzzy matching with the question.
    Return the list of diades that have a similarity score greater than 0.5.
    Exclude common words like "diada", "diades".
    """
    # Get all diades from database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT name FROM events WHERE name IS NOT NULL")
    diades_names = [row[0] for row in cur.fetchall()]
    conn.close()
    
    if not diades_names:
        return ""
    
    # Clean the question
    words_to_remove = ['diada', 'diades', 'festival', 'festivals', 'actuació', 'actuacions', 'de',
                         'del', 'dels', 'la', 'el', 'les', 'els', 'festa', 'festiu', 'festa major', 
                         'major', 'major de', 'local', 'locals']
    question_clean = clean_text_for_matching(question, words_to_remove)
    
    matching_diades = []
    
    for diada_name in diades_names:
        if not diada_name:
            continue
            
        # Clean diada name for comparison
        diada_clean = clean_text_for_matching(diada_name, words_to_remove)
        
        # Calculate fuzzy match score
        score = fuzz.partial_ratio(question_clean, diada_clean)
        
        if score >= 50:  # 0.5 * 100 for fuzzywuzzy scoring
            matching_diades.append({
                'name': diada_name,
                'score': score,
                'clean_name': diada_clean
            })
    
    # Sort by score (highest first) and return as comma-separated string
    matching_diades.sort(key=lambda x: x['score'], reverse=True)
    
    if matching_diades:
        return ", ".join([diada['name'] for diada in matching_diades[:top_n]])
    else:
        return ""

def get_castells_with_status_subset(question: str, top_n: int = 5) -> List[Castell]:
    """
    Extract castells with their status from the question text.
    Returns a list of Castell objects with castell_code and optional status.
    """
    import re
    
    # First try to parse castell code directly from text
    parsed_code = parse_castell_code_from_text(question)
    if parsed_code:
        # Extract status for this castell
        status = extract_status_for_castell(question, parsed_code)
        return [Castell(castell_code=parsed_code, status=status)]
    
    # Get all castells from database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT castell_code FROM puntuacions WHERE castell_code_name IS NOT NULL")
    castells_codes = [row[0] for row in cur.fetchall()]
    conn.close()
    
    if not castells_codes:
        return []
    
    matching_castells = []
    
    for castell_code in castells_codes:
        if not castell_code:
            continue
            
        # Calculate fuzzy match score
        score = fuzz.partial_ratio(question, castell_code)
        
        if score >= 30:  # 0.3 * 100 for fuzzywuzzy scoring
            # Extract status for this castell
            status = extract_status_for_castell(question, castell_code)
            matching_castells.append(Castell(castell_code=castell_code, status=status))
    
    # Sort by score (highest first)
    matching_castells.sort(key=lambda x: fuzz.partial_ratio(question, x.castell_code), reverse=True)
    
    return matching_castells[:top_n]


def extract_status_for_castell(question: str, castell_code: str) -> Optional[str]:
    """
    Extract status for a specific castell from the question text.
    Returns the status if found, None otherwise.
    """
    import re
    
    # Normalize text to lowercase
    text = question.lower().strip()
    
    # Define status mappings
    status_mappings = {
        'descarregat': 'Descarregat',
        'descarregats': 'Descarregat',
        'descarregada': 'Descarregat',
        'descarregades': 'Descarregat',
        'carregat': 'Carregat',
        'carregats': 'Carregat',
        'carregada': 'Carregat',
        'carregades': 'Carregat',
        'intent': 'Intent',
        'intents': 'Intent',
        'intent desmuntat': 'Intent desmuntat',
        'intents desmuntats': 'Intent desmuntat',
        'intent desmuntats': 'Intent desmuntat',
        'desmuntat': 'Intent desmuntat',
        'desmuntats': 'Intent desmuntat',
        'desmuntada': 'Intent desmuntat',
        'desmuntades': 'Intent desmuntat',
        'fallat': 'Intent desmuntat',
        'fallats': 'Intent desmuntat',
        'fallada': 'Intent desmuntat',
        'fallades': 'Intent desmuntat',
        'aconseguit': 'Descarregat',  # Default to descarregat for "aconseguit"
        'aconseguits': 'Descarregat',
        'aconseguida': 'Descarregat',
        'aconseguides': 'Descarregat',
        'completat': 'Descarregat',  # Default to descarregat for "completat"
        'completats': 'Descarregat',
        'completada': 'Descarregat',
        'completades': 'Descarregat',
        'fet': 'Descarregat',  # Default to descarregat for "fet"
        'fets': 'Descarregat',
        'feta': 'Descarregat',
        'fetes': 'Descarregat'
    }
    
    # Look for status words in the text
    for status_word, mapped_status in status_mappings.items():
        # Use word boundary to match whole words only
        pattern = r'\b' + re.escape(status_word) + r'\b'
        if re.search(pattern, text):
            return mapped_status
    
    return None

    
castell_code_name_mapping = {
    "2d6": "2de6",
    "2d6s": "2de6s", 
    "2d7": "2de7",
    "2d8": "2de8",
    "2d8f": "2de8f",
    "2d9f": "2de9f",
    "2d9fm": "2de9fm",
    "3d10fm": "3de10fm",
    "3d6": "3de6",
    "3d6a": "3de6p", # 'a' matches 'p'
    "3d6s": "3de6s",
    "3d7": "3de7",
    "3d7a": "3de7p", # 'a' matches 'p'
    "3d7s": "3de7s",
    "3d8": "3de8",
    "3d8a": "3de8p", # 'a' matches 'p'
    "3d8s": "3de8s",
    "3d9": "3de9",
    "3d9f": "3de9f",
    "3d9af": "3de9fp", # 'af' matches 'fp'
    "4d10fm": "4de10fm",
    "4d6": "4de6",
    "4d6a": "4de6p", # 'a' matches 'p'
    "4d7": "4de7",
    "4d7a": "4de7p", # 'a' matches 'p'
    "4d8": "4de8",
    "4d8a": "4de8p", # 'a' matches 'p'
    "4d9": "4de9",
    "4d9f": "4de9f",
    "4d9af": "4de9fp", # 'af' matches 'fp'
    "5d6": "5de6",
    "5d6a": "5de6p", # 'a' matches 'p'
    "5d7": "5de7",
    "5d7a": "5de7p", # 'a' matches 'p'
    "5d8": "5de8",
    "5d8a": "5de8p", # 'a' matches 'p'
    "5d9f": "5de9f",
    "7d6": "7de6",
    "7d6a": "7de6p", # 'a' matches 'p'
    "7d7": "7de7",
    "7d7a": "7de7p", # 'a' matches 'p'
    "7d8": "7de8",
    "7d8a": "7de8p", # 'a' matches 'p'
    "7d9f": "7de9f",
    "9d6": "9de6",
    "9d7": "9de7",
    "9d8": "9de8",
    "9d9f": "9de9f",
    "Pd4": "Pde4", # Also, change 'Pd4' code to 'Pde4'
    "Pd5": "Pde5",
    "Pd6": "Pde6",
    "Pd7f": "Pde7f",
    "Pd8fm": "Pde8fm",
    "Pd9fmp": "Pde9fmp"
}

def code_to_name(code: str) -> str:
    """
    Convert a castell code to a castell name.
    """
    return castell_code_name_mapping.get(code, code)