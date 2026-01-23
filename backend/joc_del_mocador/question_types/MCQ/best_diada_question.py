from random import random, choice
from typing import List, Optional
from joc_del_mocador.schemas import QuestionMCQ4Options
from joc_del_mocador.questions_utils import get_random_year, get_random_colla
from joc_del_mocador.db_pool import get_db_connection
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_diada_question_data(colla: str = None, year: str = None) -> tuple:

    if not DATABASE_URL:
        # Return fallback values instead of None
        return (("", "", ""), ["", "", ""])
    
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
            
            # Single query to get top 6 diades with points calculation using CTE
            query = f"""
               WITH castells_punts AS (
                SELECT 
                    e.id AS event_id,
                    e.name AS event_name,
                    e.date AS event_date,
                    e.place AS event_place,
                    e.city AS event_city,
                    co.id AS colla_id,
                    co.name AS colla_name,
                    c.id AS castell_id,
                    c.castell_name,
                    c.status,
                    CASE 
                        WHEN c.status = 'Descarregat' THEN COALESCE(p.punts_descarregat, 0)
                        WHEN c.status = 'Carregat' THEN COALESCE(p.punts_carregat, 0)
                        ELSE 0
                    END AS punts,
                    CASE
                        WHEN c.castell_name ~ '^[0-9]' THEN 'castell'
                        WHEN c.castell_name ~ '^[Pp]' THEN 'pilar'
                        ELSE 'altres'
                    END AS tipus
                FROM events e
                JOIN event_colles ec ON e.id = ec.event_fk
                JOIN colles co ON ec.colla_fk = co.id
                JOIN castells c ON ec.id = c.event_colla_fk
                LEFT JOIN puntuacions p ON (
                    c.castell_name = p.castell_code_external 
                    OR c.castell_name = p.castell_code
                    OR c.castell_name = p.castell_code_name
                )
                WHERE 1=1
                {colla_filter}
                {year_filter}
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY event_id, colla_id, tipus
                        ORDER BY punts DESC
                    ) AS rn_tipus
                FROM castells_punts
            ),
            millors_castells AS (
                SELECT *
                FROM ranked
                WHERE
                    (tipus = 'castell' AND rn_tipus <= 3)
                    OR
                    (tipus = 'pilar' AND rn_tipus = 1)
            )
            SELECT
                event_id,
                event_name,
                event_date,
                colla_name,
                event_place,
                event_city,
                COUNT(castell_id) AS num_castells,
                SUM(punts) AS total_punts,
                STRING_AGG(
                    castell_name || ' (' || status || ', ' || punts || ')',
                    ', '
                    ORDER BY punts DESC
                ) AS castells_comptats
            FROM millors_castells
            GROUP BY
                event_id,
                event_name,
                event_date,
                event_place,
                event_city,
                colla_name
            ORDER BY total_punts DESC
            LIMIT 4;

            """
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            if not rows or len(rows) == 0:
                # Return fallback values instead of None
                return (("", "", ""), ["", "", ""])
            
            # Get the top result (position 1) as correct answer
            # Row structure: event_id, event_name, event_date, colla_name, event_place, event_city, num_castells, total_punts, top4_castells
            correct_row = rows[0]
            correct_event_name = correct_row[1] or "Diada castellera"
            correct_event_date = correct_row[2] or ""
            correct_colla_name = correct_row[3] or ""
            correct_event_city = correct_row[5] or ""  # city
            correct_castells_fets = correct_row[8] or ""  # top4_castells
            
            # Format correct answer: "event name, city (year or colla if so)"
            if correct_event_city in correct_event_name:
                formatted_correct = f"{correct_event_name}"
            else:
                formatted_correct = f"{correct_event_name}, {correct_event_city}"
            
            # Add year if provided, otherwise add colla if colla is not provided
            if not year and correct_event_date:
                formatted_correct += f" ({correct_event_date})"
            elif not colla and correct_colla_name:
                formatted_correct += f" ({correct_colla_name})"
            
            formatted_correct = formatted_correct.strip()
            
            # Return correct answer as tuple: [formatted_string, castells_fets]
            correct_answer = (formatted_correct, correct_castells_fets or "")
            
            # Get positions 2-4 (indices 1-3) for options
            options_2_to_4 = rows[1:4]
            
            # Randomly select 3 from positions 2-4 and format them
            selected_options = []
            available = list(options_2_to_4)
            
            for _ in range(3):
                if available:
                    chosen = choice(available)
                    available.remove(chosen)
                    # Row structure: event_id, event_name, event_date, colla_name, event_place, event_city, num_castells, total_punts, top4_castells
                    event_name = chosen[1]
                    event_date = chosen[2]
                    colla_name = chosen[3]
                    event_city = chosen[5]  # city
                    
                    # Format: "event name, city (year or colla if so)"
                    event_name = event_name or "Diada castellera"
                    event_city = event_city or ""
                    event_date = event_date or ""
                    colla_name = colla_name or ""
                    
                    if event_city in event_name:
                        formatted_option = f"{event_name}"
                    else:
                        formatted_option = f"{event_name}, {event_city}"
                    
                    # Add year if provided, otherwise add colla if colla is not provided
                    if not year and event_date:
                        formatted_option += f" ({event_date})"
                    elif not colla and colla_name:
                        formatted_option += f" ({colla_name})"
                    
                    selected_options.append(formatted_option.strip())
                else:
                    # Fallback if we run out
                    fallbacks = ["Sant Fèlix, Vilafranca", "Santa Tecla, Tarragona", "El Mercadal, Vilafranca"]
                    selected_options.append(fallbacks[len(selected_options)])
            
            return (correct_answer, selected_options)
        
    except Exception as e:
        import traceback
        print(f"Error getting diada question data: {e}")
        traceback.print_exc()
        # Return empty values to trigger error handling in the generate function
        return (("", ""), ["", "", ""])

def generate_best_diada_question(selected_colles: List[str] = None, selected_years: List[int] = None) -> QuestionMCQ4Options:
    """
    Generate a question asking which was the best diada for a colla/year.
    
    Args:
        selected_colles: Optional list of colla names to pick from when add_colla is True.
        selected_years: Optional list of years to pick from when add_year is True.
    """
    if not DATABASE_URL:
        return QuestionMCQ4Options(
            question="Quin va ser la millor actuació castellera: Error?",
            answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
            correct_answer="Error al generar la resposta",
            is_error=True
        )
    
    # Try up to 5 times to get a valid colla/year combination with diades
    max_attempts = 5
    correct_answer_tuple = None
    options = None
    colla = None
    year = None
    
    for attempt in range(max_attempts):
        try:
            # Let's decide if we add the year to the question or not
            # If selected_years is provided, always add year (True)
            if selected_years and len(selected_years) > 0:
                add_year = True
            else:
                add_year = random() < 0.70
            
            year = None
            if add_year:
                # Get a random year - use selected_years if provided (equal probability)
                year = get_random_year(selected_years=selected_years)

            # Let's decide if we add the colla to the question or not
            # If selected_colles is provided, always add colla (True)
            if selected_colles and len(selected_colles) > 0:
                add_colla = True
            elif not add_year:
                add_colla = True
            else:
                add_colla = random() < 0.50

            colla = None
            if add_colla:
                # Use selected_colles if provided (equal probability), otherwise use weighted random
                colla = get_random_colla(year, selected_colles=selected_colles)

            # Get both correct answer and options in a single query
            correct_answer_tuple, options = get_diada_question_data(colla, year)
            
            # If we got valid data, break out of retry loop
            if (correct_answer_tuple and isinstance(correct_answer_tuple, tuple) and len(correct_answer_tuple) > 0 
                and correct_answer_tuple[0] and options and isinstance(options, list) and len(options) >= 3):
                break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_attempts - 1:
                import traceback
                traceback.print_exc()
                return QuestionMCQ4Options(
                    question="Quin va ser la millor actuació castellera: Error?",
                    answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
                    correct_answer="Error al generar la resposta",
                    is_error=True
                )
            continue
    
    # Check if we have valid data after retries
    if not correct_answer_tuple or not isinstance(correct_answer_tuple, tuple) or len(correct_answer_tuple) == 0 or not correct_answer_tuple[0]:
        return QuestionMCQ4Options(
            question="Quin va ser la millor actuació castellera: Error?",
            answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
            correct_answer="Error al generar la resposta",
            is_error=True
        )
    
    try:
        # correct_answer_tuple is [formatted_string, castells_fets]
        diada_correcte = str(correct_answer_tuple[0]) if correct_answer_tuple[0] else "Error al generar la resposta"
        
        if options and isinstance(options, list) and len(options) >= 3:
            diada_opcion1 = str(options[0]) if options[0] else "Error al generar la resposta"
            diada_opcion2 = str(options[1]) if options[1] else "Error al generar la resposta"
            diada_opcion3 = str(options[2]) if options[2] else "Error al generar la resposta"
        else:
            return QuestionMCQ4Options(
                question="Quin va ser la millor actuació castellera: Error?",
                answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
                correct_answer="Error al generar la resposta",
                is_error=True
            )

        question = f"Quin va ser la millor actuació castellera " 
        if colla is not None:
            question += f"dels {colla} "
        if year is not None:
            question += f"l'any {year}"
        else:
            question += " al llarg de la seva història"
        question += "?"

        return QuestionMCQ4Options(
            question=question,
            answers=[diada_correcte, diada_opcion1, diada_opcion2, diada_opcion3],
            correct_answer=diada_correcte
        )
        
    except Exception as e:
        import traceback
        print(f"Error generating best diada question: {e}")
        traceback.print_exc()
        return QuestionMCQ4Options(
            question="Quin va ser la millor actuació castellera: Error?",
            answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
            correct_answer="Error al generar la resposta",
            is_error=True
        )