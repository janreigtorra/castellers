from random import random, randint, choices
from passafaixa.schemas import QuestionSliderInput
from passafaixa.questions_utils import get_random_year, get_random_colla
from passafaixa.db_pool import get_db_connection
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

ASK_FOR_YEAR = 0.5
ASK_FOR_COLLA = 0.5
ASK_FOR_DESCARREGAT = 0.7
HALF_POINT_MARGIN = 2


def load_castells_puntuacions():
    """Load castells_puntuacions.json file"""
    script_dir = Path(__file__).parent.parent.parent
    json_file = script_dir / "castells_puntuacions.json"
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading castells_puntuacions.json: {e}")
        return []


def get_punts_descarregat_map(castells_data: list) -> dict:
    """Create a mapping from castell names to punts_descarregat
    Maps both castell_code and castell_code_external, including variations"""
    punts_map = {}
    for castell in castells_data:
        castell_code = castell.get("castell_code", "").strip()
        castell_code_external = castell.get("castell_code_external", "").strip()
        punts_descarregat = castell.get("punts_descarregat", 0)
        
        # Map castell_code (e.g., "2d6")
        if castell_code:
            punts_map[castell_code] = punts_descarregat
            # Map variation with "de" (e.g., "2d6" -> "2de6")
            if "d" in castell_code and "de" not in castell_code:
                variation = castell_code.replace("d", "de", 1)
                punts_map[variation] = punts_descarregat
        
        # Map castell_code_external (e.g., "2de6")
        if castell_code_external:
            punts_map[castell_code_external] = punts_descarregat
            # Map variation with "d" (e.g., "2de6" -> "2d6")
            if "de" in castell_code_external:
                variation = castell_code_external.replace("de", "d", 1)
                punts_map[variation] = punts_descarregat
        
        # Ensure both codes map to each other if they exist
        if castell_code and castell_code_external and castell_code != castell_code_external:
            # Cross-map: if we have both, ensure each maps to the other
            punts_map[castell_code] = punts_descarregat
            punts_map[castell_code_external] = punts_descarregat

        # if we are not able to map return error 
        if not punts_map:
            return {"error": "No punts_descarregat map found"}
    
    return punts_map


def get_castells_with_points(colla: str = None, year: str = None) -> list:
    """Query database to get all castells with their descarregat points for colla/year"""
    if not DATABASE_URL:
        return []
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
        
        # Build WHERE clause filters
        colla_filter = ""
        year_filter = ""
        params = []
        
        if colla:
            colla_filter = "AND co.name = %s"
            params.append(colla)
        
        if year:
            year_filter = "AND EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) = %s::integer"
            params.append(year)
        
        # Query to get castells with descarregat points
        # Exclude Pde4
        query = f"""
            SELECT 
                c.castell_name,
                c.status,
                COALESCE(p.punts_descarregat, 0) AS punts_descarregat
            FROM castells c
            JOIN event_colles ec ON c.event_colla_fk = ec.id
            JOIN events e ON ec.event_fk = e.id
            JOIN colles co ON ec.colla_fk = co.id
            LEFT JOIN puntuacions p ON (
                c.castell_name = p.castell_code_external 
                OR c.castell_name = p.castell_code
                OR c.castell_name = p.castell_code_name
            )
            WHERE c.castell_name != 'Pde4'
            AND c.castell_name != 'Pde4cam'
            AND c.castell_name != 'Pde4ps'
            AND c.castell_name != 'Pde 4'
            AND c.castell_name != 'P de 4'
            {colla_filter}
            {year_filter}
        """
        
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        
        # Convert to list of dicts
        castells = []
        for row in rows:
            castell_name = row[0]
            if not castell_name:
                continue
            # Additional check to exclude Pde4 (case insensitive, handle variations)
            castell_normalized = castell_name.lower().replace(" ", "").replace("-", "")
            if castell_normalized == "pde4" or castell_normalized.startswith("pde4"):
                continue
            castells.append({
                "castell_name": castell_name,
                "status": row[1],
                "punts_descarregat": row[2] or 0
            })
        
        return castells
        
    except Exception as e:
        print(f"Error querying database for castells: {e}")
        return []


def get_castell_count(colla: str, year: str, castell_name: str, status: str) -> int:
    """Query database to count how many times a specific castell was done with given status"""
    if not DATABASE_URL:
        return 0
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
        
        # Build filters
        colla_filter = ""
        year_filter = ""
        params = []
        
        if colla:
            colla_filter = "AND co.name = %s"
            params.append(colla)
        
        if year:
            year_filter = "AND EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) = %s::integer"
            params.append(year)
        
        # Query to count specific castell
        query = f"""
            SELECT COUNT(*)
            FROM castells c
            JOIN event_colles ec ON c.event_colla_fk = ec.id
            JOIN events e ON ec.event_fk = e.id
            JOIN colles co ON ec.colla_fk = co.id
            WHERE c.castell_name = %s
            AND c.status = %s
            {colla_filter}
            {year_filter}
        """
        
        params.insert(0, status)
        params.insert(0, castell_name)
        cur.execute(query, params)
        row = cur.fetchone()
        cur.close()
        
        if row:
            return row[0] or 0
        return 0
        
    except Exception as e:
        print(f"Error querying database for castell count: {e}")
        return 0


def generate_castells_descarregats_any_question() -> QuestionSliderInput:
    """
    Generate a slider input question asking how many castells were descarregat/carregat.
    """
    if not DATABASE_URL:
        return QuestionSliderInput(
            question="Quants castells es van descarregar ERROR?",
            slider_min=0,
            slider_max=50,
            slider_step=1,
            correct_answer=0,
            half_point=0,
            is_error=True
        )
    
    # Try up to 5 times to get a valid colla/year/castell combination
    max_attempts = 5
    
    for attempt in range(max_attempts):
        try:
            # Decide if asking for year
            ask_for_year = random() < ASK_FOR_YEAR
            
            # If not asking for year, always ask for colla. Otherwise, decide with probability
            if not ask_for_year:
                ask_for_colla = True
            else:
                ask_for_colla = random() < ASK_FOR_COLLA
            
            # Get year if needed
            year = None
            if ask_for_year:
                year = get_random_year()
            
            # Get colla if needed
            colla = None
            if ask_for_colla:
                colla = get_random_colla(year)
            
            # Get all castells that the colla did in that year
            castells = get_castells_with_points(colla, year)
            
            if not castells:
                if attempt == max_attempts - 1:
                    return QuestionSliderInput(
                        question="Quants castells es van descarregar ERROR?",
                        slider_min=0,
                        slider_max=50,
                        slider_step=1,
                        correct_answer=0,
                        half_point=0,
                        is_error=True
                    )
                continue
            
            # Load castells_puntuacions.json to get punts_descarregat for weighting
            castells_data = load_castells_puntuacions()
            punts_map = get_punts_descarregat_map(castells_data)
            
            # Get unique castells
            unique_castells = {}
            for c in castells:
                castell_name = c["castell_name"]
                if not castell_name:
                    continue
                
                if castell_name not in unique_castells:
                    unique_castells[castell_name] = castell_name
            
            # Convert to list
            castells_list = list(unique_castells.values())
            
            if not castells_list:
                if attempt == max_attempts - 1:
                    return QuestionSliderInput(
                        question="Quants castells es van descarregar ERROR?",
                        slider_min=0,
                        slider_max=50,
                        slider_step=1,
                        correct_answer=0,
                        half_point=0,
                        is_error=True
                    )
                continue
    
            # Get weights from castells_puntuacions.json based on punts_descarregat
            weights = []
            for castell_name in castells_list:
                # Try to find punts_descarregat in the map (try multiple name formats)
                punts = punts_map.get(castell_name, 0)
                
                # Try variations if not found
                if punts == 0:
                    # Try replacing "de" with "d" (e.g., "2de6" -> "2d6")
                    punts = punts_map.get(castell_name.replace("de", "d"), 0)
                if punts == 0:
                    # Try replacing "d" with "de" (e.g., "2d6" -> "2de6")
                    # Only replace the first occurrence to avoid replacing multiple "d"s
                    if "d" in castell_name and "de" not in castell_name:
                        punts = punts_map.get(castell_name.replace("d", "de", 1), 0)
                
                # Ensure positive weight (minimum 1)
                weights.append(max(1, punts))
            
            # Select a random castell weighted by punts_descarregat from JSON
            selected_castell_name = choices(castells_list, weights=weights, k=1)[0]
            castell_name = selected_castell_name
            
            # Decide if asking for descarregat or carregat (based on the selected castell's status)
            # But we can also decide randomly
            ask_for_descarregat = random() < ASK_FOR_DESCARREGAT
            status = "Descarregat" if ask_for_descarregat else "Carregat"
            
            # Count how many times this specific castell was done with this status
            correct_answer = get_castell_count(colla, year, castell_name, status)
            
            # If no results for this status, try the other status
            if correct_answer == 0:
                status = "Carregat" if ask_for_descarregat else "Descarregat"
                correct_answer = get_castell_count(colla, year, castell_name, status)
                ask_for_descarregat = (status == "Descarregat")
            
            # If still no results, try next attempt
            if correct_answer == 0:
                if attempt == max_attempts - 1:
                    return QuestionSliderInput(
                        question="Quants castells es van descarregar ERROR?",
                        slider_min=0,
                        slider_max=50,
                        slider_step=1,
                        correct_answer=0,
                        half_point=0,
                        is_error=True
                    )
                continue
            
            # Build question text
            check = True
            if colla and not year:
                question_parts = [f"Quants {castell_name} han "]
                if ask_for_descarregat:
                    question_parts.append("descarregat")
                    check = False
                else:
                    question_parts.append("carregat")
                    check = False
            elif colla:
                question_parts = [f"Quants {castell_name} van"]
            else:
                question_parts = [f"Quants {castell_name} es van"]
            
            
            if check and ask_for_descarregat:
                question_parts.append("descarregar")
            elif check and not ask_for_descarregat:
                question_parts.append("carregar")
            
            if colla:
                question_parts.append(f"la colla {colla}")
            
            if year:
                question_parts.append(f"l'any {year}")
            else:
                question_parts.append("al llarg de la seva història")
                
            
            question = " ".join(question_parts) + "?"
            
            # slider_max = correct_answer + random number between 5 and 20
            slider_max = correct_answer + randint(5, 20)
            
            # Calculate HALF_POINT_MARGIN based on correct_answer
            if correct_answer < 3:
                half_point_margin = 0
            elif correct_answer < 6:
                half_point_margin = 1
            else:
                half_point_margin = 2
            
            return QuestionSliderInput(
                question=question,
                slider_min=0,
                slider_max=slider_max,
                slider_step=1,
                correct_answer=correct_answer,
                half_point=half_point_margin
            )
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_attempts - 1:
                import traceback
                traceback.print_exc()
                return QuestionSliderInput(
                    question="Quants castells es van descarregar ERROR?",
                    slider_min=0,
                    slider_max=50,
                    slider_step=1,
                    correct_answer=0,
                    half_point=0,
                    is_error=True
                )
            continue
    
    # If we get here, all attempts failed
    return QuestionSliderInput(
        question="Quants castells es van descarregar ERROR?",
        slider_min=0,
        slider_max=50,
        slider_step=1,
        correct_answer=0,
        half_point=0,
        is_error=True
    )
