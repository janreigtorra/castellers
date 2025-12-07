from random import choice, shuffle
from passafaixa.schemas import QuestionMCQ4Options
import json
import re
from pathlib import Path


def generate_any_fundacio_colla_question() -> QuestionMCQ4Options:
    """
    Generate a multiple choice question about which colla was founded in a specific year.
    Filters out colles with names ending in (XXXX) or (XXXX-XXXX) pattern (historical periods).
    """
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.parent.parent
    
    colles_fundacio_file = script_dir / "colles_fundacio.json"
    
    try:
        # Load JSON data
        with open(colles_fundacio_file, "r", encoding="utf-8") as f:
            fundacio_data = json.load(f)
        
        # Filter out colles whose names end with (XXXX) or (XXXX-XXXX) pattern
        # Pattern matches: (YYYY) or (YYYY-YYYY) - single year or year ranges
        pattern = re.compile(r'\s*\(\d{4}(-\d{4})?\)\s*$')
        valid_colles = []
        
        for colla in fundacio_data:
            name = colla.get("name", "")
            any_primera_actuacio = colla.get("any_primera_actuacio", "")
            
            # Skip if name ends with (XXXX) or (XXXX-XXXX) pattern or missing required data
            if name and any_primera_actuacio and not pattern.search(name):
                valid_colles.append({
                    "name": name,
                    "year": any_primera_actuacio
                })
        
        if not valid_colles:
            # Fallback if no valid colles found
            return QuestionMCQ4Options(
                question="Quina de les seguents colles es va fundar l'any 1999?",
                answers=["Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions"],
                correct_answer="Error al obtenir les opcions",
                is_error=True
            )
        
        # Select a random colla
        selected_colla = choice(valid_colles)
        correct_colla_name = selected_colla["name"]
        target_year = selected_colla["year"]
        
        # Get 3 other colles with different years for wrong options
        other_colles = [c for c in valid_colles if c["name"] != correct_colla_name]
        used_years = {target_year}
        wrong_options = []
        
        for colla in other_colles:
            if colla["year"] not in used_years:
                wrong_options.append(colla["name"])
                used_years.add(colla["year"])
                if len(wrong_options) >= 3:
                    break
        
        # If we don't have 3 different colles, fill with any other colles
        while len(wrong_options) < 3:
            remaining = [c for c in other_colles if c["name"] not in wrong_options and c["name"] != correct_colla_name]
            if remaining:
                wrong_options.append(choice(remaining)["name"])
            else:
                # Fallback if we run out of colles
                fallback_names = ["Castellers de Cardona", "Castellers de Olius", "Gamberrus de Sant Llorenç"]
                for fallback in fallback_names:
                    if fallback not in wrong_options and fallback != correct_colla_name:
                        wrong_options.append(fallback)
                        if len(wrong_options) >= 3:
                            break
                break
        
        # Shuffle the options (correct answer + 3 wrong options)
        all_options = [correct_colla_name] + wrong_options[:3]
        shuffle(all_options)
        
        # Create question
        question = f"Quina de les seguents colles es va fundar l'any {target_year}?"
        
        return QuestionMCQ4Options(
            question=question,
            answers=all_options,
            correct_answer=correct_colla_name
        )
        
    except FileNotFoundError as e:
        print(f"Error: JSON file not found: {e}")
        # Fallback question
        return QuestionMCQ4Options(
            question="Quina de les seguents colles es va fundar l'any XXXX?",
            answers=["Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions"],
            correct_answer="Error al obtenir les opcions",
            is_error=True
        )
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        # Fallback question
        return QuestionMCQ4Options(
            question="Quina de les seguents colles es va fundar l'any XXXX?",
            answers=["Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions"],
            correct_answer="Error al obtenir les opcions",
            is_error=True
        )
    except Exception as e:
        print(f"Error generating any fundacio colla question: {e}")
        # Fallback question
        return QuestionMCQ4Options(
            question="Quina de les seguents colles es va fundar l'any XXXX?",
            answers=["Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions", "Error al obtenir les opcions"],
            correct_answer="Error al obtenir les opcions",
            is_error=True
        )