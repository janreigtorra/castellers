from random import choice, shuffle
import random
from typing import List, Optional
from joc_del_mocador.schemas import QuestionOrdering
from joc_del_mocador.db_pool import get_db_connection
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def load_concurs_anys():
    """Load concurs_anys.json file"""
    script_dir = Path(__file__).parent.parent.parent
    json_file = script_dir / "concurs_anys.json"
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading concurs_anys.json: {e}")
        return []


def select_year_jornada(concurs_data, selected_years: List[int] = None):
    """
    Select a year and jornada with weighted probabilities.
    
    Args:
        concurs_data: List of concurs data from JSON
        selected_years: Optional list of years to filter to (equal probability)
    """
    if not concurs_data:
        return None, None
    
    # Group by year
    years_data = {}
    for item in concurs_data:
        year = item.get("any")
        jornada = item.get("jornada", "")
        if year not in years_data:
            years_data[year] = []
        years_data[year].append(jornada)
    
    # If selected_years is provided, filter to only those years
    if selected_years and len(selected_years) > 0:
        selected_years_set = set(int(y) for y in selected_years)
        years_list = [y for y in sorted(years_data.keys()) if y in selected_years_set]
        if not years_list:
            # Fallback to all years if none of the selected years are in concurs data
            years_list = sorted(years_data.keys())
            weights = [1] * len(years_list)  # Equal weights for fallback
        else:
            weights = [1] * len(years_list)  # Equal weights for selected years
    else:
        # Calculate weights for years (recent years have higher probability)
        years_list = sorted(years_data.keys())
        weights = []
        
        for year in years_list:
            # Recent years (2016+) get higher weight
            if year >= 2016:
                weight = 0.5
            elif year >= 2000:
                weight = 0.35
            elif year >= 1980:
                weight = 0.10
            else:
                weight = 0.05
            weights.append(weight)
    
    if not years_list:
        return None, None
    
    # Select a year based on weighted probability
    selected_year = random.choices(years_list, weights=weights, k=1)[0]
    
    # Get jornades for this year
    jornades = years_data[selected_year]
    
    # If multiple jornades, prioritize "Jornada Diumenge Tarragona" by factor of 5
    if len(jornades) > 1:
        weights_jornada = []
        for jornada in jornades:
            if jornada == "Jornada Diumenge Tarragona":
                weights_jornada.append(5)
            else:
                weights_jornada.append(1)
        selected_jornada = random.choices(jornades, weights=weights_jornada, k=1)[0]
    else:
        selected_jornada = jornades[0] if jornades else ""
    
    return selected_year, selected_jornada


def generate_concurs_ranking_question(selected_years: List[int] = None) -> QuestionOrdering:
    """
    Generate a question asking to order colles by their ranking position in a concurs jornada.
    
    Args:
        selected_years: Optional list of years to pick from.
    """
    if not DATABASE_URL:
        return QuestionOrdering(
            question="Ordena les colles en funció de la seva posició del ranking de la jornada XX de l'any XX del concurs de castells",
            options=["Error al generar la resposta"],
            correct_answer_order=[],
            is_error=True
        )
    
    # Try up to 5 times to get valid data
    max_attempts = 5
    
    for attempt in range(max_attempts):
        try:
            # Load concurs data
            concurs_data = load_concurs_anys()
            if not concurs_data:
                continue
            
            # Select year and jornada - use selected_years if provided
            year, jornada = select_year_jornada(concurs_data, selected_years=selected_years)
            if not year:
                continue
            
            # Query database for rankings
            with get_db_connection() as conn:
                cur = conn.cursor()
                
                # Build query based on whether jornada is specified
                if jornada:
                    query = """
                        SELECT colla_name, position
                        FROM concurs_rankings
                        WHERE "any" = %s AND jornada = %s
                        ORDER BY position ASC
                        LIMIT 10
                    """
                    cur.execute(query, (year, jornada))
                else:
                    query = """
                        SELECT colla_name, position
                        FROM concurs_rankings
                        WHERE "any" = %s AND (jornada = '' OR jornada IS NULL)
                        ORDER BY position ASC
                        LIMIT 10
                    """
                    cur.execute(query, (year,))
                
                rows = cur.fetchall()
                
                if not rows or len(rows) < 3:  # Need at least 3 colles
                    continue
                
                # Extract colles and positions
                colles_data = [(row[0], row[1]) for row in rows]
                
                # Sort by position to get correct order
                colles_data.sort(key=lambda x: x[1])
                correct_order = [colla_name for colla_name, _ in colles_data]
                options = correct_order.copy()
                
                # Shuffle options for display
                shuffle(options)
                
                # Format jornada for question
                if jornada:
                    jornada_text = f"de la {jornada}"
                else:
                    jornada_text = ""
                
                question = f"Ordena les colles en funció de la seva posició del ranking {jornada_text} del concurs de castells de l'any {year} "
                
                return QuestionOrdering(
                    question=question,
                    options=options,
                    correct_answer_order=correct_order
                )
                
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_attempts - 1:
                import traceback
                traceback.print_exc()
                return QuestionOrdering(
                    question="Ordena les colles en funció de la seva posició del ranking de la jornada XX de l'any XX del concurs de castells",
                    options=["Error al generar la resposta"],
                    correct_answer_order=[],
                    is_error=True
                )
            continue
    
    # If all attempts failed
    return QuestionOrdering(
        question="Ordena les colles en funció de la seva posició del ranking de la jornada XX de l'any XX del concurs de castells",
        options=["Error al generar la resposta"],
        correct_answer_order=[],
        is_error=True
    )
