import random
from enum import Enum
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


def generate_question_mcq_4_options(): 
    # Selects which question to generate randomly

    question_type = random.choice(list(QuestionTypeMCQ4Options)) # random choice of question type   

    if question_type == QuestionTypeMCQ4Options.BEST_DIADA:
        question = generate_best_diada_question()
    elif question_type == QuestionTypeMCQ4Options.BEST_CASTELL:
        question = generate_best_castell_question()
    elif question_type == QuestionTypeMCQ4Options.COLOR_CAMISA:
        question = generate_color_camisa_question()
    elif question_type == QuestionTypeMCQ4Options.ANY_FUNDACIO_COLLA:
        question = generate_any_fundacio_colla_question()
    elif question_type == QuestionTypeMCQ4Options.ACTUACIO_COLLA_DIADA:
        question = generate_actuacio_colla_diada_question()
    elif question_type == QuestionTypeMCQ4Options.COLLA_PRIMER_CASTELL:
        question = generate_colla_primer_castell_question()
    else:
        # Fallback - should not happen but just in case
        return None
    
    # Shuffle the answers to randomize the order
    answers = question.answers.copy()
    random.shuffle(answers)
    question.answers = answers

    return question


def generate_question_slider_input():
    question_type = random.choice(list(QuestionTypeSliderInput))
    if question_type == QuestionTypeSliderInput.ANY_FUNDACIO_COLLA:
        question = generate_any_slider_input_question()
    elif question_type == QuestionTypeSliderInput.CASTELLS_DESCARREGATS_ANY:
        question = generate_castells_descarregats_any_question()
    return question


def generate_question_mixed():
    """Generate a random question of any type"""
    # Probability distribution for different question types
    question_generators = {
        generate_question_mcq_4_options: 0.65,        
        generate_question_mcq_multiple_options: 0.15,  
        generate_question_slider_input: 0.2, 
        generate_question_ordering: 0.1,
    }
    
    # Select generator based on weighted probabilities
    generators = list(question_generators.keys())
    weights = list(question_generators.values())
    selected_generator = random.choices(generators, weights=weights, k=1)[0]
    
    return selected_generator()

def generate_question_ordering():
    question_type = QuestionTypeOrdering.RANKING_JORNADA #random.choice(list(QuestionTypeOrdering))
    if question_type == QuestionTypeOrdering.RANKING_JORNADA:
        question = generate_concurs_ranking_question()
    return question

def generate_question_mcq_multiple_options():
    question_type = QuestionTypeMCQMultipleOptions.ACTUACIO_COLLA_DIADA #random.choice(list(QuestionTypeMCQMultipleOptions))
    if question_type == QuestionTypeMCQMultipleOptions.ACTUACIO_COLLA_DIADA:
        question = generate_actuacio_multiple_options_question()
    return question

# Alias for backward compatibility with backend/main.py
# Use mixed questions to include slider input questions
generate_question = generate_question_mixed

