from enum import Enum
from pydantic import BaseModel
from typing import List, Optional

class QuestionTypeMCQ4Options(Enum):
    BEST_DIADA = "best_diada"
    BEST_CASTELL = "best_castell"
    COLOR_CAMISA = "color_camisa"  # Color de camisa de la colla XX?
    ANY_FUNDACIO_COLLA = "any_fundacio_colla"  # Quina colla es va fundar l'any XX?
    ACTUACIO_COLLA_DIADA = "actuacio_colla_diada"  # Quina colla i diada es va fer la seguent actuació castellera: XdX, XdX, XdX, PdX?
    COLLA_PRIMER_CASTELL = "colla_primer_castell"  # Quina colla va fer el primer XdX l'any XX?

class QuestionTypeSliderInput(Enum):
    ANY_FUNDACIO_COLLA = "any_fundacio_colla"  # Quina colla es va fundar l'any XX?
    CASTELLS_DESCARREGATS_ANY = "castells_descarregats_any"  # Quants castells es van descarregar la colla XX l'any XX?

class QuestionTypeOrdering(Enum):
    RANKING_JORNADA = "ranking_jornada"  # Ordena les colles en funció de la seva posició del ranking de la jornada XX de l'any XX del concurs de castells

class QuestionTypeMCQMultipleOptions(Enum):
    ACTUACIO_COLLA_DIADA = "actuacio_colla_diada"  # Quina colla i diada es va fer la seguent actuació castellera: XdX, XdX, XdX, PdX?


class QuestionMCQ4Options(BaseModel):
    # Will have a question, set of answers and the correct answer
    question: str
    answers: List[str]
    correct_answer: str
    explanation: Optional[str] = None
    is_error: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Quin va ser la millor diada dels Castellers de Vilafranca l'any 2013?",
                "answers": ["TotSants", "Sant Fèlix", "Santa Tecla", "El Mercadal"],
                "correct_answer": "TotSants",
                "explanation": "Castells que es van fer en aquesta diada:"
            }
        }

    
class QuestionSliderInput(BaseModel):
    question: str
    slider_min: int
    slider_max: int
    slider_step: int
    correct_answer: int
    half_point:int
    is_error: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Quin any va ser la fundació de la colla XX?",
                "slider_min": 1900,
                "slider_max": 2025,
                "slider_step": 1,
                "correct_answer": 1900,
                "half_point": 5
            }
        }

class QuestionMCQMultipleOptions(BaseModel):
    question: str
    options: List[str]
    correct_answer: List[str]
    is_error: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Quina de les seguents colles es va fundar l'any XX?",
                "options": ["Colla A", "Colla B", "Colla C", "Colla D"],
                "correct_answer": ["Colla A", "Colla B"]
            }
        }

    
class QuestionOrdering(BaseModel):
    question: str
    options: List[str]
    correct_answer_order: List[str]
    is_error: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Ordena les colles en funció de la seva posició del ranking de la jornada XX de l'any XX del concurs de castells",
                "options": ["Colla A", "Colla B", "Colla C", "Colla D"],
                "correct_answer_order": ["Colla A", "Colla B", "Colla C", "Colla D"]
            }
        }

# Additional questions 

###### MCQ 4 options ######
# Quina colla va quedar en XX posició el concurs de castells de l'any XX la jornada YY?

###### MCQ multiple options ######
# Quina va ser l'actuació de la colla XX a la diada XX l'any XX? Selecciona tots els castells fets.

###### Slider input ###### (arrossegable)
# Quantes colles han descarregat el XdX l'any XX?

###### Ordena ###### (arrosegable)
# Ordena les colles en funció de la seva posició del ranking de la jornada XX de l'any XX del concurs de castells