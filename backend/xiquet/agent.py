import re
import json
import unicodedata
from typing import List, Optional

try:  # optional; matches load_castellers_info_chunks / requirements.txt
    import tiktoken as _tiktoken  # type: ignore

    _RAG_QUERY_TOKEN_ENCODER = _tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover
    _RAG_QUERY_TOKEN_ENCODER = None


def _rag_query_token_count(text: str) -> int:
    """Token count for follow-up vs previous-question heuristics (cl100k if available)."""
    if not text or not str(text).strip():
        return 0
    if _RAG_QUERY_TOKEN_ENCODER is not None:
        return len(_RAG_QUERY_TOKEN_ENCODER.encode(str(text)))
    return len(str(text).split())
from langdetect import detect
from dotenv import load_dotenv
from .utility_functions import (
    language_names,
    get_colles_castelleres_subset,
    get_anys_subset,
    get_llocs_subset,
    get_diades_subset,
    get_castells_with_status_subset,
    Castell,
    FirstCallResponseFormat,
    get_all_colla_options,
    get_all_castell_options,
    get_all_any_options,
    get_all_lloc_options,
    get_all_diada_options,
    castell_code_may_alias_agulla_pilar,
    is_placeholder_diada_name,
    expand_anys_for_sql_query,
    is_valid_any_entity_token,
    normalize_any_display_token,
    parse_year_range_bounds,
)
from .llm_sql_v2 import LLMSQLGeneratorV2 as LLMSQLGenerator, get_sql_summary_prompt, NoResultsFoundError, SQLExecutionError, NO_RESULTS_MESSAGE, SQL_RESULT_LIMIT
from .llm_function import llm_call, is_guardrail_violation
from .util_dics import (
    SQL_QUERY_PATTERNS,
    IS_SQL_QUERY_PATTERNS,
    SQL_QUERY_TYPES_REQUIRING_CONCURS_IN_QUERY,
    COLUMN_MAPPINGS,
    TITLE_MAPPINGS,
    GAMMA_CASTELLS,
    GAMMA_KEYWORDS,
    MAP_QUERY_CHANGE,
    sql_results_description_for_query_type,
)
from .rag import rerank_rag_results, search_castellers_info
from difflib import SequenceMatcher
from rapidfuzz import fuzz, process
from datetime import datetime

ENTITY_PLACEHOLDERS = frozenset({"", "?", "null", "none"})

# Question length limit (tokens): basic plan = shorter limit, paid subscription = longer
LARGE_QUESTION_TOKEN_LIMIT_BASIC = 35
LARGE_QUESTION_TOKEN_LIMIT_PREMIUM = 200
PREVIOUS_CONTEXT_MAX_CHARS = 100
MAX_QUESTIONS_BASIC = 10  # Maximum questions per time window
TIME_BASIC = 3600  # Time window in seconds (1 hour = 3600 seconds) 

def _is_entity_placeholder(val) -> bool:
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in ENTITY_PLACEHOLDERS


_CATALAN_NUMBER_WORDS = frozenset(
    {
        "onze",
        "dotze",
        "tretze",
        "catorze",
        "quinze",
        "setze",
        "disset",
        "divuit",
        "dinou",
        "vint",
        "trenta",
        "quaranta",
        "cinquanta",
        "seixanta",
        "setanta",
        "vuitanta",
        "noranta",

    }
)
_CATALAN_NUMBER_IN_QUESTION_RE = re.compile(
    r"(?:\d|\b(?:"
    + "|".join(re.escape(w) for w in sorted(_CATALAN_NUMBER_WORDS, key=len, reverse=True))
    + r")\b)",
    re.IGNORECASE,
)


def number_in_question(question: str) -> bool:
    """True if the question has a digit or a Catalan cardinal number word (e.g. noranta, vuitanta)."""
    if not question:
        return False
    return bool(_CATALAN_NUMBER_IN_QUESTION_RE.search(question))


def normalize_query_synonyms(query: str) -> str:
    normalized = query
    sorted_mappings = sorted(MAP_QUERY_CHANGE.items(), key=lambda x: len(x[0]), reverse=True)
    
    for synonym, standard_code in sorted_mappings:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(synonym), re.IGNORECASE)
        normalized = pattern.sub(standard_code, normalized)
    
    if normalized != query:
        print(f"[NORMALIZE] Query transformed: '{query}' -> '{normalized}'")
    return normalized

def sanitize_llm_response(response: str) -> str:

    if not response:
        return response
    
    lines = response.split('\n')
    clean_lines = []
    
    for line in lines:
        pipe_count = line.count('|')
        
        if pipe_count >= 2:
            # This is likely a table row - skip it
            continue
        
        # Also detect markdown table separator lines (e.g., "|---|---|")
        if re.match(r'^[\s|:-]+$', line) and '|' in line:
            continue
        
        clean_lines.append(line)
    
    # Join lines
    result = '\n'.join(clean_lines)
    
    # Clean up excessive newlines and spaces
    result = re.sub(r'\n{3,}', '\n\n', result)  # Max 2 consecutive newlines
    result = re.sub(r'\s{2,}', ' ', result)     # Max 1 space
    result = re.sub(r'\s+\.', '.', result)      # Remove space before period
    result = re.sub(r'\s+,', ',', result)       # Remove space before comma
    
    return result.strip()

# Load environment variables from .env file
load_dotenv()

MODEL_NAME = "sambanova:gpt-oss-120b" 
MODEL_NAME_ROUTE = "sambanova:gpt-oss-120b"
MODEL_NAME_RESPONSE = "sambanova:Meta-Llama-3.3-70B-Instruct" #"sambanova:gpt-oss-120b"
MODEL_NAME_RESPONSE_RAG = "sambanova:Llama-4-Maverick-17B-128E-Instruct" #"sambanova:Meta-Llama-3.3-70B-Instruct"
# MODEL_NAME_RESPONSE = "sambanova:Llama-4-Maverick-17B-128E-Instruct"
# MODEL_NAME_RESPONSE = "sambanova:llama3-8b"


# Available options:
# groq:llama-3.1-8b-instant - Fast and cheap (DEFAULT)
# groq:llama-3.1-70b-versatile - Faster, smaller model
# openai:gpt-4o-mini - High quality, reliable
# anthropic:claude-3-haiku-20240307 - High quality responses
# ollama:llama3.1:8b - Free local model
# gemini:gemini-1.5-flash - Google's fast model (very cheap)
# gemini:gemini-1.5-pro - Google's advanced model
# deepseek:deepseek-chat - Fast and cost-effective
# deepseek:deepseek-coder - Great for code generation
# cerebras:qwen-3-32b - High-performance large model
# cerebras:gpt-oss-120b - Massive 120B parameter model

DEBUG = True

# ---- Xiquet Class ----
class Xiquet:
    def __init__(
        self, 
        previous_question: str = None, 
        previous_response: str = None,
        previous_route: str = None,
        previous_sql_query_type: str = None,
        previous_entities: dict = None,
        pre_selected_entities: dict = None,
        subscription: str = "basic"
    ):
        self.question = ""
        self.response = None
        self.colles_castelleres = []
        self.castells = []
        self.anys = []
        self.llocs = []
        self.diades = []
        self.editions = []
        self.jornades = []
        self.positions = []
        self.gamma = None  
        self.table_data = None
        self.sql_generator = LLMSQLGenerator()
        self.previous_question = previous_question
        self.previous_response = previous_response
        self.previous_route = previous_route
        self.previous_sql_query_type = previous_sql_query_type
        self.previous_entities = previous_entities or {}
        # Pre-selected entities from UI (user selected before asking question)
        self.pre_selected_entities = pre_selected_entities or {}
        self.subscription = subscription
        # Set in generate_prompt_decide_route when the router prompt forbids extracting colles.
        self.suppress_colla_extraction_from_llm = False

    def _get_previous_context_section(self) -> str:

        if not self.previous_question or not self.previous_response:
            return ""
        
        # Truncate response to max chars
        truncated_response = self.previous_response[:PREVIOUS_CONTEXT_MAX_CHARS]
        if len(self.previous_response) > PREVIOUS_CONTEXT_MAX_CHARS:
            truncated_response += "..."
        
        # Truncate question too (but shorter limit)
        truncated_question = self.previous_question[:150]
        if len(self.previous_question) > 150:
            truncated_question += "..."
        
        # Build entities string from previous entities
        entities_parts = []
        if self.previous_entities.get("colles"):
            entities_parts.append(f"colles={self.previous_entities['colles']}")
        if self.previous_entities.get("castells"):
            entities_parts.append(f"castells={self.previous_entities['castells']}")
        if self.previous_entities.get("anys"):
            entities_parts.append(f"anys={self.previous_entities['anys']}")
        if self.previous_entities.get("llocs"):
            entities_parts.append(f"llocs={self.previous_entities['llocs']}")
        if self.previous_entities.get("diades"):
            entities_parts.append(f"diades={self.previous_entities['diades']}")
        if self.previous_entities.get("edicions"):
            entities_parts.append(f"edicions={self.previous_entities['edicions']}")
        if self.previous_entities.get("jornades"):
            entities_parts.append(f"jornades={self.previous_entities['jornades']}")
        if self.previous_entities.get("posicions"):
            entities_parts.append(f"posicions={self.previous_entities['posicions']}")
        if self.previous_entities.get("gamma"):
            entities_parts.append(f"gamma={self.previous_entities['gamma']}")
        entities_str = ", ".join(entities_parts) if entities_parts else "cap"
        
        # Build route info
        route_info = ""
        if self.previous_route:
            route_info = f"- **Ruta:** {self.previous_route}"
            if self.previous_sql_query_type and self.previous_route == "sql":
                route_info += f" | **Tipus consulta:** {self.previous_sql_query_type}"
        
        return f"""
        ### CONTEXT DE LA PREGUNTA ANTERIOR:
        - **Pregunta anterior:** "{truncated_question}"
        {route_info}
        - **Entitats anteriors:** {entities_str}
        
        Tingues en compte aquest context per entendre millor la pregunta actual NOMES en cas de que sigui rellevant per extreure entitats i decidir la ruta.
        """
    
    def _remove_llocs_in_colla_names(self, question: str, response: FirstCallResponseFormat) -> None:
        if not (response.colla and response.llocs):
            return
        
        question_lower = question.lower()
        llocs_to_remove = []
        
        for colla in response.colla:
            colla_lower = colla.lower()
            for lloc in response.llocs:
                lloc_lower = lloc.lower()
                # Check if lloc is part of colla name
                if lloc_lower in colla_lower:
                    # Count how many times this lloc appears in the query
                    occurrences = question_lower.count(lloc_lower)
                    if occurrences == 1:
                        llocs_to_remove.append(lloc)
        
        # Remove the identified llocs
        if llocs_to_remove:
            response.llocs = [lloc for lloc in response.llocs if lloc not in llocs_to_remove]
            print(f"[ENTITY_FIX] Removed llocs that are part of colla names: {llocs_to_remove}")
    
    def _has_sql_grounding_entities(self, response: FirstCallResponseFormat) -> bool:
        """True if we have any DB-oriented filter the SQL path can use (incl. gamma heuristic)."""
        return bool(
            response.colla
            or response.castells
            or response.anys
            or response.llocs
            or response.diades
            or response.editions
            or response.jornades
            or response.positions
            or self.gamma
        )

    def _count_distinct_entity_field_groups(self, response: FirstCallResponseFormat) -> int:
        """Count how many entity dimensions are non-empty (RAG→hybrid when ≥3)."""
        n = 0
        if response.colla:
            n += 1
        if response.castells:
            n += 1
        if response.anys:
            n += 1
        if response.llocs:
            n += 1
        if response.diades:
            n += 1
        if response.editions:
            n += 1
        if response.jornades:
            n += 1
        if response.positions:
            n += 1
        if self.gamma:
            n += 1
        return n

    def _handle_follow_up_detection(self, question: str, response: FirstCallResponseFormat) -> bool:
        if not (self.previous_route == "sql" and self.previous_sql_query_type):
            return False
        
        question_lower = question.lower().strip()
        
        # Detect follow-up patterns: short question + starts with "I els...", "I de...", etc.
        follow_up_patterns = ["i els ", "i de ", "i dels ", "i la ", "i les ", "i el ", "i al ", "i a ","i l'", "i pel"]
        is_short_question = len(question) < 50
        one_entity_at_least = response.colla or response.castells or response.anys or response.llocs or response.diades
        has_follow_up_start = any(question_lower.startswith(p) for p in follow_up_patterns)
        
        if not (is_short_question and has_follow_up_start and one_entity_at_least):
            return False
        
        # Follow-up detected! Force SQL route and inherit
        print(f"[FOLLOW-UP DETECTED] Previous was SQL ({self.previous_sql_query_type}), forcing SQL route")
        response.tools = "sql"
        response.sql_query_type = self.previous_sql_query_type
        
        # Inherit entities from previous context that weren't identified in current question
        if self.previous_entities:
            inherited = []
            
            # Inherit colles if current has none
            if not response.colla and self.previous_entities.get("colles"):
                response.colla = self.previous_entities["colles"]
                inherited.append(f"colles={response.colla}")
            
            # Inherit castells if current has none
            if not response.castells and self.previous_entities.get("castells"):
                prev_castells = self.previous_entities["castells"]
                inherited_castells = []
                for c in prev_castells:
                    if isinstance(c, str):
                        inherited_castells.append(Castell(castell_code=c, status=None))
                    elif isinstance(c, dict):
                        inherited_castells.append(Castell(castell_code=c.get("castell_code", c.get("code", str(c))), status=c.get("status")))
                if inherited_castells:
                    response.castells = inherited_castells
                    inherited.append(f"castells={[c.castell_code for c in inherited_castells]}")
            
            # Inherit anys if current has none (convert to strings for validation)
            if not response.anys and self.previous_entities.get("anys"):
                response.anys = [str(a) for a in self.previous_entities["anys"]]
                inherited.append(f"anys={response.anys}")
            
            # Inherit llocs if current has none
            if not response.llocs and self.previous_entities.get("llocs"):
                response.llocs = self.previous_entities["llocs"]
                inherited.append(f"llocs={response.llocs}")
            
            # Inherit diades if current has none
            if not response.diades and self.previous_entities.get("diades"):
                response.diades = self.previous_entities["diades"]
                inherited.append(f"diades={response.diades}")
            
            if inherited:
                print(f"[FOLLOW-UP INHERIT] Inherited from previous: {', '.join(inherited)}")
        
        return True
    
    def _enrich_entities_from_previous_context(self) -> None:

        if not self.previous_entities:
            return
        
        # Helper to convert to list (handles both string and list)
        def to_list(s) -> list:
            if not s:
                return []
            if isinstance(s, list):
                return s
            if isinstance(s, str):
                return [x.strip() for x in s.split(",") if x.strip()]
            return []
        
        # Helper to convert list back to comma-separated string (only if needed)
        def list_to_str(lst: list) -> str:
            return ", ".join(lst) if lst else ""
        
        # Enrich colles (can be string or list depending on pre-selected vs extracted)
        # BUT: Skip if colles are pre-selected (user explicitly selected them)
        if self.previous_entities.get("colles") and not self.pre_selected_entities.get("colles"):
            current_colles = to_list(self.colles_castelleres)
            for colla in self.previous_entities["colles"]:
                if colla and colla not in current_colles:
                    current_colles.append(colla)
            # Keep as list if it was a list, otherwise convert to string
            if isinstance(self.colles_castelleres, list):
                self.colles_castelleres = current_colles
            else:
                self.colles_castelleres = list_to_str(current_colles)
        
        # Enrich castells (List[Castell] - the only real list!)
        # BUT: Skip if castells are pre-selected (user explicitly selected them)
        if self.previous_entities.get("castells") and not self.pre_selected_entities.get("castells"):
            current_castell_codes = {c.castell_code if hasattr(c, 'castell_code') else str(c) for c in self.castells}
            for c in self.previous_entities["castells"]:
                castell_code = c.get("castell_code") if isinstance(c, dict) else (c.castell_code if hasattr(c, 'castell_code') else str(c))
                if castell_code and castell_code not in current_castell_codes:
                    self.castells.append(Castell(castell_code=castell_code, status=None))
        
        # Enrich anys (can be string or list depending on pre-selected vs extracted)
        # BUT: Skip if anys are pre-selected (user explicitly selected them)
        if self.previous_entities.get("anys") and not self.pre_selected_entities.get("anys"):
            current_anys = to_list(self.anys)
            for a in self.previous_entities["anys"]:
                any_str = str(a)
                if any_str and any_str not in current_anys:
                    current_anys.append(any_str)
            # Keep as list if it was a list, otherwise convert to string
            if isinstance(self.anys, list):
                self.anys = current_anys
            else:
                self.anys = list_to_str(current_anys)
        
        # Enrich llocs (string, comma-separated)
        # Note: llocs are not in pre-selected options, so always enrich
        if self.previous_entities.get("llocs"):
            current_llocs = to_list(self.llocs)
            for lloc in self.previous_entities["llocs"]:
                if lloc and lloc not in current_llocs:
                    current_llocs.append(lloc)
            self.llocs = list_to_str(current_llocs)
        
        # Enrich diades (string, comma-separated)
        # BUT: Skip if diades are pre-selected (user explicitly selected them)
        if self.previous_entities.get("diades") and not self.pre_selected_entities.get("diades"):
            current_diades = to_list(self.diades)
            for diada in self.previous_entities["diades"]:
                if (
                    not _is_entity_placeholder(diada)
                    and not is_placeholder_diada_name(diada)
                    and diada not in current_diades
                ):
                    current_diades.append(diada)
            current_diades = [
                d
                for d in current_diades
                if not _is_entity_placeholder(d) and not is_placeholder_diada_name(d)
            ]
            self.diades = list_to_str(current_diades)

        # Enrich gamma (string, comma-separated)
        if self.previous_entities.get("gamma"):
            current_gamma = to_list(self.gamma) if self.gamma else []
            for gamma in self.previous_entities["gamma"]:
                if gamma and gamma not in current_gamma:
                    current_gamma.append(gamma)
            self.gamma = list_to_str(current_gamma) if current_gamma else None
    
    def _detect_gamma(self, question: str) -> Optional[str]:
        question_lower = question.lower()
        for gamma_name, keywords in GAMMA_KEYWORDS.items():
            for keyword in keywords:
                if keyword in question_lower:
                    return gamma_name
        return None
    
    def abans_de_res(self, question: str) -> Optional[FirstCallResponseFormat]:

        # 1. Primer comprova guardrails (sempre s'executa, independent de la detecció d'idioma)
        if is_guardrail_violation(question):
            response = (
                "Sóc **el Xiquet**, un assistent especialitzat **exclusivament** en el món casteller. \n\n"
                "Només puc respondre preguntes sobre castells, colles, diades, concursos i història castellera.\n"
                "Si tens una pregunta castellera, estaré encantat d'ajudar-te!"
            )
            return FirstCallResponseFormat(
                tools="direct",
                sql_query_type="",
                direct_response=response,
                colla=[], castells=[], anys=[], llocs=[], diades=[]
            )
        
        # 2. Analitza si la pregunta no és en català/espanyol/portuguès/francès
        try:
            lang = detect(question)
            if lang not in ["ca", "es", 'pt', 'fr', 'it']:
                if lang in language_names:
                    response = f"Ho sento, no parlo {language_names[lang]}. Només puc respondre preguntes en català i relacionades amb el món casteller. Però sempre es bon moment per apendre a parlar català!"
                else:
                    response = "Ho sento, només puc respondre preguntes en català i relacionades amb el món casteller. Però sempre es bon moment per apendre a parlar català!"
                
                return FirstCallResponseFormat(
                    tools="direct",
                    sql_query_type="",
                    direct_response=response,
                    colla=[], castells=[], anys=[], llocs=[], diades=[]
                )
        except Exception:
            # Si no es pot detectar l'idioma, continua processant
            print(f"Error en la detecció de l'idioma")
            pass
        
        # 3. Analitza si la pregunta supera el límit de tokens (segons pla: basic=35, premium=200)
        limit = LARGE_QUESTION_TOKEN_LIMIT_BASIC if self.subscription == "basic" else LARGE_QUESTION_TOKEN_LIMIT_PREMIUM
        tokens = re.findall(r'\b\w+\b', question)
        if len(tokens) > limit:
            return FirstCallResponseFormat(
                tools="direct",
                sql_query_type="",
                direct_response="La teva pregunta és massa llarga. Si us plau, fes una pregunta més concisa i específica sobre el món casteller.",
                colla=[], castells=[], anys=[], llocs=[], diades=[]
            )
        
        # Si no es compleix cap condició, retorna None per continuar processant
        return None

    def _validate_response_entities(self, response: FirstCallResponseFormat) -> Optional[FirstCallResponseFormat]:

        # Router must never choose hybrid; if the model emits it, treat as RAG.
        if response.tools == "hybrid":
            response = response.model_copy(update={"tools": "rag"})

        # Validate tool
        if response.tools not in ["direct", "rag", "sql"]:
            return FirstCallResponseFormat(
                tools="direct",
                sql_query_type="",
                direct_response="No estic segur de com respondre aquesta pregunta, però ho estic intentant!",
                colla=[],
                castells=[],
                anys=[],
                llocs=[],
                diades=[]
            )
        
        # If response.tools is "sql" or "hybrid", validate sql_query_type
        if response.tools in ["sql", "hybrid"]:
            if response.sql_query_type not in ["millor_diada", "millor_castell", "castell_historia", "castells_list", "location_actuations", "first_castell", "castell_statistics", "year_summary", "concurs_ranking", "concurs_history", "colles", "punts", "custom"]:
                response.sql_query_type = "custom"

        validation_start = datetime.now()
        
        # Helper function to remove accents for comparison
        def normalize_accents(text: str) -> str:
            return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        
        # Validate colla (only if not empty)
        if response.colla:
            valid_colles = get_all_colla_options()
            # Create a mapping of normalized names to original names
            normalized_to_original = {normalize_accents(c).lower(): c for c in valid_colles}
            
            for i, colla in enumerate(response.colla):
                if colla not in valid_colles:
                    # Try matching without accents
                    normalized_colla = normalize_accents(colla).lower()
                    if normalized_colla in normalized_to_original:
                        matched = normalized_to_original[normalized_colla]
                        print(f"[Accent Match] Colla '{colla}' -> '{matched}'")
                        response.colla[i] = matched
                    else:
                        # Try fuzzy matching as last resort
                        fuzzy_matches = process.extractOne(
                            colla,
                            valid_colles,
                            scorer=fuzz.token_set_ratio,  # Handles word order and missing/extra words
                            score_cutoff=80,
                        )
                        if fuzzy_matches:
                            matched = fuzzy_matches[0]
                            print(f"[Fuzzy Match] Colla '{colla}' -> '{matched}' (score: {fuzzy_matches[1]})")
                            response.colla[i] = matched
                        else:
                            print(f"Error: Colla {colla} no és vàlida")
                            response.colla[i] = None
            # Remove None values
            response.colla = [c for c in response.colla if c is not None] 
        
        # Validate castells (only if not empty) - be more flexible
        if response.castells:
            valid_castells = get_all_castell_options()
            for castell in response.castells:
                # Try to find a close match if exact match not found
                if castell.castell_code not in valid_castells:
                    # Look for similar castells (e.g., "3de10" -> "3d10f")
                    similar_castells = [c for c in valid_castells if castell.castell_code.replace('e', '').replace('d', 'd') in c]
                    if similar_castells:
                        print(f"Info: Castell {castell.castell_code} no trobat exactament, usant {similar_castells[0]}")
                        castell.castell_code = similar_castells[0]
                    else:
                        print(f"Warning: Castell {castell.castell_code} no és vàlid i no s'ha trobat similar")
                        # Don't remove, keep it for the query to handle
                
                # Validate status if present
                if castell.status and castell.status not in ['Descarregat', 'Carregat', 'Intent', 'Intent desmuntat']:
                    print(f"Warning: Status {castell.status} no és vàlid per castell {castell.castell_code}")
                    castell.status = None

        # Validate any (only if not empty); allow single-year DB tokens and closed ranges
        if response.anys:
            valid_anys = get_all_any_options()
            kept_anys: list[str] = []
            for yr in list(response.anys):
                token = str(yr).strip()
                if not token:
                    continue
                if is_valid_any_entity_token(token, valid_anys):
                    kept_anys.append(normalize_any_display_token(token))
                else:
                    print(f"Error: Any {token} no és vàlid")
            response.anys = kept_anys

        # Validate lloc (only if not empty)
        if response.llocs:
            valid_llocs = get_all_lloc_options()
            for lloc in response.llocs:
                if lloc not in valid_llocs:
                    print(f"Error: Lloc {lloc} no és vàlid")
                    response.llocs.remove(lloc)

        # Validate diada (only if not empty); also drop LLM placeholders like "?"
        if response.diades:
            response.diades = [
                d
                for d in response.diades
                if not _is_entity_placeholder(d) and not is_placeholder_diada_name(d)
            ]
            valid_diades = get_all_diada_options()
            if not valid_diades:
                response.diades = []
            else:
                normalized_diada_to_original = {
                    normalize_accents(d).lower(): d for d in valid_diades
                }
                for i, diada in enumerate(list(response.diades)):
                    if diada in valid_diades:
                        continue
                    diada_str = str(diada).strip()
                    normalized_diada = normalize_accents(diada_str).lower()
                    if normalized_diada in normalized_diada_to_original:
                        matched = normalized_diada_to_original[normalized_diada]
                        print(f"[Accent Match] Diada '{diada}' -> '{matched}'")
                        response.diades[i] = matched
                    else:
                        fuzzy_matches = process.extractOne(
                            diada_str,
                            valid_diades,
                            scorer=fuzz.token_set_ratio,
                            score_cutoff=90,
                        )
                        if fuzzy_matches:
                            matched = fuzzy_matches[0]
                            print(
                                f"[Fuzzy Match] Diada '{diada}' -> '{matched}' (score: {fuzzy_matches[1]})"
                            )
                            response.diades[i] = matched
                        else:
                            print(f"Error: Diada {diada} no és vàlida")
                            response.diades[i] = None
                response.diades = [d for d in response.diades if d is not None]
                seen_diades: set[str] = set()
                deduped: list[str] = []
                for d in response.diades:
                    if d not in seen_diades:
                        seen_diades.add(d)
                        deduped.append(d)
                response.diades = deduped
        validation_time = (datetime.now() - validation_start).total_seconds() * 1000
        if DEBUG:
            print(f"DEBUG ENTITY VALIDATION TIME: {validation_time:.2f}ms")

        # When gamma is detected, clear individual castells to avoid redundant chips
        # The gamma filter will handle the castell filtering in SQL
        if self.gamma:
            response.castells = []
            if DEBUG:
                print(f"DEBUG GAMMA: {self.gamma} - Clearing individual castells")

        if DEBUG:
            print(f"DEBUG ENTITIES FOR QUESTION")
            print(f"castells: {response.castells}")
            print(f"anys: {response.anys}")
            print(f"llocs: {response.llocs}")
            print(f"diades: {response.diades}")
            print(f"colles: {response.colla}")
            print(f"editions: {response.editions}")
            print(f"jornades: {response.jornades}")
            print(f"positions: {response.positions}")
            print(f"gamma: {self.gamma}")
            print(f"tools: {response.tools}")
            print(f"sql_query_type: {response.sql_query_type}")

        return None  # Validation succeeded

    def generate_prompt_decide_route(self, question: str) -> str:
        self.suppress_colla_extraction_from_llm = False

        # If we have pre-selected entities, use them directly and skip extraction for those types
        if self.pre_selected_entities:
            # Set pre-selected entities directly
            if self.pre_selected_entities.get("colles"):
                self.colles_castelleres = self.pre_selected_entities["colles"]
            if self.pre_selected_entities.get("castells"):
                # Convert castell codes to Castell objects
                self.castells = [Castell(castell_code=c, status=None) for c in self.pre_selected_entities["castells"]]
            if self.pre_selected_entities.get("anys"):
                self.anys = self.pre_selected_entities["anys"]
            if self.pre_selected_entities.get("diades"):
                self.diades = self.pre_selected_entities["diades"]
            if DEBUG:
                print(f"DEBUG PRE-SELECTED: Using pre-selected entities: colles={self.colles_castelleres}, castells={[c.castell_code for c in self.castells]}, anys={self.anys}, diades={self.diades}")
        
        # Extract entities from question (heuristics) - but skip types that are pre-selected
        entity_start = datetime.now()
        if not self.pre_selected_entities.get("colles"):
            self.colles_castelleres = get_colles_castelleres_subset(question)
        if not self.pre_selected_entities.get("castells"):
            self.castells = get_castells_with_status_subset(question)
        if not self.pre_selected_entities.get("anys"):
            self.anys = get_anys_subset(question)
        # Always extract llocs and diades (not in pre-selected options)
        self.llocs = get_llocs_subset(question)
        self.diades = get_diades_subset(question)
        self.gamma = self._detect_gamma(question)
        
        # Enrich entity lists with previous context entities (so LLM can see them as options)
        self._enrich_entities_from_previous_context()
        
        entity_time = (datetime.now() - entity_start).total_seconds() * 1000
        
        if DEBUG:
            print(f"DEBUG ENTITY EXTRACTION TIME: {entity_time:.2f}ms")

        # Check if pregunta starts with 'quina colla' or 'quines colles'
        starts_with_quina_colla = False
        if question.lower().startswith('quina colla') or question.lower().startswith('quines colles'):
            starts_with_quina_colla = True

        # Build dynamic entities section
        # If entities are pre-selected, inform LLM but don't ask to extract them
        entities_section = ""
        # colles_castelleres can be str or list; count actual colles for "more than one" check
        _colles_list = (
            self.colles_castelleres
            if isinstance(self.colles_castelleres, list)
            else [x.strip() for x in str(self.colles_castelleres or "").split(",") if x.strip()]
        )

        # Handle pre-selected colles
        if self.pre_selected_entities.get("colles"):
            entities_section += f"""
        - **Colla o colles castellereres:** L'usuari ha seleccionat prèviament: {', '.join(self.pre_selected_entities['colles'])}. NO cal que l'extreguis de la pregunta.
        \n"""
        elif self.colles_castelleres and not starts_with_quina_colla:
            entities_section += f"""
        - **Colla o colles castellereres:** Nom de les colles castellereres.  
        Possibles opcions: {self.colles_castelleres}
         \n"""
        elif starts_with_quina_colla and len(_colles_list) > 1:
            entities_section += f"""
        - **Colla o colles castellereres:** Nom de les colles castellereres.  
        Possibles opcions: {self.colles_castelleres}. 
        IMPORTANT: Només extreu les colles castellereres que apareixen en la pregunta si són rellevants per triar entre diferents opcions.
         \n"""
        else:
            self.suppress_colla_extraction_from_llm = True
            entities_section += f"""
        - **Colla castellera:** NO extreguis cap colla. La pregunta no menciona cap colla específica.
        \n"""
        if DEBUG:
            print(f"DEBUG 1 colles_castelleres: {self.colles_castelleres}")
        
        # Handle pre-selected castells
        if self.pre_selected_entities.get("castells"):
            entities_section += f"""
        - **Castell o castells:** L'usuari ha seleccionat prèviament els següents castells: {', '.join(self.pre_selected_entities['castells'])}. NO cal que els extreguis de la pregunta.
        \n"""
        elif self.castells:
            entities_section += f"""
        - **Castell o castells:** Tipus de construcció castellera amb estat opcional.  
        Possibles opcions: {self.castells}
        Cada castell pot tenir un estat: Descarregat, Carregat, Intent, Intent desmuntat, o cap estat (posa null).
        \n"""
        else:
            entities_section += f"""
        - **Castell o castells:** No extreguis cap castell.  
        \n"""
        
        # Handle pre-selected anys
        if self.pre_selected_entities.get("anys"):
            entities_section += f"""
        - **Any/s:** L'usuari ha seleccionat prèviament: {', '.join(str(a) for a in self.pre_selected_entities['anys'])}. NO cal que l'extreguis de la pregunta.
        \n"""
        elif self.anys:
            entities_section += f"""
        - **Any/s:** Any concret o període temporal (per exemple, "2024", "2025", etc.). Per un període, un sol element en format `AAAA-AAAA` (p. ex. `2010-2026` o `2010-actualitat` resolt a `2010-2026`).
        \n"""
        elif number_in_question(question):
            entities_section += f"""  
        - **Any/s:** Si es fa referència a un període temporal, extreu un sol rang tancat `AAAA-AAAA` (p. ex. `2010-2026` o `2010-actualitat`); si no, deixa `anys` buit.
        \n""" 
        else: 
            entities_section += f"""
        - **Any/s:** No extreguis cap any.
        \n"""

        if self.llocs:
            entities_section += f"""
        - **Lloc:** Ciutat o població de certa actuació.  
        Possibles opcions: {self.llocs}
        \n"""
        
        # Diades (not in pre-selected options, always extract)
        _diades_list = (
            [x.strip() for x in self.diades.split(",") if x.strip()]
            if isinstance(self.diades, str)
            else (list(self.diades) if self.diades else [])
        )
        _diades_clean = [
            d
            for d in _diades_list
            if not _is_entity_placeholder(d) and not is_placeholder_diada_name(d)
        ]
        if _diades_clean:
            entities_section += f"""
        - **Diada/es:** Nom de la/les diada/es o jornada/es castellera.  
        Possibles opcions: {", ".join(_diades_clean)}
        \n"""

        if self.gamma:
            gamma_info = GAMMA_CASTELLS.get(self.gamma, {})
            entities_section += f"""
        - **Gamma de castells:** {self.gamma}
        {gamma_info.get("description", "")}
        \n"""

        # Add concurs-related entities if the question mentions concurs
        if "concurs" in question.lower() or "concursos" in question.lower():
            entities_section += f""" Si la pregunta és sobre un concurs de castells, afegeix les següents entitats si apareixen:
        - **Edició de concurs:** Edició del concurs de castells (I, II, III, IV,...).
        - **Jornada:** Tipus de jornada del concurs ('Jornada Diumenge Tarragona', 'Jornada Dissabte Tarragona', 'Jornada Torredembarra').
        - **Posició:** Posició en la classificació del concurs (1, 2, 3, 4, ...).
        \n"""

        # Get previous context if available
        previous_context = self._get_previous_context_section()
        
        # Build enhanced question with pre-selected entities for LLM context
        enhanced_question = question
        pre_selected_parts = []
        if self.pre_selected_entities.get("colles"):
            pre_selected_parts.append(f"colles: {', '.join(self.pre_selected_entities['colles'])}")
        if self.pre_selected_entities.get("anys"):
            pre_selected_parts.append(f"anys: {', '.join(str(a) for a in self.pre_selected_entities['anys'])}")
        if self.pre_selected_entities.get("castells"):
            pre_selected_parts.append(f"castells: {', '.join(self.pre_selected_entities['castells'])}")
        
        if pre_selected_parts:
            enhanced_question = f"{question} ({', '.join(pre_selected_parts)})"
            if DEBUG:
                print(f"DEBUG ENHANCED QUESTION: {enhanced_question}")
        
        route_prompt = f"""
        Ets el Xiquet, un assistent expert en el món casteller. 
        La teva tasca és analitzar la següent pregunta sobre castells:  
        > "{enhanced_question}"

        Segueix estrictament aquests passos:

        ### 1. Identificació d'entitats
        Analitza la pregunta i identifica, si n'hi ha, els següents tipus d'elements.  
        L'objectiu és detectar referències i mapar-les exactament a l'element correcte dins la seva llista corresponent.  

        Elements a extreure:{entities_section}

        ### 2. Elecció de l'eina adequada
        Decideix quina eina utilitzar per respondre la pregunta: sql, rag o direct.

        - **"sql"**: si la pregunta requereix **informació quantitativa o estadística** que es pot obtenir amb una consulta a la base de dades. 
            Preguntes com millor actuació, millor castells, rankings o consultes del concurs, quantes vegades s'ha fet un castell, on s'han realitzat castells, resums d'una temporada o any, estadístiques d'un castell/s, història de concursos, etc. 
            Prioritza la consulta SQL sobre la resta quan tinguis dubtes.

        - **"rag"**: si la pregunta requereix **coneixement textual o descriptiu**, com història, valors o conceptes generals sobre el mon casteller.  

        - **"direct"**: si la pregunta és **molt general, bàsica o no relacionada amb castells**.  

        ### 3. Format de resposta
        Respon **exclusivament** en format JSON segons l'estructura següent:

        {FirstCallResponseFormat.model_json_schema()}

        Regles:
        - El camp `"tools"` ha de ser exactament un d'aquests valors: `"direct"`, `"rag"`, `"sql"`.
        - Si `"tools"` és `"direct"`, **afegeix també una resposta breu i clara** al camp `"direct_response"`.
        - Assegura't que **totes les llistes** (`colla`, `castells`, `anys`, `llocs`, `diades`, `edicions`, `jornades`, `posicions`) contenen només elements exactes o són buides.


        IMPORTANT: No confonguis el nom de les colles amb el fet de que estigui parlant de una localitat o diada. 
        Per exemple, si la pregunta parla dels "castellers de Sabadell", no has d'extreure "Sabadell" com a lloc ni "Diada dels castellers de Sabadell" com a diada a nose que la pregunta faci referència a aquella especifica diada. 

        {previous_context}

        Ara analitza la pregunta de l'usuari i genera la sortida amb el format indicat.
        
        ### PREGUNTA DE L'USUARI:
        > "{enhanced_question}"
        """
        
        return route_prompt

    def decide_route(self, question: str) -> FirstCallResponseFormat:
        
        # Normalize query synonyms (e.g., "4d9 amb folre i pilar" -> "4d9af")
        question = normalize_query_synonyms(question)
        self.question = question
        
        precheck_start = datetime.now()
        # Analitza si cal donar una resposta directa abans de processar-la (guardrails, massa llarga, no en català, etc.)
        direct_response = self.abans_de_res(question)
        precheck_time = (datetime.now() - precheck_start).total_seconds() * 1000
        if precheck_time > 1:
            if DEBUG:
                print(f"DEBUG ANTES DE RES TIME: {precheck_time:.2f}ms")
        
        if direct_response is not None:
            return direct_response
        
        # Generate route prompt (extracts entities and builds prompt)
        llm_start = datetime.now()
        route_prompt = self.generate_prompt_decide_route(question)
        if DEBUG:
            print(f"DEBUG ROUTE PROMPT: {route_prompt}")

        response = llm_call(route_prompt, model=MODEL_NAME_ROUTE, response_format=FirstCallResponseFormat)
        llm_time = (datetime.now() - llm_start).total_seconds() * 1000
        if DEBUG:
            print(f"DEBUG DECIDEROUTE LLM CALL TIME: {llm_time:.2f}ms")
        
        # Handle case where provider returns dict instead of Pydantic model
        if isinstance(response, dict):
            if DEBUG:
                print(f"DEBUG WARNING: LLM returned dict instead of FirstCallResponseFormat, converting...")
            try:
                response = FirstCallResponseFormat(**response)
            except Exception as e:
                print(f"[ERROR] Failed to convert dict to FirstCallResponseFormat: {e}")
                return FirstCallResponseFormat(
                    tools="direct",
                    sql_query_type="",
                    direct_response="Ho sento, hi ha hagut un problema processant la teva pregunta. Torna-ho a provar.",
                    colla=[],
                    castells=[],
                    anys=[],
                    llocs=[],
                    diades=[]
                )
        
        self.response = response

        # Prompt told the model not to extract colles; drop any hallucinated colla list anyway.
        if self.suppress_colla_extraction_from_llm and not self.pre_selected_entities.get("colles"):
            response = response.model_copy(update={"colla": []})
            self.response = response

        sql_type_start = datetime.now()
        
        # Remove llocs that are part of colla names and only appear once in the query
        self._remove_llocs_in_colla_names(question, response)
        
        # Handle follow-up detection (forces SQL route and inherits entities if applicable)
        skip_sql_check = self._handle_follow_up_detection(question, response)
        
        if response.tools == "rag" or response.tools == "direct":
            if response.tools == "direct":
                threshold = 0.75
            else:
                threshold = 0.8
            # Check if entities exist (LLM extraction, pre-selected chips, or heuristic gamma).
            # Gamma is set in generate_prompt_decide_route via _detect_gamma but is not in FirstCallResponseFormat.
            has_entities = (
                response.colla or response.castells or response.anys or response.llocs or response.diades or
                self.pre_selected_entities.get("colles") or
                self.pre_selected_entities.get("castells") or
                self.pre_selected_entities.get("anys") or
                bool(self.gamma)
            )
            # Only attempt SQL determination if entities exist
            if has_entities:
                # Use enhanced question (with pre-selected entities) for better pattern matching
                enhanced_question = question
                pre_selected_parts = []
                if self.pre_selected_entities.get("colles"):
                    pre_selected_parts.append(f"colles: {', '.join(self.pre_selected_entities['colles'])}")
                if self.pre_selected_entities.get("anys"):
                    pre_selected_parts.append(f"anys: {', '.join(self.pre_selected_entities['anys'])}")
                if self.pre_selected_entities.get("castells"):
                    pre_selected_parts.append(f"castells: {', '.join(self.pre_selected_entities['castells'])}")
                if self.gamma:
                    pre_selected_parts.append(f"gamma: {self.gamma}")
                if pre_selected_parts:
                    enhanced_question = f"{question} ({', '.join(pre_selected_parts)})"
                
                response.sql_query_type = self._determine_sql_query_type(enhanced_question, response, IS_SQL_QUERY_PATTERNS, threshold=threshold)
                if response.sql_query_type != "custom":
                    response.tools = "sql"
                    skip_sql_check = True
                    if DEBUG:
                        print(f"DEBUG SQL ROUTE: Detected SQL query type '{response.sql_query_type}' from enhanced question with pre-selected entities")

        
        # If SQL or hybrid, determine the specific query type
        if response.tools in ["sql", "hybrid"] and not skip_sql_check:
            # Fast fuzzy matching (current default)
            response.sql_query_type = self._determine_sql_query_type(question, response, SQL_QUERY_PATTERNS)

            # INHERIT SQL QUERY TYPE FROM PREVIOUS MESSAGE IF CURRENT IS "custom"
            # This handles follow-up questions like "I els Minyons?" after asking about Vilafranca
            if response.sql_query_type == "custom" and self.previous_sql_query_type:
                valid_types = ["millor_diada", "millor_castell", "castell_historia", "castells_list", "location_actuations", 
                              "first_castell", "castell_statistics", "year_summary", "concurs_ranking", "concurs_history", "colles", "punts"]
                if self.previous_sql_query_type in valid_types:
                    if DEBUG:
                        print(f"DEBUG SQL TYPE INHERIT: Inheriting '{self.previous_sql_query_type}' from previous question (current was 'custom')")
                    response.sql_query_type = self.previous_sql_query_type
        
        sql_type_time = (datetime.now() - sql_type_start).total_seconds() * 1000
        if DEBUG:
            print(f"DEBUG SQL TYPE DETERMINATION TIME: {sql_type_time:.2f}ms")

        # Validate all entities and tools
        validation_result = self._validate_response_entities(response)
        if validation_result is not None:
            return validation_result

        self._strip_response_single_years_if_no_temporal_hint(question, response)

        # Merge pre-selected entities with LLM-extracted entities
        # Pre-selected entities take precedence (user explicitly selected them)
        if self.pre_selected_entities:
            if self.pre_selected_entities.get("colles"):
                response.colla = self.pre_selected_entities["colles"]
            if self.pre_selected_entities.get("castells"):
                # Convert castell codes to Castell objects
                response.castells = [Castell(castell_code=c, status=None) for c in self.pre_selected_entities["castells"]]
            if self.pre_selected_entities.get("anys"):
                response.anys = self.pre_selected_entities["anys"]
        
        # Update self with validated entities
        self.colles_castelleres = response.colla
        self.castells = response.castells
        self.anys = response.anys
        self.llocs = response.llocs
        self.diades = response.diades
        self.editions = response.editions
        self.jornades = response.jornades
        self.positions = response.positions

        # Phrases like "quines colles ..." fuzzy-match the `colles` SQL pattern but often have no
        # extracted colles/years/etc.; SQL then misbehaves. Prefer RAG when there is nothing to ground on.
        if response.tools == "sql" and not self._has_sql_grounding_entities(response):
            if DEBUG:
                print("DEBUG ROUTE OVERRIDE: SQL route but no grounded entities -> rag")
            response.tools = "rag"
            response.sql_query_type = "custom"

        return response

    def _determine_sql_query_type(self, question: str, response: FirstCallResponseFormat, query_patterns: dict = SQL_QUERY_PATTERNS, threshold: float = 0.5) -> str:
    
        question_lower = question.lower()
        
        # Calculate similarity scores for each query type
        scores = {}
        for query_type, spec in query_patterns.items():
            if isinstance(spec, dict):
                patterns = spec.get("patterns") or []
            else:
                patterns = spec or []
            max_similarity = 0
            best_pattern = None
            
            for pattern in patterns:
                # Calculate similarity between question and pattern
                similarity = SequenceMatcher(None, question_lower, pattern).ratio()
                if similarity > max_similarity:
                    max_similarity = similarity
                    best_pattern = pattern
            
            # Check for exact substring matches (highest priority)
            exact_substring_matches = [p for p in patterns if p in question_lower]
            if exact_substring_matches:
                # Boost score significantly for exact substring matches
                max_similarity = max(max_similarity, 0.80)
            
            # Check for fuzzy substring matches (handle typos)
            # For key patterns, check if all words appear in question (with fuzzy matching)
            fuzzy_match_score = 0
            for pattern in patterns:
                pattern_words = pattern.split()
                if len(pattern_words) >= 2:  # Only for multi-word patterns
                    # Check if all key words from pattern appear in question (with some tolerance)
                    words_found = 0
                    for word in pattern_words:
                        # Check exact match first
                        if word in question_lower:
                            words_found += 1
                        else:
                            # Check fuzzy match (typo tolerance) - look for similar words
                            for q_word in question_lower.split():
                                word_sim = SequenceMatcher(None, word, q_word).ratio()
                                if word_sim > 0.85:  # High similarity threshold for typos
                                    words_found += 1
                                    break
                    
                    # If most/all words match, boost the score significantly
                    if words_found >= len(pattern_words) * 0.8:  # 80% of words match
                        # For important patterns like "millor castell", give high priority
                        if words_found == len(pattern_words):  # All words match
                            fuzzy_match_score = max(fuzzy_match_score, 0.75)
                        else:  # Most words match
                            fuzzy_sim = SequenceMatcher(None, question_lower, pattern).ratio()
                            fuzzy_match_score = max(fuzzy_match_score, fuzzy_sim * 1.3)  # Boost by 30%
            
            if fuzzy_match_score > 0:
                max_similarity = max(max_similarity, fuzzy_match_score)
            
            scores[query_type] = max_similarity
        
        # Concurs: no barrejar amb preguntes narratives (p. ex. història d'una colla) per fuzzy match
        if "concurs" not in question_lower:
            for qt in SQL_QUERY_TYPES_REQUIRING_CONCURS_IN_QUERY:
                scores[qt] = 0.0
        
        # Find the best match
        best_match = max(scores.items(), key=lambda x: x[1])
        best_query_type, best_score = best_match
        
        # If concurs_history but jornades or positions are populated, change to concurs_ranking
        if best_query_type == "concurs_history" and (response.jornades or response.positions):
            if DEBUG:
                print(f"[Fuzzy Match] Overriding concurs_history -> concurs_ranking (jornades: {response.jornades}, positions: {response.positions})")
            best_query_type = "concurs_ranking"
        
        # Threshold for accepting a match (adjust as needed)
        if best_score >= threshold:
            if DEBUG:
                print(f"[Fuzzy Match] Best match: {best_query_type} (score: {best_score:.2f})")
            return best_query_type
        else:
            if DEBUG:
                print(f"[Fuzzy Match] No match above threshold {threshold}. Best: {best_query_type} (score: {best_score:.2f})")
            return "custom"


    def handle_direct(self) -> str:
        return self.response.direct_response

    def _heuristic_anys_empty(self) -> bool:
        """True when self.anys has no year tokens (subset string, list, or after previous-context enrich)."""
        v = self.anys
        if v is None:
            return True
        if isinstance(v, list):
            return not any(x is not None and str(x).strip() for x in v)
        return not str(v).strip()

    def _strip_response_single_years_if_no_temporal_hint(
        self, question: str, response: FirstCallResponseFormat
    ) -> None:
        """
        If there are no pre-selected anys, no heuristic/enriched anys on self, and the
        question has no digit or Catalan number-word, drop LLM single-year anys but
        keep parseable periods (YYYY-YYYY, YYYY-actualitat, etc.).
        """
        if self.pre_selected_entities.get("anys"):
            return
        if not self._heuristic_anys_empty():
            return
        if number_in_question(question):
            return
        if not response.anys:
            return
        before = list(response.anys)
        kept: list[str] = []
        for t in before:
            token = str(t).strip()
            if not token:
                continue
            if parse_year_range_bounds(token) is not None:
                kept.append(normalize_any_display_token(token))
        response.anys = kept
        if DEBUG and len(before) != len(kept):
            print(
                f"[ENTITY_FIX] Removed single-year anys without temporal hint in question "
                f"(had {before}, kept {kept})"
            )

    def _anys_tokens_list(self) -> List[str]:
        v = self.anys
        if not v:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if x is not None and str(x).strip()]
        return [s.strip() for s in str(v).split(",") if s.strip()]

    def _anys_for_sql_list(self) -> List[str]:
        tokens = self._anys_tokens_list()
        expanded = expand_anys_for_sql_query(tokens)
        return expanded if expanded else tokens

    def create_sql_query(self) -> tuple[str, dict]:
        # Build entities dictionary
        entities = {
            "colla": self.colles_castelleres,
            "castells": self.castells,
            "anys": self._anys_for_sql_list(),
            "llocs": self.llocs,
            "diades": self.diades,
            "editions": self.editions,
            "jornades": self.jornades,
            "positions": self.positions,
            "gamma": self.gamma
        }
        
        # Get sql_query_type from response
        sql_query_type = getattr(self.response, 'sql_query_type', 'custom')
        
        # Use the SQL generator
        return self.sql_generator.create_sql_query(
            self.question, 
            entities, 
            sql_query_type, 
            lambda prompt: llm_call(prompt, model=MODEL_NAME_RESPONSE)
        )

    def execute_sql_query(self, sql_query: str, params: dict) -> list:
        return self.sql_generator.execute_sql_query(sql_query, params)
    
    def organize_sql_results(self, raw_results: list, sql_query_type: str) -> list:
        """Organize raw SQL results based on query type (V2 approach)"""
        entities = {
            "colla": self.colles_castelleres,
            "castells": self.castells,
            "anys": self._anys_for_sql_list(),
            "llocs": self.llocs,
            "diades": self.diades,
            "editions": self.editions,
            "jornades": self.jornades,
            "positions": self.positions,
            "gamma": self.gamma
        }
        return self.sql_generator.organize_results(raw_results, sql_query_type, entities)


    def _build_rag_search_text(self) -> str:
        """Build the text passed to the hybrid retriever.

        We augment the user question with the entities the agent has already
        extracted (colles, castells, llocs, diades, gamma, anys). Both legs of
        the retrieval — dense embeddings AND BM25 over `search_tsv` — benefit
        from the extra signal:
        - Embeddings: explicit colla/castell names sharpen the semantic vector.
        - BM25: lexical matches on castell codes, colla names, places, etc.

        Kept short (no duplicates, lightly de-duplicated) so we don't blow the
        embedding token budget for huge selections.
        """
        parts: list[str] = [self.question]

        def _flatten(value) -> list[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(v).strip() for v in value if v is not None and str(v).strip()]
            if isinstance(value, str):
                return [s.strip() for s in value.split(",") if s.strip()]
            return [str(value)]

        parts.extend(_flatten(self.colles_castelleres))
        if self.castells:
            for c in self.castells:
                code = getattr(c, "castell_code", None) or str(c)
                if code:
                    parts.append(code)
        parts.extend(_flatten(self.llocs))
        parts.extend(_flatten(self.diades))
        parts.extend(_flatten(self._anys_tokens_list()))
        if self.gamma:
            parts.append(str(self.gamma))

        seen: set[str] = set()
        ordered: list[str] = []
        for p in parts:
            key = p.lower()
            if key not in seen:
                seen.add(key)
                ordered.append(p)
        return " ".join(ordered)

    def _build_rag_retrieval_text(self) -> str:
        """Hybrid retrieval string (embedding + BM25 only).

        When the current user message is much shorter than the previous one
        (underspecified follow-up), prepend the previous question so dense and
        sparse search carry topic signal. Reranking still uses ``self.question``
        only — see ``rerank_rag_results`` in ``_retrieve_rag_context``.
        """
        augmented = self._build_rag_search_text()
        pq = (self.previous_question or "").strip()
        if not pq:
            return augmented
        prev_tok = _rag_query_token_count(pq)
        cur_tok = _rag_query_token_count(self.question or "")
        if prev_tok < 1:
            return augmented
        # Current has at most 80% of the previous question's tokens → prepend.
        if cur_tok > 0.8 * prev_tok:
            return augmented
        return f"{pq} {augmented}"

    def _retrieve_rag_context(self, final_top_k: int) -> tuple[Optional[str], Optional[str]]:
        """
        Shared RAG retrieval + rerank + filter. Returns (context_string, error_key).
        error_key is 'no_results', 'below_threshold', or None on success.
        """
        # Hybrid retrieval: vec top-50 ∪ bm25 top-50 → RRF → top-40 candidates.
        # `min_non_revista`/`non_revista_topup` guarantee curated chunks always
        # appear in the candidate pool.
        INITIAL_K = 40
        # Cosine-similarity floor on the candidate list. With a real embedding
        # model + BM25 hybrid, anything under ~0.25 is almost always noise.
        # The reranker can still boost a chunk above this floor via colla/year
        # matches; we filter AFTER reranking so meaningful signals survive.
        MIN_SIMILARITY = 0.25
        try:
            search_text = self._build_rag_retrieval_text()
            if DEBUG:
                print(
                    f"DEBUG RAG: Hybrid search text "
                    f"(orig={self.question[:40]!r} → retrieval={search_text[:80]!r})"
                )
                print(f"DEBUG RAG: Calling search_castellers_info(k={INITIAL_K})...")
            rag_search_start = datetime.now()
            results = search_castellers_info(search_text, k=INITIAL_K)
            rag_search_time = (datetime.now() - rag_search_start).total_seconds() * 1000
            if DEBUG:
                print(f"DEBUG RAG: RAG search: {rag_search_time:.2f}ms ({len(results)} results)")

            if not results:
                return None, "no_results"

            entities = {
                "colla": self.colles_castelleres,
                "anys": self._anys_for_sql_list(),
                "llocs": self.llocs,
                "castells": self.castells,
                "diades": self.diades
            }
            rerank_start = datetime.now()
            reranked = rerank_rag_results(results, entities, self.question)
            rerank_time = (datetime.now() - rerank_start).total_seconds() * 1000
            if DEBUG:
                print(f"DEBUG RERANKING TIME: {rerank_time:.2f}ms")

            filtered = [(doc, score) for doc, score in reranked if score >= MIN_SIMILARITY]
            if DEBUG:
                print(f"DEBUG RAG: Filtered after boost: {len(reranked)} -> {len(filtered)} (threshold: {MIN_SIMILARITY})")

            if not filtered:
                return None, "below_threshold"

            top_results = filtered[:final_top_k]
            if DEBUG:
                print(f"DEBUG RAG: Final top {len(top_results)} results:")
                for i, (doc, score) in enumerate(top_results):
                    print(f"DEBUG RAG: {i+1}. [{score:.3f}] {doc['meta'].get('title', 'No title')}")

            context_parts = []
            for i, (doc_info, score) in enumerate(top_results, 1):
                title = doc_info["meta"].get("title", "")
                text = doc_info.get("text", "")
                context_parts.append(f"[Document {i}: {title}]\n{text}")
            return "\n\n".join(context_parts), None
        except Exception as e:
            print(f"[RAG] Error in _retrieve_rag_context: {e}")
            return None, "no_results"

    def handle_rag(self, final_top_k: int = 3) -> str:
        if DEBUG:
            print(f"DEBUG RAG: Starting handle_rag()")
            print(f"DEBUG RAG: Question: {self.question[:50]}...")

        try:
            context, err = self._retrieve_rag_context(final_top_k)
            if err == "no_results":
                return "No he trobat informació rellevant per respondre la teva pregunta."
            if err == "below_threshold":
                return "No he trobat informació prou rellevant per respondre la teva pregunta."
            if context is None:
                return "No he trobat informació rellevant per respondre la teva pregunta."

            # Step 6: Generate answer with LLM
            rag_system = """Ets un expert casteller amb criteri tècnic i rigor històric.
Sempre respons exclusivament en català."""
            
            rag_developer = """INSTRUCCIONS:
- Text narratiu en paràgrafs (1-3 paràgrafs màxim)
- Usa **negreta** per destacar fets clau
- No mencionis documents, fonts, consultes, "informació disponible" o "informació proporcionada" ni cap altra meta-referència al context; respon sempre de forma directa amb els fets.
- NO inventes informació que no apareix en la informació proporcionada
- Si la Informació de consulta proporcionada no és rellevant per respondre la pregunta, digues ÚNICAMENT I EXCLUSIVAMENT: "No tinc informació sobre aquest tema. Pots reformular la pregunta?" - 
- NO mencions ni facis referència a informació que no siguin rellevants per la pregunta 
- Si la informació no és rellevant, no mencionis que et proporcionem informació de la consulta i que no està especificada"""

            # Build previous context section for user prompt
            previous_context_str = ""
            if self.previous_question and self.previous_response:
                truncated_resp = self.previous_response[:PREVIOUS_CONTEXT_MAX_CHARS]
                if len(self.previous_response) > PREVIOUS_CONTEXT_MAX_CHARS:
                    truncated_resp += "..."
                previous_context_str = f"""
CONTEXT ANTERIOR DEL MISSATGE ANTERIOR:
- Pregunta: "{self.previous_question[:150]}"
- Resposta: "{truncated_resp}"

"""

            rag_user = f"""{previous_context_str}Pregunta actual:
{self.question}

Informació de consulta:
{context}

Respon basant-te en la informació. Si la informació no és suficient per respondre la pregunta, digues que no ho saps - sense mencionar que et passo informació"""
            
            rag_llm_start = datetime.now()
            answer = llm_call(
                prompt=rag_user,
                model=MODEL_NAME_RESPONSE_RAG,
                system_message=rag_system,
                developer_message=rag_developer
            )
            rag_llm_time = (datetime.now() - rag_llm_start).total_seconds() * 1000
            if DEBUG:
                print(f"DEBUG RAG: LLM call: {rag_llm_time:.2f}ms")
            
            answer = sanitize_llm_response(answer)
            
            # Don't add source footer if no relevant info was found
            if "No tinc informació sobre aquest tema" in answer:
                return answer
            return f"{answer}\n\n*Font: Cerca semàntica en documents castellers*"
            
        except Exception as e:
            print(f"[RAG] Error: {e}")
            return f"Error en la cerca semàntica: {e}"

    def handle_hybrid_rag_sql(self, rag_top_k: int) -> str:
        """
        Indirect hybrid: chosen when the router said RAG but at least three
        entity dimensions are filled (`run_handlers_after_route`).
        Combines RAG context (typically two chunks) with SQL custom table data.
        """
        if DEBUG:
            print(f"DEBUG HYBRID: rag_top_k={rag_top_k}, entity_groups={self._count_distinct_entity_field_groups(self.response)}")

        rag_context, rag_err = self._retrieve_rag_context(rag_top_k)
        if rag_err == "no_results":
            rag_block = "No hi ha fragments de documents rellevants de la cerca."
        elif rag_err == "below_threshold":
            rag_block = "No hi ha fragments de documents que superin el llindar de rellevància."
        else:
            rag_block = rag_context or ""

        saved_sql_type = getattr(self.response, "sql_query_type", "custom")
        self.response.sql_query_type = "custom"
        table_str = "columns=[]\nrows=[]"
        self.table_data = None
        try:
            sql_gen_start = datetime.now()
            sql_query, params = self.create_sql_query()
            if DEBUG:
                print(f"DEBUG HYBRID: create_sql_query(): {(datetime.now() - sql_gen_start).total_seconds() * 1000:.2f}ms")
            sql_exec_start = datetime.now()
            try:
                raw_rows = self.execute_sql_query(sql_query, params)
            except NoResultsFoundError:
                raw_rows = []
            sql_exec_time = (datetime.now() - sql_exec_start).total_seconds() * 1000
            if DEBUG:
                print(f"DEBUG HYBRID: execute_sql_query(): {sql_exec_time:.2f}ms")

            rows = self.organize_sql_results(raw_rows, "custom") if raw_rows else []
            llm_context_limit = self.sql_generator.get_llm_context_limit("custom")

            if rows and "_table_type" in rows[0]:
                top_results_for_llm = [r for r in rows if r.get("_table_type") == "top_results"]
                top_results_for_llm = [
                    {k: v for k, v in r.items() if k not in ["_table_type", "_is_aggregation"]}
                    for r in top_results_for_llm
                ]
                if top_results_for_llm:
                    table_str = self._format_results_for_llm(top_results_for_llm, max_rows=llm_context_limit)
                self.table_data = self._format_custom_tables_for_frontend(rows)
            elif rows:
                table_str = self._format_results_for_llm(rows, max_rows=llm_context_limit)
                self.table_data = self._format_table_for_frontend(rows[:SQL_RESULT_LIMIT], "custom")
        except SQLExecutionError as e:
            self.table_data = None
            table_str = f"(No s'han pogut obtenir dades SQL: {e.message})"
        except Exception as e:
            self.table_data = None
            print(f"[HYBRID] Error running SQL: {e}")
            table_str = "(Error en la consulta SQL.)"
        finally:
            self.response.sql_query_type = saved_sql_type

        previous_context_str = ""
        if self.previous_question and self.previous_response:
            truncated_resp = self.previous_response[:PREVIOUS_CONTEXT_MAX_CHARS]
            if len(self.previous_response) > PREVIOUS_CONTEXT_MAX_CHARS:
                truncated_resp += "..."
            previous_context_str = f"""CONTEXT ANTERIOR DEL MISSATGE ANTERIOR:
- Pregunta: "{self.previous_question[:150]}"
- Resposta: "{truncated_resp}"

"""

        hybrid_system = """Ets un expert casteller amb criteri tècnic i rigor històric.
Sempre respons exclusivament en català."""

        hybrid_developer = """INSTRUCCIONS:
- Utilitza qualsevol informació rellevant de les dades estructurades (base de dades) i/o dels fragments de documents.
- No mencionis documents, fonts, consultes, "informació disponible" o "informació proporcionada" ni cap altra meta-referència al context; respon sempre de forma directa amb els fets.
- No inventis fets que no apareguin en el context proporcionat.
- Si una font no aporta res útil, ignora-la sense comentar-ho.
- Text narratiu en 1–3 paràgrafs; **negreta** només per fets clau (pocs)."""

        hybrid_user = f"""{previous_context_str}Pregunta actual:
{self.question}

### Dades estructurades (consulta SQL, tipus custom)
{table_str}

### Fragments de documents (cerca semàntica)
{rag_block}

Respon de forma clara utilitzant qualsevol part del context anterior que sigui pertinent."""

        try:
            llm_start = datetime.now()
            answer = llm_call(
                prompt=hybrid_user,
                model=MODEL_NAME_RESPONSE_RAG,
                system_message=hybrid_system,
                developer_message=hybrid_developer,
            )
            if DEBUG:
                print(f"DEBUG HYBRID: LLM: {(datetime.now() - llm_start).total_seconds() * 1000:.2f}ms")
            answer = sanitize_llm_response(answer)
        except Exception as e:
            return f"No he pogut generar la resposta combinada: {e}"

        self.response = self.response.model_copy(update={"tools": "hybrid", "sql_query_type": "custom"})
        return f"{answer}\n\n*Fonts: Base de dades i documents castellers*"

    def _format_results_for_llm(self, rows: list, max_rows: int = None) -> str:

        if not rows:
            return "columns=[]\nrows=[]"
        
        # Limit rows if specified
        limited_rows = rows[:max_rows] if max_rows else rows
        
        # First pass: collect all column names (skip internal metadata fields)
        # Use the first row to determine column order
        all_columns = []
        for db_col in limited_rows[0].keys():
            if not db_col.startswith('_'):
                # Use human-readable column name if available
                display_col = COLUMN_MAPPINGS.get(db_col, db_col)
                all_columns.append((db_col, display_col))
        
        # Extract just the display column names
        column_names = [display_col for _, display_col in all_columns]
        
        # Second pass: build rows as arrays of values in column order
        formatted_rows = []
        for row in limited_rows:
            row_values = []
            for db_col, display_col in all_columns:
                value = row.get(db_col)
                # Convert None to None (will be represented as null in output)
                row_values.append(value)
            formatted_rows.append(row_values)
        
        # Format as columns=[...]\nrows=[[...],[...]]
        # Use json.dumps for proper formatting of values (handles None, strings, numbers, etc.)
        columns_str = json.dumps(column_names, ensure_ascii=False)
        rows_str = json.dumps(formatted_rows, ensure_ascii=False, default=str)
        
        return f"columns={columns_str}\nrows={rows_str}"

    def _format_table_for_frontend(self, rows: list, query_type: str) -> dict:
        if not rows:
            return None
        
        # ============================================================
        # COLUMNS TO SHOW PER QUERY TYPE
        # Define which columns to display for each query type (in order)
        # Use the database column names here
        # ============================================================
        columns_per_query_type = {
            'millor_diada': ['ranking', 'event_name', 'event_date', 'colla_name', 'event_city', 'castells_fets'],
            'millor_castell': ['gamma_filtrada', 'castell_name', 'event_name', 'date', 'colla_name', 'city', 'status'],
            'castell_historia': ['gamma_filtrada', 'castell_name', 'status', 'count_occurrences', 'colla_name', 'colles', 'first_date', 'last_date', 'cities', ],
            'castells_list': ['gamma_filtrada', 'castell_name', 'status', 'diades', 'places', 'cities', 'colles', 'first_date'],
            'location_actuations': ['event_name', 'date', 'city', 'colla_name', 'castells_fets'],
            'first_castell': ['castell_name', 'status','event_name', 'date', 'colla_name', 'city'],
            'castell_statistics': ['castell_name', 'cops_descarregat', 'cops_carregat', 'cops_intent_desmuntat', 'cops_intent', 'primera_data_descarregat', 'primera_data_carregat', 'colles_descarregat', 'colles_carregat', 'colles_intentat',  'primeres_colles_descarregat', 'primeres_colles_carregat', 'primeres_colles_intentat',],
            'concurs_ranking': ['colla_name', 'position', 'total_points', 'jornada', 'primera_ronda', 'segona_ronda', 'tercera_ronda', 'quarta_ronda', ' cinquena_ronda'],
            'concurs_history': ['any', 'jornada', 'colles_participants', 'colla_guanyadora', 'punts_guanyador', 'castells_r1_descarregats', 'castells_r2_descarregats', 'castells_r3_descarregats', 'castells_r4_descarregats', 'castells_r5_descarregats'],
            'year_summary': ['gamma_filtrada', 'colla_name', 'num_actuacions', 'num_castells', 'castells_descarregats', 'castells_carregats', 'castells_intent_desmuntat', 'castells_intent'],
            'colles': ['colla_name', 'diada', 'lloc', 'any', 'castells_fets', 'castell_name', 'cops_descarregat', 'cops_carregat', 'cops_intent', 'cops_intent_desmuntat', 'primera_data_descarregat', 'primera_data_carregat', 'primera_data'],
            'punts': ['castell_name', 'punts_descarregat', 'punts_carregat', 'event_name', 'event_date', 'colla_name', 'event_city', 'castells_fets', 'total_punts'],
        }
        # ============================================================
        
        # Get original headers from the data
        all_headers = list(rows[0].keys())
        
        # Determine which columns to show
        if query_type in columns_per_query_type:
            # Use only specified columns (in the specified order)
            selected_columns = [col for col in columns_per_query_type[query_type] if col in all_headers]
        else:
            # Default: show all columns
            selected_columns = all_headers
        
        # Map headers to nice display names
        nice_headers = [COLUMN_MAPPINGS.get(col, col.replace('_', ' ').title()) for col in selected_columns]
        
        # Helper to truncate comma-separated lists (for cities, colles columns)
        def truncate_list(value: str, max_items: int = 10) -> str:
            if not value or value == '-':
                return value
            items = [item.strip() for item in value.split(',')]
            if len(items) > max_items:
                return ', '.join(items[:max_items]) + '...'
            return value
        
        # Columns that should be truncated if they have too many items
        truncate_columns = {'cities', 'colles', 'places', 'diades'}
        
        # Format rows with only selected columns
        formatted_rows = []
        for row in rows:
            formatted_row = []
            for col in selected_columns:
                value = row.get(col)
                if value is None:
                    formatted_row.append('-')
                elif col in truncate_columns:
                    formatted_row.append(truncate_list(str(value)))
                else:
                    formatted_row.append(str(value))
            formatted_rows.append(formatted_row)
        
        return {
            'title': TITLE_MAPPINGS.get(query_type, 'Resultats'),
            'columns': nice_headers,
            'rows': formatted_rows
        }

    def _format_custom_tables_for_frontend(self, rows: list) -> list:
        """
        Format multiple tables for custom queries.
        Returns a list of table dictionaries, one for each table type.
        """
        if not rows:
            return []
        
        # Separate rows by table type
        tables_by_type = {
            'top_results': [],
            'castell_aggregations': [],
            'colla_aggregations': [],
            'diada_aggregations': []
        }
        
        for row in rows:
            table_type = row.get('_table_type', 'top_results')
            if table_type in tables_by_type:
                # Remove internal fields
                clean_row = {k: v for k, v in row.items() 
                           if k not in ['_table_type', '_is_aggregation']}
                tables_by_type[table_type].append(clean_row)
        
        # Define column mappings for each table type
        custom_columns = {
            'top_results': ['event_name', 'event_date', 'colla_name', 'event_city', 'castell_name', 'status'],
            'castell_aggregations': ['castell', 'status', 'first_date', 'first_diada', 'count'],
            'colla_aggregations': ['colla', 'year', 'top_5_castells', 'best_diada', 'num_diades', 'num_castells'],
            'diada_aggregations': ['colla', 'castells_fets', 'date', 'location']
        }
        
        # Define titles for each table type
        custom_titles = {
            'top_results': 'Top 10 Resultats',
            'castell_aggregations': 'Agregació per Castell i Status',
            'colla_aggregations': 'Agregació per Colla i Any',
            'diada_aggregations': 'Agregació per Diada i Colla'
        }
        
        # Format each table
        formatted_tables = []
        for table_type, table_rows in tables_by_type.items():
            if not table_rows:
                continue
            
            # Get columns for this table type
            all_headers = list(table_rows[0].keys())
            selected_columns = [col for col in custom_columns.get(table_type, []) if col in all_headers]
            if not selected_columns:
                selected_columns = all_headers
            
            # Map headers to nice display names
            nice_headers = [COLUMN_MAPPINGS.get(col, col.replace('_', ' ').title()) for col in selected_columns]
            
            # Format rows
            formatted_rows = []
            for row in table_rows:
                formatted_row = []
                for col in selected_columns:
                    value = row.get(col)
                    if value is None:
                        formatted_row.append('-')
                    else:
                        formatted_row.append(str(value))
                formatted_rows.append(formatted_row)
            
            formatted_tables.append({
                'title': custom_titles.get(table_type, 'Resultats'),
                'columns': nice_headers,
                'rows': formatted_rows
            })
        
        return formatted_tables


    def handle_sql(self) -> str:
        try:
            # Get the SQL query type
            sql_query_type = getattr(self.response, 'sql_query_type', 'custom')
            
            # Generate SQL query and parameters
            sql_gen_start = datetime.now()
            sql_query, params = self.create_sql_query()
            sql_gen_time = (datetime.now() - sql_gen_start).total_seconds() * 1000
            if DEBUG:
                print(f"DEBUG SQL: create_sql_query(): {sql_gen_time:.2f}ms")
            
            # Execute the query
            sql_exec_start = datetime.now()
            try:
                raw_rows = self.execute_sql_query(sql_query, params)
            except NoResultsFoundError:
                self.table_data = None
                if DEBUG:
                    print("DEBUG SQL: NoResultsFoundError -> falling back to RAG")
                if self.response is not None:
                    self.response.tools = "rag"
                    self.response.sql_query_type = "custom"
                return self.handle_rag(final_top_k=2)
            except SQLExecutionError as e:
                self.table_data = None
                return e.message
            sql_exec_time = (datetime.now() - sql_exec_start).total_seconds() * 1000
            if DEBUG:
                print(f"DEBUG SQL: execute_sql_query(): {sql_exec_time:.2f}ms")
            
            # Organize results based on query type (V2 approach)
            organize_start = datetime.now()
            rows = self.organize_sql_results(raw_rows, sql_query_type)
            organize_time = (datetime.now() - organize_start).total_seconds() * 1000
            if DEBUG:
                print(f"DEBUG SQL: organize_results(): {organize_time:.2f}ms")

            # Summarize results into a readable answer
            
            # Get personalized LLM context limit for this query type
            llm_context_limit = self.sql_generator.get_llm_context_limit(sql_query_type)
            
            # For custom queries, separate tables and only pass top_results to LLM
            if sql_query_type == 'custom' and rows and '_table_type' in rows[0]:
                # Separate rows by table type
                top_results_for_llm = [r for r in rows if r.get('_table_type') == 'top_results']
                # Remove _table_type and _is_aggregation from LLM input
                top_results_for_llm = [{k: v for k, v in r.items() 
                                       if k not in ['_table_type', '_is_aggregation']} 
                                      for r in top_results_for_llm]
                
                # Convert top_results to compact column-header format for LLM (only top 10, no IDs)
                if top_results_for_llm:
                    table_str = self._format_results_for_llm(top_results_for_llm, max_rows=llm_context_limit)
                    if DEBUG:
                        print(f"DEBUG SQL: Results for LLM (showing {min(len(top_results_for_llm), llm_context_limit)}/{len(top_results_for_llm)} rows from top_results table)\n", table_str)
                else:
                    table_str = "columns=[]\nrows=[]"
                
                # Store multiple tables for frontend display
                self.table_data = self._format_custom_tables_for_frontend(rows)
            else:
                # Convert rows to compact column-header format for LLM (limited for LLM context)
                table_str = self._format_results_for_llm(rows, max_rows=llm_context_limit) if rows else "columns=[]\nrows=[]"
                if DEBUG:
                    print(f"DEBUG SQL: Results for LLM (showing {min(len(rows), llm_context_limit)}/{len(rows)} rows)\n", table_str)
                
                # Store table data for frontend display (full results up to SQL_RESULT_LIMIT)
                # Create a nice table structure with proper column titles
                self.table_data = self._format_table_for_frontend(rows[:SQL_RESULT_LIMIT], sql_query_type)
            
            castell_ap_notation_hint = False
            if self.castells:
                for c in self.castells:
                    code = getattr(c, "castell_code", None) or ""
                    if castell_code_may_alias_agulla_pilar(code):
                        castell_ap_notation_hint = True
                        break

            # Use structured prompt with system/developer/user separation (including previous context)
            results_context = sql_results_description_for_query_type(sql_query_type)
            structured_prompt = get_sql_summary_prompt(
                sql_query_type, 
                self.question, 
                table_str,
                previous_question=self.previous_question,
                previous_response=self.previous_response,
                previous_context_max_chars=PREVIOUS_CONTEXT_MAX_CHARS,
                castell_ap_notation_hint=castell_ap_notation_hint,
                results_context=results_context,
            )

            try:
                sql_llm_start = datetime.now()
                final_answer = llm_call(
                    prompt=structured_prompt.user_prompt,
                    model=MODEL_NAME_RESPONSE,
                    system_message=structured_prompt.system_message,
                    developer_message=structured_prompt.developer_message
                )
                sql_llm_time = (datetime.now() - sql_llm_start).total_seconds() * 1000
                if DEBUG:
                    print(f"DEBUG SQL: LLM summary call: {sql_llm_time:.2f}ms")
                
                # Sanitize response to remove any tables the LLM might have added
                final_answer = sanitize_llm_response(final_answer)
            except Exception as e:
                return f"He pogut obtenir dades, però no generar una explicació: {e}\nConsulta SQL:\n{sql_query}"

            # Return the final answer with source attribution
            return f"{final_answer}\n\n*Font: Base de dades de la CCCC*"
            
        except SQLExecutionError as e:
            return e.message
        except Exception as e:
            # For any other unexpected errors, return a friendly message
            print(f"[ERROR] Unexpected error in handle_sql(): {e}")
            return "No he pogut analitzar la pregunta. Torna-ho a intentar amb una pregunta diferent."


    def _fallback_to_sql_custom_if_no_info(self, current_response: str) -> Optional[str]:
        """
        If the current response contains "No tinc informació sobre aquest tema"
        and we are in a follow-up (we have previous entities), do a fallback
        to SQL custom merging current entities with previous ones.

        Per-type override rule: current entities win; for types missing in current,
        we inherit from the previous question.

        If after merging there are no entities at all, do nothing (returns None).
        Returns the new response string if the fallback was executed, else None.
        """
        if not current_response or "No tinc informació sobre aquest tema" not in current_response:
            return None

        if not self.previous_entities or not self.response:
            return None

        def to_list_str(value) -> list:
            if not value:
                return []
            if isinstance(value, list):
                return [str(x).strip() for x in value if x is not None and str(x).strip()]
            if isinstance(value, str):
                return [s.strip() for s in value.split(",") if s.strip()]
            return [str(value)]

        # Current entities (already on self.* after decide_route)
        current_colla = to_list_str(self.colles_castelleres)
        current_castells = list(self.castells) if self.castells else []
        current_anys = to_list_str(self.anys)
        current_llocs = to_list_str(self.llocs)
        current_diades = to_list_str(self.diades)
        current_gamma = self.gamma

        # Previous entities (from previous_entities dict, possibly different shapes)
        prev_colla = to_list_str(self.previous_entities.get("colles"))
        prev_anys = to_list_str(self.previous_entities.get("anys"))
        prev_llocs = to_list_str(self.previous_entities.get("llocs"))
        prev_diades = to_list_str(self.previous_entities.get("diades"))
        prev_gamma = self.previous_entities.get("gamma")
        if isinstance(prev_gamma, list):
            prev_gamma = prev_gamma[0] if prev_gamma else None

        prev_castells_raw = self.previous_entities.get("castells") or []
        prev_castells: list = []
        for c in prev_castells_raw:
            if isinstance(c, Castell):
                prev_castells.append(c)
            elif isinstance(c, dict):
                code = c.get("castell_code") or c.get("code")
                if code:
                    prev_castells.append(Castell(castell_code=code, status=c.get("status")))
            elif isinstance(c, str):
                prev_castells.append(Castell(castell_code=c, status=None))

        # Per-type override: current wins; otherwise inherit from previous
        merged_colla = current_colla if current_colla else prev_colla
        merged_castells = current_castells if current_castells else prev_castells
        merged_anys = current_anys if current_anys else prev_anys
        merged_llocs = current_llocs if current_llocs else prev_llocs
        merged_diades = current_diades if current_diades else prev_diades
        merged_gamma = current_gamma if current_gamma else prev_gamma

        # If after merging there are no entities at all, do nothing
        has_any_entity = bool(
            merged_colla or merged_castells or merged_anys
            or merged_llocs or merged_diades or merged_gamma
        )
        if not has_any_entity:
            return None

        if DEBUG:
            print("[FALLBACK NO-INFO] Triggered after follow-up with 'No tinc informació' response")
            print(f"  merged colla={merged_colla}")
            print(f"  merged castells={[getattr(c, 'castell_code', c) for c in merged_castells]}")
            print(f"  merged anys={merged_anys}")
            print(f"  merged llocs={merged_llocs}")
            print(f"  merged diades={merged_diades}")
            print(f"  merged gamma={merged_gamma}")

        # Apply merged entities to self.* (lists, as expected by handle_sql)
        self.colles_castelleres = merged_colla
        self.castells = merged_castells
        self.anys = merged_anys
        self.llocs = merged_llocs
        self.diades = merged_diades
        self.gamma = merged_gamma

        # Force SQL route with custom query type and update response object
        self.response.tools = "sql"
        self.response.sql_query_type = "custom"
        self.response.colla = merged_colla
        self.response.castells = merged_castells
        self.response.anys = merged_anys
        self.response.llocs = merged_llocs
        self.response.diades = merged_diades

        # Re-run SQL handler with merged entities
        return self.handle_sql()

    def run_handlers_after_route(self) -> str:
        """
        Execute the handler for the current `self.response` (after decide_route) and apply
        the no-info SQL fallback. Used by process_question and by main's two-phase chat path.
        """
        response = self.response
        if not response:
            return "No estic segur de com respondre això, però ho estic intentant!"

        handler_start = datetime.now()
        if response.tools == "direct":
            result = self.handle_direct()
        elif response.tools == "rag":
            n_entity_groups = self._count_distinct_entity_field_groups(response)
            if n_entity_groups >= 3:
                result = self.handle_hybrid_rag_sql(rag_top_k=2)
            else:
                result = self.handle_rag()
        elif response.tools == "sql":
            result = self.handle_sql()
        else:
            result = "No estic segur de com respondre això, però ho estic intentant!"

        handler_time = (datetime.now() - handler_start).total_seconds() * 1000
        if DEBUG:
            eff = getattr(response, "tools", "")
            print(f"DEBUG HANDLER: route={eff} -> {handler_time:.2f}ms (final tools={getattr(self.response, 'tools', eff)})")

        fallback_result = self._fallback_to_sql_custom_if_no_info(result)
        if fallback_result is not None:
            result = fallback_result

        return result

    def process_question(self, question: str) -> str:

        # Step 1: Decide route
        route_start = datetime.now()
        response = self.decide_route(question)
        route_time = (datetime.now() - route_start).total_seconds() * 1000
        if DEBUG:
            print(f"DEBUG DECIDEROUTE TIME: {route_time:.2f}ms")
        
        # Store response for later access (e.g., getting route_used)
        self.response = response
        if DEBUG:
            print(f"DEBUG ROUTER: Ruta escollida: {response.tools}, {response.sql_query_type}")

        return self.run_handlers_after_route()

# ---- Agent principal ----
def xiquet_agent(
    question: str, 
    previous_question: str = None, 
    previous_response: str = None,
    previous_route: str = None,
    previous_sql_query_type: str = None,
    previous_entities: dict = None,
    pre_selected_entities: dict = None
) -> str:

    xiquet = Xiquet(
        previous_question=previous_question,
        previous_response=previous_response,
        previous_route=previous_route,
        previous_sql_query_type=previous_sql_query_type,
        previous_entities=previous_entities,
        pre_selected_entities=pre_selected_entities
    )
    return xiquet.process_question(question)

# ---- Exemple d'ús ----
if __name__ == "__main__":
    xiquet = Xiquet()
    while True:
        q = input("Pregunta (en català, 'sortir' per acabar): ")
        if q.lower() == "sortir":
            break
        print("Xiquet.cat:", xiquet.process_question(q))
        print("-" * 50)






# SOME LEGACY CODE 

#     def handle_hybrid(self) -> str:

#         from datetime import datetime
        
#         try:
#             # Step 1: Try to get SQL results first
#             sql_gen_start = datetime.now()
#             sql_query, params = self.create_sql_query()
#             sql_gen_time = (datetime.now() - sql_gen_start).total_seconds() * 1000
#             print(f"[TIMING] hybrid create_sql_query(): {sql_gen_time:.2f}ms")
            
#             sql_exec_start = datetime.now()
#             try:
#                 sql_rows = self.execute_sql_query(sql_query, params)
#             except NoResultsFoundError:
#                 sql_rows = []  # Continue with RAG context only
#             except SQLExecutionError as e:
#                 # SQL execution failed, return friendly message instead of falling back to RAG
#                 return e.message
#             sql_exec_time = (datetime.now() - sql_exec_start).total_seconds() * 1000
#             print(f"[TIMING] hybrid execute_sql_query(): {sql_exec_time:.2f}ms")
            
#             # Step 2: Get RAG context
#             rag_search_start = datetime.now()
#             rag_results = search_castellers_info(self.question, k=3)
#             rag_search_time = (datetime.now() - rag_search_start).total_seconds() * 1000
#             print(f"[TIMING] hybrid RAG search_castellers_info(): {rag_search_time:.2f}ms")
            
#             # Step 3: Prepare SQL context
#             sql_context = ""
#             if sql_rows:
#                 header = list(sql_rows[0].keys())
#                 table_str = "\n".join([" | ".join(header)] + [" | ".join(str(v) for v in r.values()) for r in sql_rows[:5]])
#                 sql_context = f"""
#                     ### Dades estructurades de la base de dades:
#                     {table_str}
#                     """
#             else:
#                 sql_context = ""
            
#             # Step 4: Prepare RAG context
#             rag_context = ""
#             if rag_results:
#                 rag_parts = []
#                 for i, (doc_info, score) in enumerate(rag_results, 1):
#                     meta = doc_info.get("meta", {})
#                     text = doc_info.get("text", "")
                    
#                     # Add metadata context
#                     context_info = []
#                     if meta.get("colla_name"):
#                         context_info.append(f"Colla: {meta['colla_name']}")
#                     if meta.get("date"):
#                         context_info.append(f"Data: {meta['date']}")
#                     if meta.get("place"):
#                         context_info.append(f"Lloc: {meta['place']}")
#                     if meta.get("category"):
#                         context_info.append(f"Categoria: {meta['category']}")
                    
#                     context_str = f"[Document {i}] " + "; ".join(context_info) + f"\n{text}"
#                     rag_parts.append(context_str)
                
#                 rag_context = f"""
#                     ### Informació contextual dels documents:
#                     {chr(10).join(rag_parts)}
#                     """
#             else:
#                 rag_context = ""
            
#             # Step 5: Generate comprehensive answer using both sources with structured prompts
#             hybrid_system = """Ets un expert casteller amb criteri tècnic i rigor històric.
# Sempre respons exclusivament en català.
# Segueixes estrictament les instruccions de format i sortida."""
            
#             hybrid_developer = """INSTRUCCIONS ESTRICTES (OBLIGATÒRIES):

# PROHIBIT:
# - Afegir taules
# - Afegir llistes amb guions o punts
# - Repetir dades literals
# - Mencionar punts o puntuacions numèriques
# - Donar opinions o valoracions personals

# FORMAT DE SORTIDA:
# - Markdown, text narratiu (paràgrafs)
# - Únic ús de **negreta** per destacar fets rellevants (màxim 3-4 elements)

# CONTEXT ESPECÍFIC:
# - Combina la informació de les dues fonts (SQL i RAG)
# - Prioritza dades SQL per informació específica (dates, estadístiques)
# - Utilitza RAG per context històric o explicacions
# - Respon en 1-2 paràgrafs màxim
# - Si hi ha context anterior, tingues-lo en compte per entendre preguntes de seguiment"""

#             # Build previous context section for user prompt
#             previous_context_str = ""
#             if self.previous_question and self.previous_response:
#                 truncated_resp = self.previous_response[:PREVIOUS_CONTEXT_MAX_CHARS]
#                 if len(self.previous_response) > PREVIOUS_CONTEXT_MAX_CHARS:
#                     truncated_resp += "..."
#                 previous_context_str = f"""CONTEXT ANTERIOR:
# - Pregunta: "{self.previous_question[:150]}"
# - Resposta: "{truncated_resp}"

# """

#             hybrid_user = f"""{previous_context_str}Pregunta actual:
# {self.question}

# {sql_context}

# {rag_context}

# Respon de forma breu i directa combinant ambdues fonts."""
            
#             hybrid_llm_start = datetime.now()
#             answer = llm_call(
#                 prompt=hybrid_user,
#                 model=MODEL_NAME_RESPONSE,
#                 system_message=hybrid_system,
#                 developer_message=hybrid_developer
#             )
#             hybrid_llm_time = (datetime.now() - hybrid_llm_start).total_seconds() * 1000
#             print(f"[TIMING] handle_hybrid() LLM call: {hybrid_llm_time:.2f}ms")
            
#             # Sanitize response to remove any tables
#             answer = sanitize_llm_response(answer)
            
#             # Step 6: Add provenance information
#             provenance = "*Fonts: SQL + RAG*"
            
#             return f"{answer}\n\n{provenance}"
            
#         except SQLExecutionError as e:
#             # SQL execution error - return friendly message
#             return e.message
#         except Exception as e:
#             # Fallback to RAG only if SQL fails for other reasons
#             try:
#                 print(f"[Hybrid] SQL failed, falling back to RAG: {e}")
#                 return self.handle_rag()
#             except Exception as rag_error:
#                 # If RAG also fails, return friendly message
#                 print(f"[ERROR] Both SQL and RAG failed: {e}, {rag_error}")
#                 return "No he pogut analitzar la pregunta. Torna-ho a intentar amb una pregunta diferent."
