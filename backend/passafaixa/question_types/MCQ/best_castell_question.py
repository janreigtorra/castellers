from random import random, choice
from passafaixa.schemas import QuestionMCQ4Options
from passafaixa.questions_utils import get_random_year, get_random_colla
from passafaixa.db_pool import get_db_connection
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def load_castells_puntuacions():
    """Load castells_puntuacions.json file"""
    script_dir = Path(__file__).parent.parent
    json_file = script_dir / "castells_puntuacions.json"
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading castells_puntuacions.json: {e}")
        return []


def find_similar_castells(correct_castell_name: str, correct_status: str, castells_data: list, num_options: int = 3) -> list:
    """Find castells with similar points to the correct answer"""
    if not castells_data or not correct_castell_name:
        return []
    
    # Normalize castell name for comparison (remove spaces, lowercase)
    correct_castell_normalized = correct_castell_name.strip().lower()
    
    # Find the points for the correct castell
    correct_points = None
    correct_castell_code = None
    for castell in castells_data:
        castell_code_external = castell.get("castell_code_external", "").strip().lower()
        castell_code = castell.get("castell_code", "").strip().lower()
        
        # Check if this castell matches the correct answer
        if (castell_code_external == correct_castell_normalized or 
            castell_code == correct_castell_normalized or
            castell_code_external.replace("de", "d") == correct_castell_normalized.replace("de", "d") or
            castell_code.replace("de", "d") == correct_castell_normalized.replace("de", "d")):
            if correct_status == "Descarregat":
                correct_points = castell.get("punts_descarregat", 0)
            elif correct_status == "Carregat":
                correct_points = castell.get("punts_carregat", 0)
            correct_castell_code = castell.get("castell_code_external", castell.get("castell_code", ""))
            break
    
    if correct_points is None or correct_points == 0:
        return []
    
    # Find castells with similar points (±20% range, minimum ±200 points)
    min_points = max(0, correct_points - max(200, int(correct_points * 0.2)))
    max_points = correct_points + max(200, int(correct_points * 0.2))
    
    similar_castells = []
    seen_castells = set()  # Track castell codes to avoid duplicates
    
    for castell in castells_data:
        castell_code_external = castell.get("castell_code_external", "").strip()
        castell_code = castell.get("castell_code", "").strip()
        castell_code_to_use = castell_code_external or castell_code
        
        # Normalize for comparison
        castell_code_normalized = castell_code_to_use.lower()
        
        # Skip if this is the correct castell (check multiple formats)
        if (castell_code_normalized == correct_castell_normalized or
            castell_code_normalized.replace("de", "d") == correct_castell_normalized.replace("de", "d") or
            castell_code_to_use == correct_castell_code):
            continue  # Skip the correct answer
        
        # Skip if we've already added this castell code
        if castell_code_to_use in seen_castells:
            continue
        
        # Check both descarregat and carregat points
        desc_punts = castell.get("punts_descarregat", 0)
        carr_punts = castell.get("punts_carregat", 0)
        
        # Add if either status has similar points
        if min_points <= desc_punts <= max_points:
            similar_castells.append((castell_code_to_use, "Descarregat", desc_punts))
            seen_castells.add(castell_code_to_use)
        elif min_points <= carr_punts <= max_points:
            similar_castells.append((castell_code_to_use, "Carregat", carr_punts))
            seen_castells.add(castell_code_to_use)
    
    # Sort by how close they are to the correct points
    similar_castells.sort(key=lambda x: abs(x[2] - correct_points))
    
    # Select up to num_options, randomly choosing from top candidates
    if len(similar_castells) <= num_options:
        selected = similar_castells
    else:
        # Take top 2*num_options and randomly select from them
        top_candidates = similar_castells[:num_options * 2]
        selected = []
        available = list(top_candidates)
        for _ in range(num_options):
            if available:
                chosen = choice(available)
                available.remove(chosen)
                selected.append(chosen)
    
    # Format as "castell_name (status)" and ensure no duplicates
    formatted_options = []
    seen_formatted = set()
    for c in selected:
        formatted = f"{c[0]} ({c[1]})"
        if formatted not in seen_formatted:
            formatted_options.append(formatted)
            seen_formatted.add(formatted)
    
    return formatted_options


def get_castell_question_data(colla: str = None, year: str = None) -> tuple:
    
    if not DATABASE_URL:
        return ("", ["", "", ""])
    
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
        
        # Query to get only the top castell (correct answer)
        query = f"""
            WITH castells_punts AS (
                SELECT 
                    c.castell_name,
                    c.status,
                    CASE 
                        WHEN c.status = 'Descarregat' THEN COALESCE(p.punts_descarregat, 0)
                        WHEN c.status = 'Carregat' THEN COALESCE(p.punts_carregat, 0)
                        ELSE 0
                    END AS punts
                FROM castells c
                JOIN event_colles ec ON c.event_colla_fk = ec.id
                JOIN events e ON ec.event_fk = e.id
                JOIN colles co ON ec.colla_fk = co.id
                LEFT JOIN puntuacions p ON (
                    c.castell_name = p.castell_code_external 
                    OR c.castell_name = p.castell_code
                    OR c.castell_name = p.castell_code_name
                )
                WHERE 1=1
                {colla_filter}
                {year_filter}
            ),
            millors_castells AS (
                SELECT 
                    castell_name,
                    status,
                    punts,
                    ROW_NUMBER() OVER (
                        PARTITION BY castell_name 
                        ORDER BY punts DESC, 
                                 CASE WHEN status = 'Descarregat' THEN 1 
                                      WHEN status = 'Carregat' THEN 2 
                                      ELSE 3 END
                    ) AS rn
                FROM castells_punts
                WHERE punts > 0
            )
            SELECT castell_name, status
            FROM millors_castells
            WHERE rn = 1
            ORDER BY punts DESC
            LIMIT 1
        """
        
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        
        if not rows or len(rows) == 0:
            return ("", ["", "", ""])
        
        # Get the correct answer
        correct_row = rows[0]
        correct_castell_name = correct_row[0] or ""
        correct_status = correct_row[1] or ""
        correct_castell = f"{correct_castell_name} ({correct_status})" if correct_castell_name else ""
        
        # Find similar castells from JSON
        castells_data = load_castells_puntuacions()
        similar_options = find_similar_castells(correct_castell_name, correct_status, castells_data, num_options=3)
        
        # Final check: remove any option that matches the correct answer
        similar_options = [opt for opt in similar_options if opt != correct_castell]
        
        # Ensure we have exactly 3 options
        while len(similar_options) < 3:
            fallbacks = ["3d10fm (Descarregat)", "4d10fm (Descarregat)", "3d8s (Descarregat)"]
            # Make sure fallbacks don't match correct answer
            for fallback in fallbacks:
                if fallback != correct_castell and fallback not in similar_options:
                    similar_options.append(fallback)
                    if len(similar_options) >= 3:
                        break
        
        return (correct_castell, similar_options[:3])
        
    except Exception as e:
        import traceback
        print(f"Error getting castell question data: {e}")
        traceback.print_exc()
        return ("3d10fm (Descarregat)", ["4d10fm (Descarregat)", "3d8s (Descarregat)", "2d9f (Descarregat)"])


def generate_best_castell_question() -> QuestionMCQ4Options:
    """
    Generate a question asking which was the best castell for a colla/year.
    """
    if not DATABASE_URL:
        return QuestionMCQ4Options(
            question="Quin va ser el millor castell: Error?",
            answers=["Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions"],
            correct_answer="Error al obtenir les opcions",
            is_error=True
        )
    
    # Try up to 5 times to get a valid colla/year combination with castells
    max_attempts = 5
    castell_correcte = None
    options = None
    colla = None
    year = None
    
    for attempt in range(max_attempts):
        try:
            # Let's decide if we add the year to the question or not (70% probability to be True)
            add_year = random() < 0.70
            year = None
            if add_year:
                year = get_random_year()
            
            # Let's decide if we add the colla to the question or not (70% probability to be True)
            if not add_year:
                add_colla = True
            else:
                add_colla = random() < 0.50
            
            colla = None
            if add_colla:
                colla = get_random_colla(year)
            
            castell_correcte, options = get_castell_question_data(colla, year)
            
            # If we got valid data with a correct castell, break out of retry loop
            if castell_correcte and castell_correcte != "" and options and isinstance(options, list) and len(options) >= 3:
                break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_attempts - 1:
                # Last attempt failed, return error
                import traceback
                traceback.print_exc()
                return QuestionMCQ4Options(
                    question="Quin va ser el millor castell: Error?",
                    answers=["Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions"],
                    correct_answer="Error al obtenir les opcions",
                    is_error=True
                )
            continue
    
    # Check if we have valid data after retries
    if not castell_correcte or castell_correcte == "" or not options or not isinstance(options, list) or len(options) < 3:
        return QuestionMCQ4Options(
            question="Quin va ser el millor castell: Error?",
            answers=["Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions"],
            correct_answer="Error al obtenir les opcions",
            is_error=True
        )
    
    try:
        castell_correcte = str(castell_correcte)
        castell_opcion1 = str(options[0]) if options[0] else ""
        castell_opcion2 = str(options[1]) if options[1] else ""
        castell_opcion3 = str(options[2]) if options[2] else ""
        
        # Ensure we have valid options
        if not castell_opcion1 or not castell_opcion2 or not castell_opcion3:
            return QuestionMCQ4Options(
                question="Quin va ser el millor castell: Error?",
                answers=["Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions"],
                correct_answer="Error al obtenir les opcions",
                is_error=True
            )
        
        question = f"Quin va ser el millor castell "
        if colla is not None:
            question += f"dels {colla} "
        if year is not None:
            question += f"l'any {year}"
        else:
            question += " al llarg de la seva història"
        question += "?"
        
        return QuestionMCQ4Options(
            question=question,
            answers=[castell_correcte, castell_opcion1, castell_opcion2, castell_opcion3],
            correct_answer=castell_correcte
        )
        
    except Exception as e:
        import traceback
        print(f"Error generating best castell question: {e}")
        traceback.print_exc()
        return QuestionMCQ4Options(
            question="Quin va ser el millor castell: Error?",
            answers=["Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions"],
            correct_answer="Error al obtenir les opcions",
            is_error=True
        )