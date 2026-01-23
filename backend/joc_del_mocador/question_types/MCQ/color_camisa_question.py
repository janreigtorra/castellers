from random import choices, shuffle
from joc_del_mocador.schemas import QuestionMCQ4Options
import json
from pathlib import Path


def generate_color_camisa_question() -> QuestionMCQ4Options:

    # Get the directory where this script is located
    script_dir = Path(__file__).parent.parent.parent
    
    json_colles_file = script_dir / "json_colles.json"
    colles_fundacio_file = script_dir / "colles_fundacio.json"
    
    try:
        # Load JSON data
        with open(json_colles_file, "r", encoding="utf-8") as f:
            colles_data = json.load(f)
        
        with open(colles_fundacio_file, "r", encoding="utf-8") as f:
            fundacio_data = json.load(f)
        
        # Create mappings: colla_name -> boost, and name -> color_camisa
        colla_boost_map = {colla["colla_name"]: colla.get("boost", 0) for colla in colles_data}
        colla_color_map = {colla["name"]: colla.get("color_camisa", "") for colla in fundacio_data}
        
        # Find colles that exist in both files and have a color_camisa
        valid_colles = []
        colla_weights = []
        
        for colla_name, boost in colla_boost_map.items():
            if colla_name in colla_color_map and colla_color_map[colla_name]:
                valid_colles.append(colla_name)
                # Weight is boost + 1 (so boost=0 still has weight 1)
                colla_weights.append(boost + 1)
        
        if not valid_colles:
            # Fallback if no valid colles found
            return QuestionMCQ4Options(
                question="Quin és el color de camisa dels Castellers de Vilafranca?",
                answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
                correct_answer="Error al generar la resposta",
                is_error=True
            )
        
        # Select a random colla using boost weighting
        selected_colla = choices(valid_colles, weights=colla_weights, k=1)[0]
        correct_color = colla_color_map[selected_colla]
        
        # Get 3 other colles with different colors for wrong options
        other_colles = [c for c in valid_colles if c != selected_colla]
        other_colors = []
        used_colors = {correct_color}
        
        for colla in other_colles:
            color = colla_color_map[colla]
            if color and color not in used_colors:
                other_colors.append(color)
                used_colors.add(color)
                if len(other_colors) >= 3:
                    break
        
        # If we don't have 3 different colors, fill with fallback colors
        fallback_colors = ["Blau", "Verd", "Groc", "Lila", "Bordeus", "Blanc"]
        while len(other_colors) < 3:
            for fallback in fallback_colors:
                if fallback not in used_colors:
                    other_colors.append(fallback)
                    used_colors.add(fallback)
                    break
            else:
                # If all fallbacks are used, just add generic colors
                other_colors.extend(["Blau", "Verd", "Groc"][:3 - len(other_colors)])
                break
        
        # Shuffle the options (correct answer + 3 wrong options)
        all_options = [correct_color] + other_colors[:3]
        # Shuffle to randomize position
        shuffle(all_options)
        
        # Create question
        question = f"Quin és el color de camisa la colla {selected_colla}?"
        
        return QuestionMCQ4Options(
            question=question,
            answers=all_options,
            correct_answer=correct_color
        )
        
    except FileNotFoundError as e:
        print(f"Error: JSON file not found: {e}")
        # Fallback question
        return QuestionMCQ4Options(
            question="Quin és el color de camisa dels Castellers de Vilafranca?",
            answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
            correct_answer="Error al generar la resposta",
            is_error=True
        )
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        # Fallback question
        return QuestionMCQ4Options(
            question="Quin és el color de camisa dels Castellers de Vilafranca?",
            answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
            correct_answer="Error al generar la resposta",
            is_error=True
        )
    except Exception as e:
        print(f"Error generating color camisa question: {e}")
        # Fallback question
        return QuestionMCQ4Options(
            question="Quin és el color de camisa dels Castellers de Vilafranca?",
            answers=["Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta", "Error al generar la resposta"],
            correct_answer="Error al generar la resposta",
            is_error=True
        )

