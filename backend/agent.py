"""
agent.py
Agent "Xiquet": respon preguntes sobre castells usant LLM + RAG + SQL.
"""

import json
import os
import unicodedata
from typing import Dict, Any, List, Optional
from langdetect import detect
from database_pipeline.rag_index_supabase import search_query_supabase
from dotenv import load_dotenv
from utility_functions import (
    language_names,
    get_colles_castelleres_subset,
    get_castells_subset,
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
from llm_sql import LLMSQLGenerator, get_sql_summary_prompt, StructuredPrompt, NoResultsFoundError, NO_RESULTS_MESSAGE, SQL_RESULT_LIMIT, LLM_CONTEXT_LIMIT
from llm_function import llm_call, list_available_providers, list_provider_models, is_guardrail_violation
from util_dics import SQL_QUERY_PATTERNS, IS_SQL_QUERY_PATTERNS, COLUMN_MAPPINGS, TITLE_MAPPINGS
from difflib import SequenceMatcher
import re


def sanitize_llm_response(response: str) -> str:
    """
    Post-process LLM response to remove unwanted formatting like tables.
    """
    if not response:
        return response
    
    lines = response.split('\n')
    clean_lines = []
    
    for line in lines:
        # Detect table rows: lines with 2+ pipe characters (e.g., "| col1 | col2 |")
        pipe_count = line.count('|')
        
        if pipe_count >= 2:
            # This is likely a table row - skip it
            print(f"[DEBUG] Removing table line: {line[:80]}...")
            continue
        
        # Also detect markdown table separator lines (e.g., "|---|---|")
        if re.match(r'^[\s|:-]+$', line) and '|' in line:
            print(f"[DEBUG] Removing table separator: {line}")
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

# ---- Configuració ----
# MODEL_NAME = "sambanova:gpt-oss-120b"  

MODEL_NAME = "sambanova:gpt-oss-120b" 
MODEL_NAME_ROUTE = "sambanova:gpt-oss-120b"
# MODEL_NAME_RESPONSE = "sambanova:Meta-Llama-3.1-8B-Instruct"
# MODEL_NAME_RESPONSE = "sambanova:Qwen3-235B"
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




# ---- Xiquet Class ----
class Xiquet:
    def __init__(self):
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
        # Table data to be sent to frontend (avoids LLM generating tables)
        self.table_data = None
        self.sql_generator = LLMSQLGenerator()
    
    def abans_de_res(self, question: str) -> Optional[FirstCallResponseFormat]:
        """
        Analitza la pregunta abans de processar-la i retorna una resposta directa si es compleixen certes condicions.
        """
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
        
        # 2. Analitza si la pregunta no és en català/espanyol/portuguès
        try:
            lang = detect(question)
            if lang not in ["ca", "es", 'pt']:
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
        import re
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

    def decide_route(self, question: str) -> FirstCallResponseFormat:
        """
        Decideix la ruta:
          - direct
          - rag
          - sql
          - hybrid
        """
        from datetime import datetime
        
        self.question = question
        
        # Primer analitza si cal donar una resposta directa
        precheck_start = datetime.now()
        direct_response = self.abans_de_res(question)
        precheck_time = (datetime.now() - precheck_start).total_seconds() * 1000
        if precheck_time > 1:
            print(f"[TIMING] abans_de_res(): {precheck_time:.2f}ms")
        
        if direct_response is not None:
            return direct_response
        
        # Extract entities from question (heuristics)
        entity_start = datetime.now()
        self.colles_castelleres = get_colles_castelleres_subset(question)
        self.castells = get_castells_with_status_subset(question)
        self.anys = get_anys_subset(question)
        self.llocs = get_llocs_subset(question)
        self.diades = get_diades_subset(question)
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
        
        if self.anys:
            entities_section += f"""
        - **Any:** Any concret d'una actuació o d'una referència temporal (per exemple, "2024", "2025", etc.)  
        \n"""
        #Possibles opcions: {self.anys}
        
        if self.llocs:
            entities_section += f"""
        - **Lloc:** Ciutat o població de certa actuació.  
        Possibles opcions: {self.llocs}
        \n"""
        
        if self.diades:
            entities_section += f"""
        - **Diada:** Nom de la diada o jornada castellera.  
        Possibles opcions: {self.diades}
        \n"""

        # Add concurs-related entities if the question mentions concurs
        if "concurs" in question.lower() or "concursos" in question.lower():
            entities_section += f""" Si la pregunta és sobre un concurs de castells, afegeix les següents entitats si apareixen:
        - **Edició de concurs:** Edició del concurs de castells (I, II, III, IV,...).
        - **Jornada:** Tipus de jornada del concurs ('Jornada Diumenge Tarragona', 'Jornada Dissabte Tarragona', 'Jornada Torredembarra').
        - **Posició:** Posició en la classificació del concurs (1, 2, 3, 4, ...).
        \n"""

        # Demana al LLM classificar
        llm_start = datetime.now()
        route_prompt = f"""
        Ets **el Xiquet**, un assistent expert en el món casteller. 
        La teva tasca és **analitzar la següent pregunta** sobre castells:  
        > "{question}"

        Per respondre correctament, has de seguir aquests passos de forma estricta:

        ### 1. Identificació d'entitats
        Analitza la pregunta i identifica, si n'hi ha, els següents tipus d'elements.  
        L'objectiu és detectar referències i mapar-les exactament a l'element correcte dins la seva llista corresponent.  

        Elements a extreure:{entities_section}

        IMPORTANT: No confonguis el nom de les colles amb el fet de que estigui parlant de una localitat o diada. 
        Per exemple, si la pregunta parla dels "castellers de Sabadell", no has d'extreure "Sabadell" com a lloc ni "Diada dels castellers de Sabadell" com a diada a nose que la pregunta faci referència a aquella especifica diada. 


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

        Ara analitza la pregunta i genera la sortida amb el format indicat.
        """

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
        skip_sql_check = False
        if response.tools == "rag" or response.tools == "direct":
            if response.tools == "direct":
                threshold = 0.85
            else:
                threshold = 0.8
            # Only attempt SQL determination if entities exist
            if response.colla or response.castells or response.anys or response.llocs or response.diades:
                response.sql_query_type = self._determine_sql_query_type(question, response, IS_SQL_QUERY_PATTERNS, threshold=threshold)
                if response.sql_query_type != "custom":
                    response.tools = "sql"
                    skip_sql_check = True

        
        # If SQL or hybrid, determine the specific query type
        if response.tools in ["sql", "hybrid"] and not skip_sql_check:
            # Option 1: Fast fuzzy matching (current default)
            response.sql_query_type = self._determine_sql_query_type(question, response, SQL_QUERY_PATTERNS)
            
            # Option 2: LLM-based classification (uncomment to use)
            # response.sql_query_type = self._determine_sql_query_type_llm_call(question, response)
        sql_type_time = (datetime.now() - sql_type_start).total_seconds() * 1000
        print(f"[TIMING] SQL query type determination: {sql_type_time:.2f}ms")

        # Validate tool
        if response.tools not in ["direct", "rag", "sql", "hybrid"]:
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
            if response.sql_query_type not in ["millor_diada", "millor_castell", "castell_historia", "location_actuations", "first_castell", "castell_statistics", "year_summary", "concurs_ranking", "concurs_history", "custom"]:
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
            for any in response.anys:
                if any not in valid_anys:
                    print(f"Error: Any {any} no és vàlid")
                    response.anys.remove(any)

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

        if DEBUG:
            print(f"castells: {response.castells}")
            print(f"anys: {response.anys}")
            print(f"llocs: {response.llocs}")
            print(f"diades: {response.diades}")
            print(f"colles: {response.colla}")
            print(f"editions: {response.editions}")
            print(f"jornades: {response.jornades}")
            print(f"positions: {response.positions}")
            print(f"tools: {response.tools}")
            print(f"sql_query_type: {response.sql_query_type}")

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

    def _determine_sql_query_type(self, question: str, response: FirstCallResponseFormat, query_patterns: dict = SQL_QUERY_PATTERNS, threshold: float = 0.3) -> str:
        """Determine the specific SQL query type using fuzzy matching with similarity scores"""
    
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
                max_similarity = max(max_similarity, 0.8)
            
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

    def _determine_sql_query_type_llm_call(self, question: str, response: FirstCallResponseFormat) -> str:
        """Determine the specific SQL query type using LLM call"""
        sql_query_prompt = f"""
        Ets **el Xiquet**, un assistent expert en el món casteller. 
        La teva tasca és **determinar el tipus de consulta SQL** més adequat per a la següent pregunta:

        **Pregunta:** {question}

        **Opcions de queries predeterminades disponibles:**
        1. **"millor_diada"** - Per preguntes sobre la millor diada/actuació (d'una colla, any o lloc)
           Exemples: "Quin va ser la millor actuació dels Castellers de Sabadell l'any 2012?"
        2. **"millor_castell"** - Per preguntes sobre el millor castell (d'una colla, any, lloc o diada)
           Exemples: "Quin va ser el millor castell dels Minyons de Terrassa la temporada 2023?"
        3. **"castell_historia"** - Per preguntes sobre quants castells d'un tipus (per colla, any, lloc o diada)
           Exemples: "Quants 3de10 han fet els Castellers de Vilafranca?"
        4. **"location_actuations"** - Per preguntes sobre quin any o quin lloc s'ha fet la millor actuació (d'una colla, any o lloc)
           Exemples: "Quin any va tenir la millor actuació dels Castellers de Vilafranca? Quin lloc va tenir la millor actuació l'any 2023?"
        5. **"first_castell"** - Per preguntes sobre quin any s'ha fet el primer castell (castell requerit- per colla, lloc o diada)
           Exemples: "Quin any es va descarregar el primer 3d10fm de la història?"
        6. **"castell_statistics"** - Per preguntes sobre estadístiques completes d'un castell específic (castell requerit)
           Exemples: "Quants cops s'ha descarregat el 3d10fm? Quantes colles l'han aconseguit?"
        7. **"year_summary"** - Per preguntes sobre resum d'activitat castellera d'un any específic (filtrable per colla i/o lloc)
           Exemples: "Com va ser la temporada 2023? Quin va ser el resum de l'any 2022 per als Castellers de Vilafranca?"
        8. **"concurs_ranking"** - Per preguntes sobre el concurs de castells
           Exemples: "Quina va ser la classificació del Concurs de Castells XXIV? Qui va guanyar el concurs de dissabte?"

        **Si cap de les opcions anteriors s'adapta o s'assembla a la pregunta**, tria "custom" i el sistema generarà una query personalitzada.

        Respon **només** amb el nom del tipus de consulta (ex: "millor_diada", "concurs_ranking", "custom").
        """
        
        try:
            result = llm_call(sql_query_prompt, model=MODEL_NAME)
            # Clean the response and validate
            query_type = result.strip().lower()
            valid_types = ["millor_diada", "millor_castell", "castell_historia", "location_actuations", 
                          "first_castell", "castell_statistics", "year_summary", "concurs_ranking", "concurs_history", "custom"]
            
            if query_type in valid_types:
                return query_type
            else:
                print(f"Warning: Invalid SQL query type '{query_type}', defaulting to 'custom'")
                return "custom"
        except Exception as e:
            print(f"Error in LLM SQL query type determination: {e}")
            return "custom"

    def handle_direct(self) -> str:
        return self.response.direct_response

    def create_sql_query(self) -> tuple[str, dict]:
        """
        Generate a SQL query and parameters using the predefined template system or custom generation.
        Returns (sql_query, params) tuple.
        """
        # Build entities dictionary
        entities = {
            "colla": self.colles_castelleres,
            "castells": self.castells,
            "anys": self.anys,
            "llocs": self.llocs,
            "diades": self.diades,
            "editions": self.editions,
            "jornades": self.jornades,
            "positions": self.positions
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
        """
        Execute a SQL query safely and return the results.
        """
        return self.sql_generator.execute_sql_query(sql_query, params)

    def _rerank_results(self, question: str, results: list, top_k: int = 5) -> list:
        """
        Re-rank RAG results. 
        Cross-encoder disabled by default as it adds 17+ seconds for minimal benefit with few results.
        The vector similarity from pgvector is usually sufficient.
        """
        if not results:
            return results
        
        # Simply return top_k results sorted by original similarity score
        # This is already done by pgvector, but ensure we limit to top_k
        return results[:top_k]

    def handle_rag(self) -> str:
        """
        Use RAG to answer the question by searching through embeddings.
        Includes: relevance filtering, cross-encoder re-ranking, and smart prompting.
        """
        from datetime import datetime
        
        # Configuration
        MIN_SIMILARITY_THRESHOLD = 0.25  # Minimum similarity score to consider
        INITIAL_RETRIEVAL_K = 15  # Retrieve more candidates for re-ranking
        FINAL_TOP_K = 5  # Final number of results after re-ranking
        
        try:
            # Step 1: Initial retrieval (retrieve more candidates for re-ranking)
            rag_search_start = datetime.now()
            results = search_query_supabase(self.question, k=INITIAL_RETRIEVAL_K)
            rag_search_time = (datetime.now() - rag_search_start).total_seconds() * 1000
            print(f"[TIMING] RAG search_query_supabase(): {rag_search_time:.2f}ms (retrieved {len(results)} candidates)")
            
            if not results:
                return "No he trobat informació rellevant per respondre la teva pregunta."
            
            # Step 2: Relevance score filtering (remove low-quality results)
            filtered_results = [(doc, score) for doc, score in results if score >= MIN_SIMILARITY_THRESHOLD]
            print(f"[RAG] Filtered from {len(results)} to {len(filtered_results)} results (threshold: {MIN_SIMILARITY_THRESHOLD})")
            
            if not filtered_results:
                return "No he trobat informació prou rellevant per respondre la teva pregunta. Prova a reformular la pregunta."
            
            # Step 3: Re-rank with cross-encoder for better semantic matching
            reranked_results = self._rerank_results(self.question, filtered_results, top_k=FINAL_TOP_K)
            print(f"[RAG] Re-ranked to top {len(reranked_results)} results")
            
            # Step 4: Build context from re-ranked results (simple text concatenation)
            context_parts = []
            for i, (doc_info, score) in enumerate(reranked_results, 1):
                text = doc_info.get("text", "")
                context_parts.append(f"[Document {i}]\n{text}")
            
            context = "\n\n".join(context_parts)
            
            # Step 5: Generate answer with improved prompt
            rag_system = """Ets un expert casteller amb criteri tècnic i rigor històric.
Sempre respons exclusivament en català.
Segueixes estrictament les instruccions de format i sortida."""
            
            rag_developer = """INSTRUCCIONS ESTRICTES (OBLIGATÒRIES):

PROHIBIT:
- Afegir taules
- Afegir llistes amb guions o punts
- Donar opinions o valoracions personals

FORMAT DE SORTIDA:
- Markdown, text narratiu (paràgrafs) (NO TAULES)
- Únic ús de **negreta** per destacar fets rellevants (màxim 3-4 elements)

SOBRE LA INFORMACIÓ PROPORCIONADA:
- Utilitza la informació proporcionada si és rellevant; si no, respon amb el teu propi coneixement casteller.
- Si no tens informació suficient, digues-ho honestament i no inventis dades específiques.

Respon en 1-3 paràgrafs segons la complexitat de la pregunta."""

            rag_user = f"""Pregunta:
{self.question}

Informació trobada als documents:
{context}

Respon la pregunta de forma breu i directa. Si la informació dels documents no és rellevant, utilitza el teu coneixement casteller."""
            
            rag_llm_start = datetime.now()
            answer = llm_call(
                prompt=rag_user,
                model=MODEL_NAME_RESPONSE,
                system_message=rag_system,
                developer_message=rag_developer
            )
            rag_llm_time = (datetime.now() - rag_llm_start).total_seconds() * 1000
            print(f"[TIMING] handle_rag() LLM call: {rag_llm_time:.2f}ms")
            
            # Sanitize response to remove any tables
            answer = sanitize_llm_response(answer)
            return f"{answer}\n\n*Font: Cerca semàntica en documents castellers*"
            
        except Exception as e:
            return f"Error en la cerca semàntica: {e}"

    def _format_table_for_frontend(self, rows: list, query_type: str) -> dict:
        """
        Format SQL results as a structured table for frontend display.
        Returns a dict with 'title', 'columns' (with nice names), and 'rows'.
        Only includes columns specified for each query type.
        """
        if not rows:
            return None
        
        # ============================================================
        # COLUMNS TO SHOW PER QUERY TYPE
        # Define which columns to display for each query type (in order)
        # Use the database column names here
        # ============================================================
        columns_per_query_type = {
            'millor_diada': ['ranking', 'event_name', 'event_date', 'colla_name', 'event_city', 'castells_fets'],
            'millor_castell': ['castell_name', 'event_name', 'event_date', 'colla_name', 'event_city', 'status'],
            'castell_historia': ['castell_name', 'status', 'count_occurrences', 'colla_name', 'first_date', 'last_date', 'cities'],
            'location_actuations': ['event_name', 'date', 'city', 'colla_name', 'castells_fets'],
            'first_castell': ['castell_name', 'status','event_name', 'date', 'colla_name', 'city'],
            'castell_statistics': ['castell_name', 'cops_descarregat', 'cops_carregat', 'cops_intent_desmuntat', 'cops_intent', 'primera_data_descarregat', 'primera_data_carregat', 'colles_descarregat', 'colles_carregat', 'colles_intentat',  'primeres_colles_descarregat', 'primeres_colles_carregat', 'primeres_colles_intentat',],
            'concurs_ranking': ['colla_name', 'position', 'total_points', 'jornada', 'primera_ronda', 'segona_ronda', 'tercera_ronda', 'quarta_ronda', ' cinquena_ronda'],
            'concurs_history': ['any', 'jornada', 'colles_participants', 'colla_guanyadora', 'punts_guanyador', 'castells_r1_descarregats', 'castells_r2_descarregats', 'castells_r3_descarregats', 'castells_r4_descarregats', 'castells_r5_descarregats'],
            'year_summary': ['colla_name', 'num_actuacions', 'num_castells', 'castells_descarregats', 'castells_carregats', 'castells_intent_desmuntat', 'castells_intent'],
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
        
        # Format rows with only selected columns
        formatted_rows = []
        for row in rows:
            formatted_row = [str(row.get(col, '-')) if row.get(col) is not None else '-' for col in selected_columns]
            formatted_rows.append(formatted_row)
        
        return {
            'title': TITLE_MAPPINGS.get(query_type, 'Resultats'),
            'columns': nice_headers,
            'rows': formatted_rows
        }

    def handle_sql(self) -> str:
        """
        Generate and execute a SQL query using the LLM,
        safely retrieve data from the SQLite DB, and explain results in Catalan.
        """
        from datetime import datetime
        
        try:
            # Generate SQL query and parameters
            sql_gen_start = datetime.now()
            sql_query, params = self.create_sql_query()
            sql_gen_time = (datetime.now() - sql_gen_start).total_seconds() * 1000
            print(f"[TIMING] create_sql_query(): {sql_gen_time:.2f}ms")
            
            # Execute the query
            sql_exec_start = datetime.now()
            try:
                rows = self.execute_sql_query(sql_query, params)
            except NoResultsFoundError:
                self.table_data = None
                return NO_RESULTS_MESSAGE
            sql_exec_time = (datetime.now() - sql_exec_start).total_seconds() * 1000
            print(f"[TIMING] execute_sql_query(): {sql_exec_time:.2f}ms")

            # Summarize results into a readable answer
            # Convert rows to a friendly table (limited for LLM context)
            header = list(rows[0].keys())
            table_str = "\n".join([" | ".join(header)] + [" | ".join(str(v) for v in r.values()) for r in rows[:LLM_CONTEXT_LIMIT]])
            print("[SQL Results for LLM]\n", table_str)
            
            # Get the SQL query type for specific prompt
            sql_query_type = getattr(self.response, 'sql_query_type', 'custom')
            
            # Store table data for frontend display (full results up to SQL_RESULT_LIMIT)
            # Create a nice table structure with proper column titles
            self.table_data = self._format_table_for_frontend(rows[:SQL_RESULT_LIMIT], sql_query_type)
            
            # Use structured prompt with system/developer/user separation
            structured_prompt = get_sql_summary_prompt(sql_query_type, self.question, table_str)

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
            
        except Exception as e:
            return str(e)


    def handle_hybrid(self) -> str:
        """
        Hybrid approach: Combine SQL query results with RAG context for comprehensive answers.
        """
        from datetime import datetime
        
        try:
            # Step 1: Try to get SQL results first
            sql_gen_start = datetime.now()
            sql_query, params = self.create_sql_query()
            sql_gen_time = (datetime.now() - sql_gen_start).total_seconds() * 1000
            print(f"[TIMING] hybrid create_sql_query(): {sql_gen_time:.2f}ms")
            
            sql_exec_start = datetime.now()
            try:
                sql_rows = self.execute_sql_query(sql_query, params)
            except NoResultsFoundError:
                sql_rows = []  # Continue with RAG context only
            sql_exec_time = (datetime.now() - sql_exec_start).total_seconds() * 1000
            print(f"[TIMING] hybrid execute_sql_query(): {sql_exec_time:.2f}ms")
            
            # Step 2: Get RAG context
            rag_search_start = datetime.now()
            rag_results = search_query_supabase(self.question, k=3)
            rag_search_time = (datetime.now() - rag_search_start).total_seconds() * 1000
            print(f"[TIMING] hybrid RAG search_query_supabase(): {rag_search_time:.2f}ms")
            
            # Step 3: Prepare SQL context
            sql_context = ""
            if sql_rows:
                header = list(sql_rows[0].keys())
                table_str = "\n".join([" | ".join(header)] + [" | ".join(str(v) for v in r.values()) for r in sql_rows[:5]])
                sql_context = f"""
                    ### Dades estructurades de la base de dades:
                    {table_str}
                    """
            else:
                sql_context = ""
            
            # Step 4: Prepare RAG context
            rag_context = ""
            if rag_results:
                rag_parts = []
                for i, (doc_info, score) in enumerate(rag_results, 1):
                    meta = doc_info.get("meta", {})
                    text = doc_info.get("text", "")
                    
                    # Add metadata context
                    context_info = []
                    if meta.get("colla_name"):
                        context_info.append(f"Colla: {meta['colla_name']}")
                    if meta.get("date"):
                        context_info.append(f"Data: {meta['date']}")
                    if meta.get("place"):
                        context_info.append(f"Lloc: {meta['place']}")
                    if meta.get("category"):
                        context_info.append(f"Categoria: {meta['category']}")
                    
                    context_str = f"[Document {i}] " + "; ".join(context_info) + f"\n{text}"
                    rag_parts.append(context_str)
                
                rag_context = f"""
                    ### Informació contextual dels documents:
                    {chr(10).join(rag_parts)}
                    """
            else:
                rag_context = ""
            
            # Step 5: Generate comprehensive answer using both sources with structured prompts
            hybrid_system = """Ets un expert casteller amb criteri tècnic i rigor històric.
Sempre respons exclusivament en català.
Segueixes estrictament les instruccions de format i sortida."""
            
            hybrid_developer = """INSTRUCCIONS ESTRICTES (OBLIGATÒRIES):

PROHIBIT:
- Afegir taules
- Afegir llistes amb guions o punts
- Repetir dades literals
- Mencionar punts o puntuacions numèriques
- Donar opinions o valoracions personals

FORMAT DE SORTIDA:
- Markdown, text narratiu (paràgrafs)
- Únic ús de **negreta** per destacar fets rellevants (màxim 3-4 elements)

CONTEXT ESPECÍFIC:
- Combina la informació de les dues fonts (SQL i RAG)
- Prioritza dades SQL per informació específica (dates, estadístiques)
- Utilitza RAG per context històric o explicacions
- Respon en 1-2 paràgrafs màxim"""

            hybrid_user = f"""Pregunta:
{self.question}

{sql_context}

{rag_context}

Respon de forma breu i directa combinant ambdues fonts."""
            
            hybrid_llm_start = datetime.now()
            answer = llm_call(
                prompt=hybrid_user,
                model=MODEL_NAME_RESPONSE,
                system_message=hybrid_system,
                developer_message=hybrid_developer
            )
            hybrid_llm_time = (datetime.now() - hybrid_llm_start).total_seconds() * 1000
            print(f"[TIMING] handle_hybrid() LLM call: {hybrid_llm_time:.2f}ms")
            
            # Sanitize response to remove any tables
            answer = sanitize_llm_response(answer)
            
            # Step 6: Add provenance information
            provenance = "*Fonts: SQL + RAG*"
            
            return f"{answer}\n\n{provenance}"
            
        except Exception as e:
            # Fallback to RAG only if SQL fails
            try:
                print(f"[Hybrid] SQL failed, falling back to RAG: {e}")
                return self.handle_rag()
            except Exception as rag_error:
                return f"Error en l'enfocament híbrid: {e}\nError en RAG de fallback: {rag_error}"

    def process_question(self, question: str) -> str:
        """
        Process a question and return the response.
        This is the main entry point for the Xiquet agent.
        """
        from datetime import datetime
        
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
        elif response.tools == "hybrid":
            result = self.handle_hybrid()
        else:
            result = "No estic segur de com respondre això, però ho estic intentant!"
        
        handler_time = (datetime.now() - handler_start).total_seconds() * 1000
        print(f"[TIMING] handle_{response.tools}(): {handler_time:.2f}ms")
        
        return result

# ---- Agent principal ----
def xiquet_agent(question: str) -> str:
    """
    Legacy function for backward compatibility.
    Creates a new Xiquet instance and processes the question.
    """
    xiquet = Xiquet()
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
