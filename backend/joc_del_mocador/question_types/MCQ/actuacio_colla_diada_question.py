from random import choice, shuffle, randint
from typing import List, Optional
from joc_del_mocador.schemas import QuestionMCQ4Options
from joc_del_mocador.questions_utils import get_random_year, get_random_colla
from joc_del_mocador.db_pool import get_db_connection
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_actuacio_question_data(colla: str, year: str) -> tuple:
    """
    Get actuació data for a specific colla and year.
    Returns: (correct_answer_tuple, wrong_options_list)
    correct_answer_tuple: (colla_name, event_name, event_date, castells_list)
    """
    if not DATABASE_URL:
        return (("", "", "", ""), ["", "", ""])
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Get top 4 diades with all their castells for this colla in this year
            query = """
                SELECT 
                    e.id AS event_id,
                    e.name AS event_name,
                    e.date AS event_date,
                    e.city AS event_city,
                    co.name AS colla_name,
                    c.castell_name,
                    c.status,
                    CASE 
                        WHEN c.status = 'Descarregat' THEN COALESCE(p.punts_descarregat, 0)
                        WHEN c.status = 'Carregat' THEN COALESCE(p.punts_carregat, 0)
                        ELSE 0
                    END AS punts
                FROM events e
                JOIN event_colles ec ON e.id = ec.event_fk
                JOIN colles co ON ec.colla_fk = co.id
                JOIN castells c ON ec.id = c.event_colla_fk
                LEFT JOIN puntuacions p ON (
                    c.castell_name = p.castell_code_external 
                    OR c.castell_name = p.castell_code
                    OR c.castell_name = p.castell_code_name
                )
                WHERE co.name = %s
                AND EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) = %s::integer
                ORDER BY e.id, punts DESC
            """
            
            cur.execute(query, (colla, year))
            rows = cur.fetchall()
            cur.close()
            
            if not rows or len(rows) == 0:
                return (("", "", "", ""), ["", "", ""])
        
        # Group by event and calculate total points (top 4 castells per event)
        events_data = {}
        for row in rows:
            event_id = row[0]
            event_name = row[1]
            event_date = row[2]
            event_city = row[3]
            colla_name = row[4]
            castell_name = row[5]
            status = row[6]
            punts = row[7]
            
            if event_id not in events_data:
                events_data[event_id] = {
                    'event_name': event_name,
                    'event_date': event_date,
                    'event_city': event_city,
                    'colla_name': colla_name,
                    'castells': [],
                    'total_punts': 0,
                    'castell_count': 0
                }
            
            # Only count top 4 castells for points calculation
            if events_data[event_id]['castell_count'] < 4:
                events_data[event_id]['total_punts'] += punts
                events_data[event_id]['castell_count'] += 1
            
            # Store all castells for later filtering
            events_data[event_id]['castells'].append((castell_name, status))
        
        # Get top 4 events by total points (OUTSIDE the for loop now)
        top_events = sorted(events_data.items(), key=lambda x: x[1]['total_punts'], reverse=True)[:4]
        
        if not top_events:
            return (("", "", "", ""), ["", "", ""])
    
        # Choose one of the top 4 diades at random
        selected_event_id, selected_event_data = choice(top_events)
        event_id = selected_event_id
        event_name = selected_event_data['event_name']
        event_date = selected_event_data['event_date']
        colla_name = selected_event_data['colla_name']
        event_city = selected_event_data['event_city']
        all_castells = selected_event_data['castells']
        
        # Filter castells according to rules:
        # - Do not include ones that start with 'Pd4%' or 'Pde4%'
        # - If there are more than 6, do not include ones that start with 'Pd5%' or 'Pde5%'
        filtered_castells = []
        for castell_name, status in all_castells:
            if not castell_name:
                continue
            castell_upper = castell_name.upper()
            # Skip Pd4 or Pde4
            if castell_upper.startswith('PD4') or castell_upper.startswith('PDE4'):
                continue
            # If more than 6 castells, also skip Pd5 or Pde5
            if len(all_castells) > 6:
                if castell_upper.startswith('PD5') or castell_upper.startswith('PDE5'):
                    continue
            filtered_castells.append((castell_name, status))
        
        # Deduplicate castells: if same castell appears multiple times, keep only the best status
        # Priority: Descarregat > Carregat > others
        castell_dict = {}
        status_priority = {"Descarregat": 1, "Carregat": 2}
        
        for castell_name, status in filtered_castells:
            if castell_name not in castell_dict:
                castell_dict[castell_name] = status
            else:
                # Keep the status with higher priority (lower number)
                current_priority = status_priority.get(castell_dict[castell_name], 99)
                new_priority = status_priority.get(status, 99)
                if new_priority < current_priority:
                    castell_dict[castell_name] = status
        
        # Format castells list for question
        castells_list = ", ".join([f"{name} ({status})" for name, status in castell_dict.items()])
        
        # If no castells after filtering, return error
        if not castells_list or len(castell_dict) == 0:
            return (("", "", "", ""), ["", "", ""])
        
        # Format correct answer: "Colla, Diada (Year)"
        if event_city and event_city not in event_name:
            formatted_diada = f"{event_name}, {event_city}"
        else:
            formatted_diada = event_name or "Diada castellera"
        
        correct_answer = f"{colla_name}, {formatted_diada} ({year})"
        
        # Get wrong options: different diades and different years
        wrong_options = []
        
        # 1. Same colla, different diades (from the other top diades)
        other_events = [(eid, edata) for eid, edata in top_events if eid != event_id]
        for other_event_id, other_event_data in other_events:
            if len(wrong_options) >= 3:
                break
            diada_name = other_event_data['event_name'] or "Diada castellera"
            diada_city = other_event_data['event_city']
            if diada_city and diada_city not in diada_name:
                formatted = f"{diada_name}, {diada_city}"
            else:
                formatted = diada_name or "Diada castellera"
            wrong_options.append(f"{colla_name}, {formatted} ({year})")
        
        # 2. Same diada, different year (randomly sample years ±5 from correct year)
        if len(wrong_options) < 3:
            year_int = int(year)
            used_years = {year_int}
            
            # Generate up to 2 different years within ±5 of the correct year
            attempts = 0
            while len(wrong_options) < 3 and attempts < 20:
                offset = randint(-5, 5)
                other_year_int = year_int + offset
                # Make sure it's different and reasonable (between 1960 and 2025)
                if other_year_int != year_int and 1960 <= other_year_int <= 2025 and other_year_int not in used_years:
                    other_year = str(other_year_int)
                    used_years.add(other_year_int)
                    if event_city and event_city not in event_name:
                        formatted = f"{event_name}, {event_city}"
                    else:
                        formatted = event_name or "Diada castellera"
                    wrong_options.append(f"{colla_name}, {formatted} ({other_year})")
                attempts += 1
        
        # Fill remaining slots with error fallbacks if needed
        while len(wrong_options) < 3:
            wrong_options.append("Error al generar la resposta")
        
        return ((colla_name, formatted_diada, year, castells_list), wrong_options[:3])
        
    except Exception as e:
        import traceback
        print(f"Error getting actuacio question data: {e}")
        traceback.print_exc()
        cur.close()
        return (("", "", "", ""), ["", "", ""])


def generate_actuacio_colla_diada_question(selected_colles: List[str] = None, selected_years: List[int] = None) -> QuestionMCQ4Options:
    """
    Generate a question asking which colla, diada, and year had a specific actuació castellera.
    If only one colla is selected, the question asks only about the diada.
    
    Args:
        selected_colles: Optional list of colla names to pick from.
        selected_years: Optional list of years to pick from.
    """
    if not DATABASE_URL:
        return QuestionMCQ4Options(
            question="Quina colla castellera i en quina diada es va fer la seguent actuació: Error?",
            answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
            correct_answer="Error al generar la resposta",
            is_error=True
        )
    
    # Determine if we're asking only for diada (single colla selected)
    single_colla_mode = selected_colles and len(selected_colles) == 1
    
    # Try up to 5 times to get a valid colla/year combination with events
    max_attempts = 5
    correct_answer_tuple = None
    wrong_options = None
    
    for attempt in range(max_attempts):
        try:
            # Get a random year - use selected_years if provided (equal probability)
            year = get_random_year(selected_years=selected_years)
            
            # Get a random colla that was active in that year
            # Use selected_colles if provided (equal probability), otherwise use weighted random
            colla = get_random_colla(year, selected_colles=selected_colles)
            
            correct_answer_tuple, wrong_options = get_actuacio_question_data(colla, year)
            
            # If we got valid data with castells, break out of retry loop
            if correct_answer_tuple and correct_answer_tuple[3] and len(correct_answer_tuple[3]) > 0:
                break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_attempts - 1:
                # Last attempt failed, return error
                import traceback
                traceback.print_exc()
                return QuestionMCQ4Options(
                    question="Quina colla castellers i en quina diada es va fer la seguent actuació: Error?",
                    answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
                    correct_answer="Error al generar la resposta",
                    is_error=True
                )
            continue
    
    # Check if we have valid data after retries
    if not correct_answer_tuple or not correct_answer_tuple[3] or len(correct_answer_tuple[3]) == 0:
        return QuestionMCQ4Options(
            question="Quina colla castellers i en quina diada es va fer la seguent actuació: Error?",
            answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
            correct_answer="Error al generar la resposta",
            is_error=True
        )
    
    try:
        colla_name = correct_answer_tuple[0]
        diada_name = correct_answer_tuple[1]
        year_str = correct_answer_tuple[2]
        castells_list = correct_answer_tuple[3]
        
        # Format correct answer
        correct_answer = f"{colla_name}, {diada_name} ({year_str})"
        
        # Ensure we have 3 wrong options
        if not wrong_options:
            wrong_options = []
        while len(wrong_options) < 3:
            wrong_options.append("Error al generar la resposta")
        
        # Shuffle all options
        all_options = [correct_answer] + wrong_options[:3]
        shuffle(all_options)
        
        # Create question - if single colla mode, only ask about diada
        if single_colla_mode:
            question = f"En quina diada va fer la colla {colla_name} la següent actuació: {castells_list}?"
        else:
            question = f"Quina colla castellera i en quina diada es va fer la seguent actuació: {castells_list}?"
        
        return QuestionMCQ4Options(
            question=question,
            answers=all_options,
            correct_answer=correct_answer
        )
        
    except Exception as e:
        import traceback
        print(f"Error generating actuacio colla diada question: {e}")
        traceback.print_exc()
        return QuestionMCQ4Options(
            question="Quina colla castellers i en quina diada es va fer la seguent actuació: Error?",
            answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
            correct_answer="Error al generar la resposta",
            is_error=True
        )
