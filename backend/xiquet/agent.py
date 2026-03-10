import re
import unicodedata
from typing import List, Optional
from langdetect import detect
from database_pipeline.rag_index_supabase import search_query_supabase
from database_pipeline.load_castellers_info_chunks import search_castellers_info
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
    get_all_diada_options

)
from .llm_sql_v2 import LLMSQLGeneratorV2 as LLMSQLGenerator, get_sql_summary_prompt, NoResultsFoundError, SQLExecutionError, NO_RESULTS_MESSAGE, SQL_RESULT_LIMIT
from .llm_function import llm_call, is_guardrail_violation
from .util_dics import SQL_QUERY_PATTERNS, IS_SQL_QUERY_PATTERNS, COLUMN_MAPPINGS, TITLE_MAPPINGS, GAMMA_CASTELLS, GAMMA_KEYWORDS, MAP_QUERY_CHANGE
from .rag import rerank_rag_results
from difflib import SequenceMatcher
from rapidfuzz import fuzz, process
from datetime import datetime


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
MODEL_NAME_RESPONSE = "sambanova:Meta-Llama-3.3-70B-Instruct"

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

PREVIOUS_CONTEXT_MAX_CHARS = 100 

# ---- Xiquet Class ----
class Xiquet:
    def __init__(
        self, 
        previous_question: str = None, 
        previous_response: str = None,
        previous_route: str = None,
        previous_sql_query_type: str = None,
        previous_entities: dict = None
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
    
    def _handle_follow_up_detection(self, question: str, response: FirstCallResponseFormat) -> bool:
        if not (self.previous_route == "sql" and self.previous_sql_query_type):
            return False
        
        question_lower = question.lower().strip()
        
        # Detect follow-up patterns: short question + starts with "I els...", "I de...", etc.
        follow_up_patterns = ["i els ", "i de ", "i dels ", "i la ", "i les ", "i el ", "i al ", "i a ","i l'"]
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
        
        # Helper to convert comma-separated string to list
        def str_to_list(s: str) -> list:
            if not s:
                return []
            return [x.strip() for x in s.split(",") if x.strip()]
        
        # Helper to convert list back to comma-separated string
        def list_to_str(lst: list) -> str:
            return ", ".join(lst)
        
        # Enrich colles (string, comma-separated)
        if self.previous_entities.get("colles"):
            current_colles = str_to_list(self.colles_castelleres)
            for colla in self.previous_entities["colles"]:
                if colla and colla not in current_colles:
                    current_colles.append(colla)
            self.colles_castelleres = list_to_str(current_colles)
        
        # Enrich castells (List[Castell] - the only real list!)
        if self.previous_entities.get("castells"):
            current_castell_codes = {c.castell_code if hasattr(c, 'castell_code') else str(c) for c in self.castells}
            for c in self.previous_entities["castells"]:
                castell_code = c.get("castell_code") if isinstance(c, dict) else (c.castell_code if hasattr(c, 'castell_code') else str(c))
                if castell_code and castell_code not in current_castell_codes:
                    self.castells.append(Castell(castell_code=castell_code, status=None))
        
        # Enrich anys (string, comma-separated)
        if self.previous_entities.get("anys"):
            current_anys = str_to_list(self.anys)
            for a in self.previous_entities["anys"]:
                any_str = str(a)
                if any_str and any_str not in current_anys:
                    current_anys.append(any_str)
            self.anys = list_to_str(current_anys)
        
        # Enrich llocs (string, comma-separated)
        if self.previous_entities.get("llocs"):
            current_llocs = str_to_list(self.llocs)
            for lloc in self.previous_entities["llocs"]:
                if lloc and lloc not in current_llocs:
                    current_llocs.append(lloc)
            self.llocs = list_to_str(current_llocs)
        
        # Enrich diades (string, comma-separated)
        if self.previous_entities.get("diades"):
            current_diades = str_to_list(self.diades)
            for diada in self.previous_entities["diades"]:
                if diada and diada not in current_diades:
                    current_diades.append(diada)
            self.diades = list_to_str(current_diades)

        # Enrich gamma (string, comma-separated)
        if self.previous_entities.get("gamma"):
            current_gamma = str_to_list(self.gamma)
            for gamma in self.previous_entities["gamma"]:
                if gamma and gamma not in current_gamma:
                    current_gamma.append(gamma)
            self.gamma = list_to_str(current_gamma)
    
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
            if lang not in ["ca", "es", 'pt', 'fr']:
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
        
        # 3. Analitza si la pregunta té més de 25 tokens
        tokens = re.findall(r'\b\w+\b', question)
        if len(tokens) > 25:
            return FirstCallResponseFormat(
                tools="direct",
                sql_query_type="",
                direct_response="La teva pregunta és massa llarga. Si us plau, fes una pregunta més concisa i específica sobre el món casteller.",
                colla=[], castells=[], anys=[], llocs=[], diades=[]
            )
        
        # Si no es compleix cap condició, retorna None per continuar processant
        return None

    def _validate_response_entities(self, response: FirstCallResponseFormat) -> Optional[FirstCallResponseFormat]:

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
            if response.sql_query_type not in ["millor_diada", "millor_castell", "castell_historia", "castells_list", "location_actuations", "first_castell", "castell_statistics", "year_summary", "concurs_ranking", "concurs_history", "colles", "custom"]:
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
                            score_cutoff=75
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

        # Validate any (only if not empty)
        if response.anys:
            valid_anys = get_all_any_options()
            for yr in response.anys:
                if yr not in valid_anys:
                    print(f"Error: Any {yr} no és vàlid")
                    response.anys.remove(yr)

        # Validate lloc (only if not empty)
        if response.llocs:
            valid_llocs = get_all_lloc_options()
            for lloc in response.llocs:
                if lloc not in valid_llocs:
                    print(f"Error: Lloc {lloc} no és vàlid")
                    response.llocs.remove(lloc)

        # Validate diada (only if not empty)
        if response.diades:
            valid_diades = get_all_diada_options()
            for diada in response.diades:
                if diada not in valid_diades:
                    print(f"Error: Diada {diada} no és vàlida")
                    response.diades.remove(diada)
        validation_time = (datetime.now() - validation_start).total_seconds() * 1000
        print(f"[TIMING] Entity validation: {validation_time:.2f}ms")

        # When gamma is detected, clear individual castells to avoid redundant chips
        # The gamma filter will handle the castell filtering in SQL
        if self.gamma:
            response.castells = []
            print(f"[Gamma] Clearing individual castells - gamma filter will handle: {self.gamma}")

        if DEBUG:
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

        # Extract entities from question (heuristics)
        entity_start = datetime.now()
        self.colles_castelleres = get_colles_castelleres_subset(question)
        self.castells = get_castells_with_status_subset(question)
        self.anys = get_anys_subset(question)
        self.llocs = get_llocs_subset(question)
        self.diades = get_diades_subset(question)
        self.gamma = self._detect_gamma(question)
        
        # Enrich entity lists with previous context entities (so LLM can see them as options)
        self._enrich_entities_from_previous_context()
        
        entity_time = (datetime.now() - entity_start).total_seconds() * 1000
        print(f"[TIMING] Entity extraction: {entity_time:.2f}ms")

        # Build dynamic entities section
        entities_section = ""
        if self.colles_castelleres:
            entities_section += f"""
        - **Colla castellera:** Nom de la colla castellera.  
        Possibles opcions: {self.colles_castelleres}
         \n"""
        
        if self.castells:
            entities_section += f"""
        - **Castell o castells:** Tipus de construcció castellera amb estat opcional.  
        Possibles opcions: {self.castells}
        Cada castell pot tenir un estat: Descarregat, Carregat, Intent, Intent desmuntat, o cap estat (posa null).
        \n"""
        else:
            entities_section += f"""
        - **Castell o castells:** No extreguis cap castell.  
        \n"""
        
        if self.anys:
            entities_section += f"""
        - **Any:** Any concret d'una actuació o d'una referència temporal (per exemple, "2024", "2025", etc.)  
        \n"""
        else:
            entities_section += f"""
        - **Any:** No extreguis cap any.  
        \n"""

        
        if self.llocs:
            entities_section += f"""
        - **Lloc:** Ciutat o població de certa actuació.  
        Possibles opcions: {self.llocs}
        \n"""
        
        if self.diades and self.diades.strip():
            entities_section += f"""
        - **Diada:** Nom de la diada o jornada castellera.  
        Possibles opcions: {self.diades}
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
        
        route_prompt = f"""
        Ets el Xiquet, un assistent expert en el món casteller. 
        La teva tasca és analitzar la següent pregunta sobre castells:  
        > "{question}"

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
        > "{question}"
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
            print(f"[TIMING] abans_de_res(): {precheck_time:.2f}ms")
        
        if direct_response is not None:
            return direct_response
        
        # Generate route prompt (extracts entities and builds prompt)
        llm_start = datetime.now()
        route_prompt = self.generate_prompt_decide_route(question)

        response = llm_call(route_prompt, model=MODEL_NAME_ROUTE, response_format=FirstCallResponseFormat)
        llm_time = (datetime.now() - llm_start).total_seconds() * 1000
        print(f"[TIMING] decide_route() LLM call: {llm_time:.2f}ms")
        
        # Handle case where provider returns dict instead of Pydantic model
        if isinstance(response, dict):
            print(f"[WARNING] LLM returned dict instead of FirstCallResponseFormat, converting...")
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
        
        sql_type_start = datetime.now()
        
        # Remove llocs that are part of colla names and only appear once in the query
        self._remove_llocs_in_colla_names(question, response)
        
        # Handle follow-up detection (forces SQL route and inherits entities if applicable)
        skip_sql_check = self._handle_follow_up_detection(question, response)
        
        if response.tools == "rag" or response.tools == "direct":
            if response.tools == "direct":
                threshold = 0.75
            else:
                threshold = 0.65
            # Only attempt SQL determination if entities exist
            if response.colla or response.castells or response.anys or response.llocs or response.diades:
                response.sql_query_type = self._determine_sql_query_type(question, response, IS_SQL_QUERY_PATTERNS, threshold=threshold)
                if response.sql_query_type != "custom":
                    response.tools = "sql"
                    skip_sql_check = True

        
        # If SQL or hybrid, determine the specific query type
        if response.tools in ["sql", "hybrid"] and not skip_sql_check:
            # Fast fuzzy matching (current default)
            response.sql_query_type = self._determine_sql_query_type(question, response, SQL_QUERY_PATTERNS)

            # INHERIT SQL QUERY TYPE FROM PREVIOUS MESSAGE IF CURRENT IS "custom"
            # This handles follow-up questions like "I els Minyons?" after asking about Vilafranca
            if response.sql_query_type == "custom" and self.previous_sql_query_type:
                valid_types = ["millor_diada", "millor_castell", "castell_historia", "castells_list", "location_actuations", 
                              "first_castell", "castell_statistics", "year_summary", "concurs_ranking", "concurs_history", "colles"]
                if self.previous_sql_query_type in valid_types:
                    print(f"[SQL TYPE INHERIT] Inheriting '{self.previous_sql_query_type}' from previous question (current was 'custom')")
                    response.sql_query_type = self.previous_sql_query_type
        
        sql_type_time = (datetime.now() - sql_type_start).total_seconds() * 1000
        print(f"[TIMING] SQL query type determination: {sql_type_time:.2f}ms")

        # Validate all entities and tools
        validation_result = self._validate_response_entities(response)
        if validation_result is not None:
            return validation_result

        # Update self with validated entities
        self.colles_castelleres = response.colla
        self.castells = response.castells
        self.anys = response.anys
        self.llocs = response.llocs
        self.diades = response.diades
        self.editions = response.editions
        self.jornades = response.jornades
        self.positions = response.positions

        return response

    def _determine_sql_query_type(self, question: str, response: FirstCallResponseFormat, query_patterns: dict = SQL_QUERY_PATTERNS, threshold: float = 0.5) -> str:
    
        question_lower = question.lower()
        
        # Calculate similarity scores for each query type
        scores = {}
        for query_type, patterns in query_patterns.items():
            max_similarity = 0
            for pattern in patterns:
                # Calculate similarity between question and pattern
                similarity = SequenceMatcher(None, question_lower, pattern).ratio()
                max_similarity = max(max_similarity, similarity)
            
            # Also check for partial matches (substring matching)
            partial_matches = sum(1 for pattern in patterns if pattern in question_lower)
            if partial_matches > 0:
                # Boost score for exact substring matches
                max_similarity = max(max_similarity, 0.65)
            
            scores[query_type] = max_similarity
        
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

    def create_sql_query(self) -> tuple[str, dict]:
        # Build entities dictionary
        entities = {
            "colla": self.colles_castelleres,
            "castells": self.castells,
            "anys": self.anys,
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
            "anys": self.anys,
            "llocs": self.llocs,
            "diades": self.diades,
            "editions": self.editions,
            "jornades": self.jornades,
            "positions": self.positions,
            "gamma": self.gamma
        }
        return self.sql_generator.organize_results(raw_results, sql_query_type, entities)


    def handle_rag(self) -> str:
        print(f"[RAG] === Starting handle_rag() ===", flush=True)
        print(f"[RAG] Question: {self.question[:50]}...", flush=True)
        
        # Configuration
        INITIAL_K = 350          # Get top K from vector search
        FINAL_TOP_K = 2         # Pass top K to LLM
        MIN_SIMILARITY = 0.005   # Minimum similarity threshold
        
        try:
            # Step 1: Semantic search on castellers_info_chunks
            print(f"[RAG] Step 1: Calling search_castellers_info(k={INITIAL_K})...", flush=True)
            rag_search_start = datetime.now()
            results = search_castellers_info(self.question, k=INITIAL_K)
            rag_search_time = (datetime.now() - rag_search_start).total_seconds() * 1000
            print(f"[TIMING] RAG search: {rag_search_time:.2f}ms ({len(results)} results)", flush=True)
            
            if not results:
                return "No he trobat informació rellevant per respondre la teva pregunta."
            
            # Step 2: Rerank FIRST (boost colles, keywords, etc.) BEFORE filtering
            # This ensures documents mentioning the exact colla get boosted before threshold check
            entities = {
                "colla": self.colles_castelleres,
                "anys": self.anys,
                "llocs": self.llocs,
                "castells": self.castells,
                "diades": self.diades
            }
            
            rerank_start = datetime.now()
            reranked = rerank_rag_results(results, entities, self.question)
            rerank_time = (datetime.now() - rerank_start).total_seconds() * 1000
            print(f"[TIMING] Reranking: {rerank_time:.2f}ms")
            
            # Step 3: Filter by minimum similarity AFTER boosting
            # Documents with low embedding score but high entity match can now pass
            filtered = [(doc, score) for doc, score in reranked if score >= MIN_SIMILARITY]
            print(f"[RAG] Filtered after boost: {len(reranked)} -> {len(filtered)} (threshold: {MIN_SIMILARITY})")
            
            if not filtered:
                return "No he trobat informació prou rellevant per respondre la teva pregunta."
            
            # Step 4: Take top K results
            top_results = reranked[:FINAL_TOP_K]
            print(f"[RAG] Final top {len(top_results)} results:")
            for i, (doc, score) in enumerate(top_results):
                print(f"  {i+1}. [{score:.3f}] {doc['meta'].get('title', 'No title')}")
            
            # Step 5: Build context for LLM
            context_parts = []
            for i, (doc_info, score) in enumerate(top_results, 1):
                title = doc_info["meta"].get("title", "")
                text = doc_info.get("text", "")
                context_parts.append(f"[Document {i}: {title}]\n{text}")
            
            context = "\n\n".join(context_parts)
            
            # Step 6: Generate answer with LLM
            rag_system = """Ets un expert casteller amb criteri tècnic i rigor històric.
Sempre respons exclusivament en català."""
            
            rag_developer = """INSTRUCCIONS:
- Text narratiu en paràgrafs (1-3 paràgrafs màxim)
- Usa **negreta** per destacar fets clau
- NO inventes informació que no apareix als documents
- Si els documents NO contenen informació rellevant per respondre la pregunta, digues ÚNICAMENT I EXCLUSIVAMENT: "No tinc informació sobre aquest tema." 
- NO mencions ni facis referència a documents que no siguin rellevants per la pregunta 
- Només utilitza informació que respongui directament a la pregunta de l'usuari"""

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

Documents:
{context}

Respon basant-te en els documents."""
            
            rag_llm_start = datetime.now()
            answer = llm_call(
                prompt=rag_user,
                model=MODEL_NAME_RESPONSE,
                system_message=rag_system,
                developer_message=rag_developer
            )
            rag_llm_time = (datetime.now() - rag_llm_start).total_seconds() * 1000
            print(f"[TIMING] handle_rag() LLM call: {rag_llm_time:.2f}ms")
            
            answer = sanitize_llm_response(answer)
            
            # Don't add source footer if no relevant info was found
            if "No tinc informació sobre aquest tema" in answer:
                return answer
            return f"{answer}\n\n*Font: Cerca semàntica en documents castellers*"
            
        except Exception as e:
            print(f"[RAG] Error: {e}")
            return f"Error en la cerca semàntica: {e}"

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
            print(f"[TIMING] create_sql_query(): {sql_gen_time:.2f}ms")
            
            # Execute the query
            sql_exec_start = datetime.now()
            try:
                raw_rows = self.execute_sql_query(sql_query, params)
            except NoResultsFoundError:
                self.table_data = None
                return NO_RESULTS_MESSAGE
            except SQLExecutionError as e:
                self.table_data = None
                return e.message
            sql_exec_time = (datetime.now() - sql_exec_start).total_seconds() * 1000
            print(f"[TIMING] execute_sql_query(): {sql_exec_time:.2f}ms")
            
            # Organize results based on query type (V2 approach)
            organize_start = datetime.now()
            rows = self.organize_sql_results(raw_rows, sql_query_type)
            organize_time = (datetime.now() - organize_start).total_seconds() * 1000
            print(f"[TIMING] organize_results(): {organize_time:.2f}ms")

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
                
                # Convert top_results to table string for LLM (only top 10, no IDs)
                if top_results_for_llm:
                    header = list(top_results_for_llm[0].keys())
                    table_str = "\n".join([" | ".join(header)] + [" | ".join(str(v) for v in r.values()) for r in top_results_for_llm[:llm_context_limit]])
                    print(f"[SQL Results for LLM] (showing {min(len(top_results_for_llm), llm_context_limit)}/{len(top_results_for_llm)} rows from top_results table)\n", table_str)
                else:
                    table_str = "No results found."
                
                # Store multiple tables for frontend display
                self.table_data = self._format_custom_tables_for_frontend(rows)
            else:
                # Convert rows to a friendly table (limited for LLM context)
                header = list(rows[0].keys()) if rows else []
                table_str = "\n".join([" | ".join(header)] + [" | ".join(str(v) for v in r.values()) for r in rows[:llm_context_limit]]) if rows else "No results found."
                print(f"[SQL Results for LLM] (showing {min(len(rows), llm_context_limit)}/{len(rows)} rows)\n", table_str)
                
                # Store table data for frontend display (full results up to SQL_RESULT_LIMIT)
                # Create a nice table structure with proper column titles
                self.table_data = self._format_table_for_frontend(rows[:SQL_RESULT_LIMIT], sql_query_type)
            
            # Use structured prompt with system/developer/user separation (including previous context)
            structured_prompt = get_sql_summary_prompt(
                sql_query_type, 
                self.question, 
                table_str,
                previous_question=self.previous_question,
                previous_response=self.previous_response,
                previous_context_max_chars=PREVIOUS_CONTEXT_MAX_CHARS
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
                print(f"[TIMING] handle_sql() LLM summary call: {sql_llm_time:.2f}ms")
                
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


    def process_question(self, question: str) -> str:

        # Step 1: Decide route
        route_start = datetime.now()
        response = self.decide_route(question)
        route_time = (datetime.now() - route_start).total_seconds() * 1000
        print(f"[TIMING] decide_route(): {route_time:.2f}ms")
        
        # Store response for later access (e.g., getting route_used)
        self.response = response
        print(f"[Router] Ruta escollida: {response.tools}, {response.sql_query_type}")
        
        # Step 2: Handle based on route
        handler_start = datetime.now()
        if response.tools == "direct":
            result = self.handle_direct()
        elif response.tools == "rag":
            result = self.handle_rag()
        elif response.tools == "sql":
            result = self.handle_sql()
        # elif response.tools == "hybrid":
        #     result = self.handle_hybrid()
        else:
            result = "No estic segur de com respondre això, però ho estic intentant!"
        
        handler_time = (datetime.now() - handler_start).total_seconds() * 1000
        print(f"[TIMING] handle_{response.tools}(): {handler_time:.2f}ms")
        
        return result

# ---- Agent principal ----
def xiquet_agent(
    question: str, 
    previous_question: str = None, 
    previous_response: str = None,
    previous_route: str = None,
    previous_sql_query_type: str = None,
    previous_entities: dict = None
) -> str:

    xiquet = Xiquet(
        previous_question=previous_question,
        previous_response=previous_response,
        previous_route=previous_route,
        previous_sql_query_type=previous_sql_query_type,
        previous_entities=previous_entities
    )
    return xiquet.process_question(question)

# ---- Exemple d'ús ----
if __name__ == "__main__":
    xiquet = Xiquet()
    while True:
        q = input("Pregunta (en català, 'sortir' per acabar): ")
        if q.lower() == "sortir":
            break
        print("Xiquet:", xiquet.process_question(q))
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
#             rag_results = search_query_supabase(self.question, k=3)
#             rag_search_time = (datetime.now() - rag_search_start).total_seconds() * 1000
#             print(f"[TIMING] hybrid RAG search_query_supabase(): {rag_search_time:.2f}ms")
            
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
