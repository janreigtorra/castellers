from random import choices, shuffle
from typing import List, Optional
from joc_del_mocador.schemas import QuestionMCQ4Options
from joc_del_mocador.questions_utils import get_random_year
from joc_del_mocador.db_pool import get_db_connection
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


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


def load_json_colles():
    """Load json_colles.json file"""
    script_dir = Path(__file__).parent.parent.parent
    json_file = script_dir / "json_colles.json"
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading json_colles.json: {e}")
        return []


def get_castells_for_year(year: int, castells_data: list) -> list:
    """Get all castells that were completed in the given year"""
    castells_for_year = []
    for castell in castells_data:
        years = castell.get("years", [])
        # Filter out null values and check if year is in the list
        valid_years = [y for y in years if y is not None]
        if year in valid_years:
            castells_for_year.append(castell)
    return castells_for_year


def get_first_colles_for_castell(castell_name: str, year: str, limit: int = 4) -> list:
    """Query database to find the first colles that performed the castell in the given year (ordered by date)"""
    if not DATABASE_URL:
        return []
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Query to find the first colles that performed this castell in the given year
            # Get the first occurrence of each colla, then order by that first occurrence
            query = """
                WITH first_performances AS (
                    SELECT DISTINCT ON (co.name) 
                        co.name,
                        TO_DATE(e.date, 'DD/MM/YYYY') AS first_date,
                        e.id AS first_event_id
                    FROM castells c
                    JOIN event_colles ec ON c.event_colla_fk = ec.id
                    JOIN events e ON ec.event_fk = e.id
                    JOIN colles co ON ec.colla_fk = co.id
                    WHERE (
                        c.castell_name = %s 
                        OR c.castell_name = %s
                    )
                    AND EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) = %s::integer
                    ORDER BY 
                        co.name,
                        TO_DATE(e.date, 'DD/MM/YYYY') ASC,
                        e.id ASC
                )
                SELECT name
                FROM first_performances
                ORDER BY first_date ASC, first_event_id ASC
                LIMIT %s;
            """
            
            # Try both castell_code and castell_code_external formats
            cur.execute(query, (castell_name, castell_name.replace("de", "d"), year, limit))
            rows = cur.fetchall()
            cur.close()
            
            # Extract colla names
            colles = [row[0] for row in rows if row[0]]
            
            return colles
        
    except Exception as e:
        print(f"Error querying database for first colles: {e}")
        return []


def get_other_colla_options(excluded_colles: set, year: int, num_options: int = 3) -> list:
    """Get other colla options from json_colles.json based on boost, excluding specified colles"""
    colles_data = load_json_colles()
    
    # Filter colles that were active in the given year and not in excluded list
    filtered_colles = [
        colla for colla in colles_data
        if colla["min_year"] <= year <= colla["max_year"]
        and colla["colla_name"] not in excluded_colles
    ]
    
    if not filtered_colles:
        # Fallback if no colles match
        return ["Castellers de Vilafranca", "Castellers de Barcelona", "Colla Joves Xiquets de Valls"]
    
    # Extract colla names and weights (boost + 1 to ensure positive weights)
    colla_names = [colla["colla_name"] for colla in filtered_colles]
    weights = [colla["boost"] + 1 for colla in filtered_colles]
    
    # Select random colles based on weighted probability
    selected = choices(colla_names, weights=weights, k=min(num_options, len(colla_names)))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_selected = []
    for colla in selected:
        if colla not in seen:
            seen.add(colla)
            unique_selected.append(colla)
    
    # Fill up to num_options if needed
    while len(unique_selected) < num_options and len(unique_selected) < len(filtered_colles):
        remaining = [c for c in filtered_colles if c["colla_name"] not in unique_selected]
        if remaining:
            remaining_names = [c["colla_name"] for c in remaining]
            remaining_weights = [c["boost"] + 1 for c in remaining]
            additional = choices(remaining_names, weights=remaining_weights, k=1)[0]
            unique_selected.append(additional)
        else:
            break
    
    return unique_selected[:num_options]


def generate_colla_primer_castell_question(selected_years: List[int] = None) -> QuestionMCQ4Options:
    """
    Generate question: Quina colla va fer el primer XdX l'any XX?
    
    Args:
        selected_years: Optional list of years to pick from.
    """
    
    if not DATABASE_URL:
        return QuestionMCQ4Options(
            question="Quina colla va fer el primer XdX l'any XXXX?",
            answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
            correct_answer="Error al generar la resposta",
            is_error=True
        )
    
    # Try up to 5 times to get a valid year/castell/colla combination
    max_attempts = 5
    
    for attempt in range(max_attempts):
        try:
            # Get a random year - use selected_years if provided (equal probability)
            year_str = get_random_year(min_year=2005, selected_years=selected_years)
            year_int = int(year_str)
            
            # Load castells data
            castells_data = load_castells_puntuacions()
            if not castells_data:
                if attempt == max_attempts - 1:
                    return QuestionMCQ4Options(
                        question="Quina colla va fer el primer XdX l'any XXXX?",
                        answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
                        correct_answer="Error al generar la resposta",
                        is_error=True
                    )
                continue
            
            # Get castells that were completed in that year
            castells_for_year = get_castells_for_year(year_int, castells_data)
            
            if not castells_for_year:
                if attempt == max_attempts - 1:
                    return QuestionMCQ4Options(
                        question="Quina colla va fer el primer XdX l'any XXXX?",
                        answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
                        correct_answer="Error al generar la resposta",
                        is_error=True
                    )
                continue
            
            # Select a random castell weighted by punts_descarregat
            castell_names = [c.get("castell_code_external") or c.get("castell_code", "") for c in castells_for_year]
            weights = [c.get("punts_descarregat", 0) for c in castells_for_year]
            
            # Ensure all weights are positive
            if sum(weights) == 0:
                weights = [1] * len(weights)
            
            selected_castell = choices(castells_for_year, weights=weights, k=1)[0]
            castell_name = selected_castell.get("castell_code_external") or selected_castell.get("castell_code", "")
            
            # Query database to find the first colles that performed this castell in that year
            colles_ranking = get_first_colles_for_castell(castell_name, year_str, limit=4)
            
            if not colles_ranking:
                if attempt == max_attempts - 1:
                    return QuestionMCQ4Options(
                        question="Quina colla va fer el primer XdX l'any XXXX?",
                        answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
                        correct_answer="Error al generar la resposta",
                        is_error=True
                    )
                continue
    
            # First colla is the correct answer
            correct_colla = colles_ranking[0]
            
            # Use positions 2, 3, 4 from ranking as wrong options (if available)
            other_options = colles_ranking[1:4] if len(colles_ranking) > 1 else []
            
            # If we don't have enough options (less than 4 total), fill with get_other_colla_options
            # Exclude all colles already in the ranking
            excluded_colles = set(colles_ranking)
            needed = 3 - len(other_options)
            
            if needed > 0:
                # Get additional options, excluding those already in ranking
                additional_options = get_other_colla_options(excluded_colles, year_int, num_options=needed + 3)
                other_options.extend(additional_options[:needed])
            
            # Ensure we have exactly 3 wrong options
            while len(other_options) < 3:
                fallbacks = ["Castellers de Vilafranca", "Castellers de Barcelona", "Colla Joves Xiquets de Valls"]
                for fallback in fallbacks:
                    if fallback not in excluded_colles and fallback not in other_options:
                        other_options.append(fallback)
                        excluded_colles.add(fallback)
                        if len(other_options) >= 3:
                            break
            
            # Shuffle the options
            all_answers = [correct_colla] + other_options[:3]
            shuffle(all_answers)
            
            # Build question
            question = f"Quina colla va fer el primer {castell_name} l'any {year_str}?"
            
            return QuestionMCQ4Options(
                question=question,
                answers=all_answers,
                correct_answer=correct_colla
            )
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_attempts - 1:
                import traceback
                traceback.print_exc()
                return QuestionMCQ4Options(
                    question="Quina colla va fer el primer XdX l'any XXXX?",
                    answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
                    correct_answer="Error al generar la resposta",
                    is_error=True
                )
            continue
    
    # If we get here, all attempts failed
    return QuestionMCQ4Options(
        question="Quina colla va fer el primer XdX l'any XXXX?",
        answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
        correct_answer="Error al generar la resposta",
        is_error=True
    )
