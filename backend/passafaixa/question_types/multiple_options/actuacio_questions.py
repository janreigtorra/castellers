from random import choice, shuffle
from typing import List, Optional
from passafaixa.schemas import QuestionMCQMultipleOptions
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
    script_dir = Path(__file__).parent.parent.parent
    json_file = script_dir / "castells_puntuacions.json"
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading castells_puntuacions.json: {e}")
        return []


def find_similar_castells(correct_castells: list, castells_data: list, num_options: int = 2) -> list:
    """Find castells with similar points to the correct castells"""
    if not castells_data or not correct_castells:
        return []
    
    # Calculate average points of correct castells
    total_points = 0
    count = 0
    correct_castell_names = set()
    
    for castell_name, status in correct_castells:
        correct_castell_names.add(castell_name.lower().strip())
        # Find points for this castell
        for castell in castells_data:
            castell_code_external = castell.get("castell_code_external", "").strip().lower()
            castell_code = castell.get("castell_code", "").strip().lower()
            
            if (castell_code_external == castell_name.lower().strip() or 
                castell_code == castell_name.lower().strip()):
                if status == "Descarregat":
                    total_points += castell.get("punts_descarregat", 0)
                elif status == "Carregat":
                    total_points += castell.get("punts_carregat", 0)
                count += 1
                break
    
    if count == 0:
        return []
    
    avg_points = total_points / count
    
    # Find castells with similar points (±20% range, minimum ±200 points)
    min_points = max(0, avg_points - max(200, int(avg_points * 0.2)))
    max_points = avg_points + max(200, int(avg_points * 0.2))
    
    similar_castells = []
    seen_castells = set()
    
    for castell in castells_data:
        castell_code_external = castell.get("castell_code_external", "").strip()
        castell_code = castell.get("castell_code", "").strip()
        castell_code_to_use = castell_code_external or castell_code
        
        # Skip if this is one of the correct castells
        if castell_code_to_use.lower().strip() in correct_castell_names:
            continue
        
        # Skip if we've already added this castell
        if castell_code_to_use in seen_castells:
            continue
        
        # Check both descarregat and carregat points
        desc_punts = castell.get("punts_descarregat", 0)
        carr_punts = castell.get("punts_carregat", 0)
        
        # Add if either status has similar points
        if min_points <= desc_punts <= max_points:
            similar_castells.append((castell_code_to_use, "Descarregat"))
            seen_castells.add(castell_code_to_use)
        elif min_points <= carr_punts <= max_points:
            similar_castells.append((castell_code_to_use, "Carregat"))
            seen_castells.add(castell_code_to_use)
    
    # Randomly select up to num_options
    if len(similar_castells) <= num_options:
        return similar_castells
    else:
        shuffle(similar_castells)
        return similar_castells[:num_options]


def generate_actuacio_colla_diada_question(selected_colles: List[str] = None, selected_years: List[int] = None) -> QuestionMCQMultipleOptions:
    """
    Generate a question asking which castells were made in a specific actuació.
    Returns 8 options: 4 correct castells + 4 wrong options (2 same castells different status + 2 similar castells).
    
    Args:
        selected_colles: Optional list of colla names to pick from.
        selected_years: Optional list of years to pick from.
    """
    if not DATABASE_URL:
        return QuestionMCQMultipleOptions(
            question="Quina va ser l'actuació de la colla XX a la diada XX l'any XX? Selecciona tots els castells fets.",
            options=["Error al generar la resposta"] * 8,
            correct_answer=[],
            is_error=True
        )
    
    # Try up to 5 times to get valid data
    max_attempts = 5
    
    for attempt in range(max_attempts):
        try:
            # Get a random year - use selected_years if provided (equal probability)
            year = get_random_year(selected_years=selected_years)
            
            # Get a random colla that was active in that year
            # Use selected_colles if provided (equal probability), otherwise use weighted random
            colla = get_random_colla(year, selected_colles=selected_colles)
            
            with get_db_connection() as conn:
                cur = conn.cursor()
                
                # Get all diades with castells for this colla in this year
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
                
                if not rows or len(rows) == 0:
                    continue
            
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
                
                # Store all castells
                events_data[event_id]['castells'].append((castell_name, status, punts))
            
            # Get top 3 events by total points
            top_events = sorted(events_data.items(), key=lambda x: x[1]['total_punts'], reverse=True)[:3]
            
            if not top_events:
                continue
            
            # Choose one of the top 3 diades at random
            selected_event_id, selected_event_data = choice(top_events)
            event_name = selected_event_data['event_name']
            event_date = selected_event_data['event_date']
            colla_name = selected_event_data['colla_name']
            event_city = selected_event_data['event_city']
            all_castells = selected_event_data['castells']
            
            # Filter castells: exclude Pd4, Pde4, and if more than 8, also exclude Pd5, Pde5
            filtered_castells = []
            for castell_name, status, punts in all_castells:
                if not castell_name:
                    continue
                castell_upper = castell_name.upper()
                if castell_upper.startswith('PD4') or castell_upper.startswith('PDE4'):
                    continue
                if len(all_castells) > 8:
                    if castell_upper.startswith('PD5') or castell_upper.startswith('PDE5'):
                        continue
                filtered_castells.append((castell_name, status, punts))
            
            # Deduplicate: keep best status for each castell
            castell_dict = {}
            status_priority = {"Descarregat": 1, "Carregat": 2}
            
            for castell_name, status, punts in filtered_castells:
                if castell_name not in castell_dict:
                    castell_dict[castell_name] = (status, punts)
                else:
                    current_priority = status_priority.get(castell_dict[castell_name][0], 99)
                    new_priority = status_priority.get(status, 99)
                    if new_priority < current_priority:
                        castell_dict[castell_name] = (status, punts)
            
            # Get top 4 castells by points (these are the correct answers)
            sorted_castells = sorted(castell_dict.items(), key=lambda x: x[1][1], reverse=True)[:4]
            
            if len(sorted_castells) < 4:
                continue
            
            correct_castells = [(name, status) for name, (status, _) in sorted_castells]
            
            # Generate wrong options
            wrong_options = []
            
            # 2 options: same castells but different status
            for castell_name, status in correct_castells[:2]:
                if status == "Descarregat":
                    wrong_options.append((castell_name, "Carregat"))
                else:
                    wrong_options.append((castell_name, "Descarregat"))
            
            # 2 options: similar castells (different castells with similar points)
            castells_data = load_castells_puntuacions()
            similar_castells = find_similar_castells(correct_castells, castells_data, num_options=2)
            wrong_options.extend(similar_castells)
            
            # Ensure we have exactly 4 wrong options
            while len(wrong_options) < 4:
                wrong_options.append(("4d8ps", "Descarregat"))
            
            # Format options
            correct_answers = [f"{name} ({status})" for name, status in correct_castells]
            all_wrong = [f"{name} ({status})" for name, status in wrong_options[:4]]
            
            # Combine and shuffle all options
            all_options = correct_answers + all_wrong
            shuffle(all_options)
            
            # Format diada name
            if event_city and event_city not in event_name:
                formatted_diada = f"{event_name}, {event_city}"
            else:
                formatted_diada = event_name or "Diada castellera"
            
            if 'diada' not in formatted_diada.lower():
                formatted_diada = f"diada {formatted_diada}"
            
            # Create question
            question = f"Quina va ser l'actuació de la colla castellera {colla_name} a la {formatted_diada} l'any {year}? Selecciona les 4 construccions fetes."
            
            return QuestionMCQMultipleOptions(
                question=question,
                options=all_options,
                correct_answer=correct_answers
            )
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_attempts - 1:
                import traceback
                traceback.print_exc()
                return QuestionMCQMultipleOptions(
                    question="Quina va ser l'actuació de la colla XX a la diada XX l'any XX? Selecciona tots els castells fets.",
                    options=["Error al generar la resposta"] * 8,
                    correct_answer=[],
                    is_error=True
                )
            continue
    
    # If all attempts failed
    return QuestionMCQMultipleOptions(
        question="Quina va ser l'actuació de la colla XX a la diada XX l'any XX? Selecciona tots els castells fets.",
        options=["Error al generar la resposta"] * 8,
        correct_answer=[],
        is_error=True
    )
