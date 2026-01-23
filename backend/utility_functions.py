"""
utility_functions.py
Utility functions for fuzzy matching entities in questions.
"""

import psycopg2
import re
import os
import time
from typing import List, Optional
from rapidfuzz import fuzz, process  # 10-100x faster than fuzzywuzzy
from pydantic import BaseModel
from typing import Literal
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================
# SIMPLE CACHE - Stores database results to avoid repeated queries
# ============================================================
_cache = {}
_CACHE_TTL = 3600  # 1 hour in seconds

def _get_cached(key: str, fetch_fn):
    """Get from cache or fetch and cache."""
    now = time.time()
    if key in _cache:
        data, timestamp = _cache[key]
        if now - timestamp < _CACHE_TTL:
            return data
    
    data = fetch_fn()
    _cache[key] = (data, now)
    return data

def clear_cache():
    """Clear all cached data (useful for testing or manual refresh)."""
    global _cache
    _cache = {}

def warm_entity_cache():
    """
    Pre-warm the entity cache by fetching all entity options from the database.
    Call this at app startup to avoid slow first queries.
    
    Returns:
        dict: Statistics about what was cached
    """
    import time
    start = time.time()
    stats = {}
    
    try:
        # Pre-fetch all entity types
        colles = get_all_colla_options()
        stats['colles'] = len(colles)
        
        castells = get_all_castell_options()
        stats['castells'] = len(castells)
        
        anys = get_all_any_options()
        stats['anys'] = len(anys)
        
        llocs = get_all_lloc_options()
        stats['llocs'] = len(llocs)
        
        diades = get_all_diada_options()
        stats['diades'] = len(diades)
        
        elapsed = (time.time() - start) * 1000
        stats['time_ms'] = round(elapsed, 2)
        
        print(f"[CACHE] Entity cache warmed in {elapsed:.2f}ms")
        print(f"[CACHE] Loaded: {stats['colles']} colles, {stats['castells']} castells, {stats['anys']} anys, {stats['llocs']} llocs, {stats['diades']} diades")
        
        return stats
    except Exception as e:
        print(f"[CACHE] Warning: Failed to warm entity cache: {e}")
        return {'error': str(e)}

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Get database connection to Supabase"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL must be set in environment variables")
    
    try:
        # Try connecting with the DATABASE_URL as-is
        return psycopg2.connect(DATABASE_URL)
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        
        # Check if it's a DNS resolution error
        if "could not translate host name" in error_msg or "nodename nor servname provided" in error_msg:
            hostname = None
            try:
                from urllib.parse import urlparse
                parsed = urlparse(DATABASE_URL)
                hostname = parsed.hostname
            except:
                pass
            
            error_help = f"\n❌ DNS Resolution Error: Cannot resolve hostname '{hostname}'"
            error_help += "\n\nPossible causes:"
            error_help += "\n1. Your Supabase project may be paused (free tier pauses after 7 days of inactivity)"
            error_help += "\n   → Check your Supabase dashboard and restore the project if paused"
            error_help += "\n2. Network connectivity issue"
            error_help += "\n   → Check your internet connection"
            error_help += "\n3. DNS cache issue"
            error_help += "\n   → Try: sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder"
            error_help += "\n4. The hostname may have changed"
            error_help += "\n   → Check your Supabase project settings for the correct DATABASE_URL"
            
            raise psycopg2.OperationalError(error_help) from e
        
        # Re-raise other operational errors as-is
        raise

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
    sql_query_type: str #Literal["millor_diada", "millor_castell", "castell_historia", "location_actuations", "first_castell", "castell_statistics", "year_summary", "concurs_ranking", "concurs_history", "custom"] = "custom"
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
    """Get all colles from the database (cached)."""
    def fetch():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT name FROM colles WHERE name IS NOT NULL")
        colles_names = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return colles_names
    return _get_cached('colles', fetch)
    
def get_all_castell_options() -> list[str]:
    """Get all castells from the database (cached)."""
    def fetch():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT castell_code FROM puntuacions WHERE castell_code IS NOT NULL")
        castells_codes = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return castells_codes
    return _get_cached('castells', fetch)
    
def get_all_any_options() -> list[str]:
    """Get all years from the database (cached)."""
    def fetch():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT date FROM events WHERE date IS NOT NULL")
        dates = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        
        # Extract years from dates
        years = set()
        for date in dates:
            if date:
                year_match = re.search(r'\b(19|20)\d{2}\b', str(date))
                if year_match:
                    years.add(year_match.group())
        return sorted(list(years))
    return _get_cached('anys', fetch)
    
def get_all_lloc_options() -> list[str]:
    """Get all llocs from the database (cached)."""
    def fetch():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT city FROM events WHERE city IS NOT NULL")
        llocs = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return llocs
    return _get_cached('llocs', fetch)
    
def get_all_diada_options() -> list[str]:
    """Get all diades from the database (cached)."""
    def fetch():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT name FROM events WHERE name IS NOT NULL")
        diades = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return diades
    return _get_cached('diades', fetch)



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
    Get colles matching the question using fast batch fuzzy matching.
    """
    colles_names = get_all_colla_options()
    if not colles_names:
        return ""
    
    # Use rapidfuzz.process.extract for batch matching (much faster)
    matches = process.extract(
        question.lower(), 
        colles_names, 
        scorer=fuzz.partial_ratio,
        limit=top_n,
        score_cutoff=85
    )
    
    if matches:
        return ", ".join([match[0] for match in matches])
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
    Get castells matching the question using fast batch fuzzy matching.
    """
    # First try to parse castell code directly from text (fast path)
    parsed_code = parse_castell_code_from_text(question)
    if parsed_code:
        return parsed_code
    
    castells_codes = get_all_castell_options()
    if not castells_codes:
        return ""
    
    # Use rapidfuzz.process.extract for batch matching
    matches = process.extract(
        question,
        castells_codes,
        scorer=fuzz.partial_ratio,
        limit=top_n,
        score_cutoff=30
    )
    
    if matches:
        return ", ".join([match[0] for match in matches])
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
    Get cities matching the question using fast batch fuzzy matching.
    """
    cities = get_all_lloc_options()
    locations = [city for city in cities if city]
    
    if not locations:
        return ""
    
    # Use rapidfuzz.process.extract for batch matching
    matches = process.extract(
        question.lower(),
        locations,
        scorer=fuzz.partial_ratio,
        limit=top_n,
        score_cutoff=50
    )
    
    if matches:
        return ", ".join([match[0] for match in matches])
    return ""

def get_diades_subset(question: str, top_n: int = 6) -> str:
    """
    Get diades matching the question using priority keywords + fuzzy matching.
    """
    diades_names = get_all_diada_options()
    
    if not diades_names:
        return ""
    
    # Priority mapping: common diada keywords -> full diada names
    # If any of these keywords appear in the question, add the diada(s) to the top
    priority_diades = {
        'sant magi': ['Diada de Sant Magí a Tarragona'],
        'sant magí': ['Diada de Sant Magí a Tarragona'],
        'santa tecla': ['Diada de Santa Tecla a Tarragona'],
        'merce': ['Diada de la Mercè a Barcelona', 'Diada de la Mercè (colles convidades) a Barcelona'],
        'mercè': ['Diada de la Mercè a Barcelona', 'Diada de la Mercè (colles convidades) a Barcelona'],
        'sant felix': ['Diada de Sant Fèlix a Vilafranca del Penedès'],
        'sant fèlix': ['Diada de Sant Fèlix a Vilafranca del Penedès'],
        'sant ramon': ['Diada de Sant Ramon a Vilafranca del Penedès'],
        'les santes': ['Les Santes a Mataró'],
        'tots sants': ['Diada de Tots Sants a Vilafranca del Penedès'],
        'sant narcis': ['Diada de Sant Narcís a Girona'],
        'sant narcís': ['Diada de Sant Narcís a Girona'],
        'santa ursula': ['Diada de Santa Úrsula a Valls'],
        'santa úrsula': ['Diada de Santa Úrsula a Valls'],
        'les neus': ['Diada de les Neus de Vilanova i la Geltrú'],
        'santa teresa': ['Diada de Santa Teresa al Vendrell'],
        'mercadal': ['Diada del Mercadal a Reus'],
    }
    
    question_lower = question.lower()
    result_diades = []
    
    # Step 1: Check for priority diades in the question - these go FIRST
    for keyword, diada_names in priority_diades.items():
        if keyword in question_lower:
            for diada in diada_names:
                if diada not in result_diades:
                    result_diades.append(diada)
    
    # Step 2: Also do fuzzy matching to find additional diades
    # Common words to remove before matching - these cause false positives
    words_to_remove = [
        'diada', 'diades', 'actuació', 'actuacions', 'actuacio',
        'castellers', 'casteller', 'castell', 'castells',
        'colla', 'colles', 'jornada', 'jornades',
        'millor', 'millors', 'pitjor', 'primera', 'primer', 'última', 'últim',
        'quina', 'quin', 'quines', 'quins', 'quan', 'quant', 'quantes', 'quants',
        'historia', 'història', 'temporada', 'any', 'anys',
        'part', 'llarg', 'estat', 'sido', 'fer', 'fet', 'feta', 'fets',
        'dels', 'les', 'els', 'per', 'que', 'com', 'amb', 'una', 'uns'
    ]
    
    # Clean the question by removing common words
    question_clean = clean_text_for_matching(question_lower, words_to_remove)
    
    # Use rapidfuzz.process.extract for batch matching
    matches = process.extract(
        question_clean,
        diades_names,
        scorer=fuzz.partial_ratio,
        limit=top_n,
        score_cutoff=50
    )
    
    # Add fuzzy matches (avoiding duplicates)
    if matches:
        for match in matches:
            if match[0] not in result_diades:
                result_diades.append(match[0])
    
    # Return up to top_n results
    if result_diades:
        return ", ".join(result_diades[:top_n])
    return ""

def get_castells_with_status_subset(question: str, top_n: int = 5) -> List[Castell]:
    """
    Extract castells with their status using fast batch fuzzy matching.
    """
    # First try to parse castell code directly from text (fast path)
    parsed_code = parse_castell_code_from_text(question)
    if parsed_code:
        status = extract_status_for_castell(question, parsed_code)
        return [Castell(castell_code=parsed_code, status=status)]
    
    castells_codes = get_all_castell_options()
    if not castells_codes:
        return []
    
    # Use rapidfuzz.process.extract for batch matching
    matches = process.extract(
        question,
        castells_codes,
        scorer=fuzz.partial_ratio,
        limit=top_n,
        score_cutoff=30
    )
    
    # Extract status for matched castells
    result = []
    for match in matches:
        castell_code = match[0]
        status = extract_status_for_castell(question, castell_code)
        result.append(Castell(castell_code=castell_code, status=status))
    
    return result


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