from random import choices
from passafaixa.schemas import QuestionSliderInput
import json
from pathlib import Path

HALF_POINT_MARGIN = 5

def load_colles_fundacio():
    """Load colles_fundacio.json file"""
    script_dir = Path(__file__).parent.parent.parent
    json_file = script_dir / "colles_fundacio.json"
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading colles_fundacio.json: {e}")
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


def generate_any_slider_input_question() -> QuestionSliderInput:
    min_year = 1950 
    max_year = 2025
    
    # Load data
    fundacio_data = load_colles_fundacio()
    colles_data = load_json_colles()
    
    if not fundacio_data or not colles_data:
        # Fallback
        return QuestionSliderInput(
            question="Quin any va ser la fundació de la colla XX?",
            slider_min=min_year,
            slider_max=max_year,
            slider_step=1,
            correct_answer=2000,
            half_point=HALF_POINT_MARGIN,
            is_error=True
        )
    
    # Create a mapping of colla_name -> boost for quick lookup
    # Filter out colles with parentheses at the end of their name (historical periods)
    boost_map = {
        colla["colla_name"]: colla.get("boost", 0) 
        for colla in colles_data 
        if not colla["colla_name"].strip().endswith(")")
    }
    
    # Filter colles by year range and get their boost values
    valid_colles = []
    weights = []
    
    for colla in fundacio_data:
        name = colla.get("name", "")
        any_primera_actuacio = colla.get("any_primera_actuacio", "")
        
        if not name or not any_primera_actuacio:
            continue
        
        # Skip colles with parentheses in their name (historical periods)
        if "(" in name or name.strip().endswith(")"):
            continue
        
        try:
            year = int(any_primera_actuacio)
            if min_year <= year <= max_year:
                # Get boost value (default to 0 if not found)
                boost = boost_map.get(name, 0)
                valid_colles.append({
                    "name": name,
                    "year": year
                })
                # Weight is boost + 1 to ensure positive weights
                weights.append(boost)
        except (ValueError, TypeError):
            continue
    
    if not valid_colles:
        # Fallback if no valid colles found
        return QuestionSliderInput(
            question="Quin any va ser la fundació de la colla XX?",
            slider_min=min_year,
            slider_max=max_year,
            slider_step=1,
            correct_answer=2000,
            half_point=HALF_POINT_MARGIN,
            is_error=True
        )
    
    # Select a random colla weighted by boost
    selected_colla = choices(valid_colles, weights=weights, k=1)[0]
    colla_name = selected_colla["name"]
    foundation_year = selected_colla["year"]
    
    return QuestionSliderInput(
        question=f"Quin any va ser la fundació de la colla {colla_name}?",
        slider_min=min_year,
        slider_max=max_year,
        slider_step=1,
        correct_answer=foundation_year,
        half_point=HALF_POINT_MARGIN
    )
