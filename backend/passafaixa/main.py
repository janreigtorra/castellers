import random
from enum import Enum
from typing import List, Optional
from .schemas import *

from .question_types.MCQ.best_diada_question import generate_best_diada_question
from .question_types.MCQ.best_castell_question import generate_best_castell_question
from .question_types.MCQ.color_camisa_question import generate_color_camisa_question
from .question_types.MCQ.any_fundacio_colla_question import generate_any_fundacio_colla_question
from .question_types.MCQ.actuacio_colla_diada_question import generate_actuacio_colla_diada_question
from .question_types.MCQ.primer_castell_question import generate_colla_primer_castell_question
from .question_types.slider_input.any_fundation_question import generate_any_slider_input_question
from .question_types.slider_input.castells_descarregats_question import generate_castells_descarregats_any_question
from .question_types.multiple_options.actuacio_questions import generate_actuacio_colla_diada_question as generate_actuacio_multiple_options_question
from .question_types.ordering.concurs_ranking_question import generate_concurs_ranking_question


# =============================================================================
# PROBABILITY CONFIGURATIONS - Adjust these to control question distribution
# =============================================================================

# Probabilities for MCQ 4 Options question types
MCQ_4_OPTIONS_PROBABILITIES = {
    QuestionTypeMCQ4Options.BEST_DIADA: 3,
    QuestionTypeMCQ4Options.BEST_CASTELL: 2,
    QuestionTypeMCQ4Options.COLOR_CAMISA: 1,
    QuestionTypeMCQ4Options.ANY_FUNDACIO_COLLA: 1,
    QuestionTypeMCQ4Options.ACTUACIO_COLLA_DIADA: 2,
    QuestionTypeMCQ4Options.COLLA_PRIMER_CASTELL: 1,
}


# MCQ 4 Options allowed when colles are selected (filtered subset)
MCQ_4_OPTIONS_COLLES_FILTER = {
    QuestionTypeMCQ4Options.BEST_DIADA: 1.0,
    QuestionTypeMCQ4Options.BEST_CASTELL: 1.0,
    QuestionTypeMCQ4Options.ACTUACIO_COLLA_DIADA: 1.0,
}

# MCQ 4 Options allowed when years are selected (filtered subset)
# Note: ACTUACIO_COLLA_DIADA is excluded when years are selected
MCQ_4_OPTIONS_YEARS_FILTER = {
    QuestionTypeMCQ4Options.BEST_DIADA: 1.0,
    QuestionTypeMCQ4Options.BEST_CASTELL: 1.0,
    QuestionTypeMCQ4Options.COLLA_PRIMER_CASTELL: 1.0,
}

# Probabilities for Slider Input question types
SLIDER_INPUT_PROBABILITIES = {
    QuestionTypeSliderInput.ANY_FUNDACIO_COLLA: 1.0,
    QuestionTypeSliderInput.CASTELLS_DESCARREGATS_ANY: 1.0,
}

# Slider Input allowed when colles are selected (filtered subset)
SLIDER_INPUT_COLLES_FILTER = {
    QuestionTypeSliderInput.CASTELLS_DESCARREGATS_ANY: 1.0,
}

# Slider Input allowed when years are selected (filtered subset)
SLIDER_INPUT_YEARS_FILTER = {
    QuestionTypeSliderInput.CASTELLS_DESCARREGATS_ANY: 1.0,
}

# Probabilities for main question generators (will be set after functions are defined)
QUESTION_GENERATOR_PROBABILITIES = {}  # Initialized after function definitions

# =============================================================================


def generate_question_mcq_4_options(selected_colles: List[str] = None, selected_years: List[int] = None): 
    # Use filtered probabilities based on selections
    if selected_colles and len(selected_colles) > 0:
        probs = MCQ_4_OPTIONS_COLLES_FILTER
    elif selected_years and len(selected_years) > 0:
        probs = MCQ_4_OPTIONS_YEARS_FILTER
    else:
        probs = MCQ_4_OPTIONS_PROBABILITIES
    
    # Selects which question to generate randomly based on probabilities
    types = list(probs.keys())
    weights = list(probs.values())
    question_type = random.choices(types, weights=weights, k=1)[0]   

    if question_type == QuestionTypeMCQ4Options.BEST_DIADA:
        question = generate_best_diada_question(selected_colles=selected_colles, selected_years=selected_years)
    elif question_type == QuestionTypeMCQ4Options.BEST_CASTELL:
        question = generate_best_castell_question(selected_colles=selected_colles, selected_years=selected_years)
    elif question_type == QuestionTypeMCQ4Options.COLOR_CAMISA:
        question = generate_color_camisa_question()
    elif question_type == QuestionTypeMCQ4Options.ANY_FUNDACIO_COLLA:
        question = generate_any_fundacio_colla_question()
    elif question_type == QuestionTypeMCQ4Options.ACTUACIO_COLLA_DIADA:
        question = generate_actuacio_colla_diada_question(selected_colles=selected_colles, selected_years=selected_years)
    elif question_type == QuestionTypeMCQ4Options.COLLA_PRIMER_CASTELL:
        question = generate_colla_primer_castell_question(selected_years=selected_years)
    else:
        # Fallback - should not happen but just in case
        return None
    
    # Shuffle the answers to randomize the order
    answers = question.answers.copy()
    random.shuffle(answers)
    question.answers = answers

    return question


def generate_question_slider_input(selected_colles: List[str] = None, selected_years: List[int] = None):
    # Use filtered probabilities based on selections
    if selected_colles and len(selected_colles) > 0:
        probs = SLIDER_INPUT_COLLES_FILTER
    elif selected_years and len(selected_years) > 0:
        probs = SLIDER_INPUT_YEARS_FILTER
    else:
        probs = SLIDER_INPUT_PROBABILITIES
    
    # Selects which question to generate randomly based on probabilities
    types = list(probs.keys())
    weights = list(probs.values())
    question_type = random.choices(types, weights=weights, k=1)[0]
    
    if question_type == QuestionTypeSliderInput.ANY_FUNDACIO_COLLA:
        question = generate_any_slider_input_question()
    elif question_type == QuestionTypeSliderInput.CASTELLS_DESCARREGATS_ANY:
        question = generate_castells_descarregats_any_question(selected_colles=selected_colles, selected_years=selected_years)
    return question

def generate_question_ordering(selected_colles: List[str] = None, selected_years: List[int] = None):
    question_type = QuestionTypeOrdering.RANKING_JORNADA #random.choice(list(QuestionTypeOrdering))
    if question_type == QuestionTypeOrdering.RANKING_JORNADA:
        question = generate_concurs_ranking_question(selected_years=selected_years)
    return question

def generate_question_mcq_multiple_options(selected_colles: List[str] = None, selected_years: List[int] = None):
    question_type = QuestionTypeMCQMultipleOptions.ACTUACIO_COLLA_DIADA #random.choice(list(QuestionTypeMCQMultipleOptions))
    if question_type == QuestionTypeMCQMultipleOptions.ACTUACIO_COLLA_DIADA:
        question = generate_actuacio_multiple_options_question(selected_colles=selected_colles, selected_years=selected_years)
    return question


def generate_question_mixed(selected_colles: List[str] = None, selected_years: List[int] = None):
    """Generate a random question of any type"""
    
    # If colles are selected, use filtered question generators
    if selected_colles and len(selected_colles) > 0:
        # Only allow question types that support colla filtering
        filtered_generators = {
            'mcq_4_options': 0.50,           # BEST_DIADA, BEST_CASTELL, ACTUACIO_COLLA_DIADA
            'mcq_multiple_options': 0.25,     # ACTUACIO_COLLA_DIADA (multiple options)
            'slider_input': 0.25,             # CASTELLS_DESCARREGATS_ANY
            # ordering is NOT included when colles are selected
        }
        
        generator_funcs = {
            'mcq_4_options': lambda: generate_question_mcq_4_options(selected_colles),
            'mcq_multiple_options': lambda: generate_question_mcq_multiple_options(selected_colles),
            'slider_input': lambda: generate_question_slider_input(selected_colles),
        }
        
        generators = list(filtered_generators.keys())
        weights = list(filtered_generators.values())
        selected_key = random.choices(generators, weights=weights, k=1)[0]
        return generator_funcs[selected_key]()
    
    # If years are selected, use filtered question generators
    if selected_years and len(selected_years) > 0:
        # Allow question types that support year filtering
        filtered_generators = {
            'mcq_4_options': 0.45,           # BEST_DIADA, BEST_CASTELL, ACTUACIO_COLLA_DIADA, COLLA_PRIMER_CASTELL
            'mcq_multiple_options': 0.20,     # ACTUACIO_COLLA_DIADA (multiple options)
            'slider_input': 0.20,             # CASTELLS_DESCARREGATS_ANY
            'ordering': 0.15,                 # RANKING_JORNADA
        }

        generator_funcs = {
            'mcq_4_options': lambda: generate_question_mcq_4_options(selected_years=selected_years),
            'mcq_multiple_options': lambda: generate_question_mcq_multiple_options(selected_years=selected_years),
            'slider_input': lambda: generate_question_slider_input(selected_years=selected_years),
            'ordering': lambda: generate_question_ordering(selected_years=selected_years),
        }
        
        generators = list(filtered_generators.keys())
        weights = list(filtered_generators.values())
        selected_key = random.choices(generators, weights=weights, k=1)[0]
        return generator_funcs[selected_key]()
    
    # Default behavior: use all question types
    generators = list(QUESTION_GENERATOR_PROBABILITIES.keys())
    weights = list(QUESTION_GENERATOR_PROBABILITIES.values())
    selected_generator = random.choices(generators, weights=weights, k=1)[0]
    
    return selected_generator()


# Initialize QUESTION_GENERATOR_PROBABILITIES after functions are defined
QUESTION_GENERATOR_PROBABILITIES.update({
    generate_question_mcq_4_options: 0.7,        
    generate_question_mcq_multiple_options: 0.15,  
    generate_question_slider_input: 0.2, 
    generate_question_ordering: 0.05,
})


# Main entry point for question generation
def generate_question(selected_colles: List[str] = None, selected_years: List[int] = None):
    """Generate a random question, optionally filtered by selected colles or years."""
    return generate_question_mixed(selected_colles=selected_colles, selected_years=selected_years)

