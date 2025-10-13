"""
agent.py
Agent "Xiquet": respon preguntes sobre castells usant LLM + RAG + SQL.
"""

import json
import os
from typing import Dict, Any, List, Optional
from langdetect import detect
from rag_index import search_query
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
from llm_sql import LLMSQLGenerator, get_sql_summary_prompt
from llm_function import llm_call, list_available_providers, list_provider_models

# Load environment variables from .env file
load_dotenv()

# ---- Configuració ----
DB_PATH = "database.db"
MODEL_NAME = "openai:gpt-4o"  

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


# Database path
DB_PATH = "database.db"


# ---- Xiquet Class ----
class Xiquet:
    def __init__(self):
        self.question = ""
        self.response = None
        self.colles_castelleres = []
        self.castells = []  # This will now be a list of Castell objects
        self.anys = []
        self.llocs = []
        self.diades = []
        self.editions = []
        self.jornades = []
        self.positions = []
        self.sql_generator = LLMSQLGenerator()
    
    def abans_de_res(self, question: str) -> Optional[FirstCallResponseFormat]:
        """
        Analitza la pregunta abans de processar-la i retorna una resposta directa si es compleixen certes condicions.
        """
        # Analitza si la pregunta no és en català
        try:
            lang = detect(question)
            if lang != "ca":
                if lang in language_names:
                    response = f"Ho sento, no parlo {language_names[lang]}. Només puc respondre preguntes en català i relacionades amb el món casteller. Però sempre es bon moment per apendre a parlar català!"
                else:
                    response = "Ho sento, només puc respondre preguntes en català i relacionades amb el món casteller. Però sempre es bon moment per apendre a parlar català!"
                
                return FirstCallResponseFormat(
                    tools="direct",
                    direct_response=response,
                    colla=[], castells=[], anys=[], llocs=[], diades=[]
                )
        except Exception:
            # Si no es pot detectar l'idioma, continua processant
            pass
        
        # Analitza si la pregunta té més de 30 tokens
        # Utilitzem una aproximació simple: dividir per espais i puntuació
        import re
        tokens = re.findall(r'\b\w+\b', question)
        if len(tokens) > 30:
            return FirstCallResponseFormat(
                tools="direct",
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
        self.question = question
        
        # Primer analitza si cal donar una resposta directa
        direct_response = self.abans_de_res(question)
        if direct_response is not None:
            return direct_response
        
        # Extract entities from question (heuristics)
        self.colles_castelleres = get_colles_castelleres_subset(question)
        self.castells = get_castells_with_status_subset(question)
        self.anys = get_anys_subset(question)
        self.llocs = get_llocs_subset(question)
        self.diades = get_diades_subset(question)

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
        - **Any:** Any concret d'una actuació o d'una referència temporal.  
        Possibles opcions: {self.anys}
        \n"""
        
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
        Per exemple, si la pregunta parla dels "castellers de Sabadell", no has d'extreure "Sabadell" com a lloc ni "Diada dels castellers de Sabadell" com a diada a nose que ho estigui parlant explicitament. 


        ### 2. Elecció de l'eina adequada
        Decideix quina eina utilitzar per respondre la pregunta: sql, rag, hybrid o direct.

        - **"sql"**: si la pregunta requereix **informació quantitativa o estadística** que es pot obtenir amb una consulta a la base de dades.

        - **"rag"**: si la pregunta requereix **coneixement textual o descriptiu**, com història, valors, fets generals o informació no numèrica.  

        - **"hybrid"**: si la pregunta combina informació **estadística i contextual** o si un context textual pot ajudar a interpretar millor la dada SQL.
            En aquest cas indica també el tipus de query SQL que has utilitzat.

        - **"direct"**: si la pregunta és **molt general, bàsica o no relacionada amb castells**.  

        ### 3. Format de resposta
        Respon **exclusivament** en format JSON segons l'estructura següent:

        {FirstCallResponseFormat.model_json_schema()}

        Regles:
        - El camp `"tools"` ha de ser exactament un d'aquests valors: `"direct"`, `"rag"`, `"sql"`, `"hybrid"`.
        - Si `"tools"` és `"sql"` o `"hybrid"`, **NO** triïs el camp `"sql_query_type"` ara - es farà en un segon pas.
        - Si `"tools"` és `"direct"`, **afegeix també una resposta breu i clara** al camp `"direct_response"`.
        - Assegura't que **totes les llistes** (`colla`, `castells`, `anys`, `llocs`, `diades`, `edicions`, `jornades`, `posicions`) contenen només elements exactes o són buides.

        Ara analitza la pregunta i genera la sortida amb el format indicat.
        """

        response = llm_call(route_prompt, model=MODEL_NAME, response_format=FirstCallResponseFormat)
        self.response = response
        
        # If SQL or hybrid, determine the specific query type
        if response.tools in ["sql", "hybrid"]:
            # Option 1: Fast fuzzy matching (current default)
            response.sql_query_type = self._determine_sql_query_type(question, response)
            
            # Option 2: LLM-based classification (uncomment to use)
            # response.sql_query_type = self._determine_sql_query_type_llm_call(question, response)

        # Validate tool
        if response.tools not in ["direct", "rag", "sql", "hybrid"]:
            return FirstCallResponseFormat(
                tools="direct",
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

        # Validate colla (only if not empty)
        if response.colla:
            valid_colles = get_all_colla_options()
            for colla in response.colla:
                if colla not in valid_colles:
                    print(f"Error: Colla {colla} no és vàlida")
                    response.colla.remove(colla) 
        
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

    def _determine_sql_query_type(self, question: str, response: FirstCallResponseFormat) -> str:
        """Determine the specific SQL query type using fuzzy matching with similarity scores"""
        from difflib import SequenceMatcher
        
        question_lower = question.lower()
        
        # Define query types with their characteristic keywords
        query_patterns = {
            "millor_diada": ["millor diada", "millor actuació", "millor actuacio", "millor actuacion", "millor actuacions", "quina diada", "quina actuació", "millor actuacions"],
            "millor_castell": ["millor castell", "millor torre", "millor construcció", "millor construccio", "millor torre", "millor construcció"],
            "castell_historia": ["quants", "quant", "vegades", "cops", "història", "historia", "ha fet", "han fet", "quantes vegades"],
            "location_actuations": ["quin any", "quin lloc", "millor any", "millor lloc", "quina ciutat", "quina població", "millor ciutat"],
            "first_castell": ["primer", "primera", "primer cop", "primera vegada", "primer castell", "primera vegada"],
            "castell_statistics": ["estadístiques", "estadisticas", "estadística", "estadistica", "estadístiques castell"],
            "year_summary": ["resum", "resum temporada", "activitat", "com va ser la temporada", "com va ser l'any", "resum any", "com va anar la temporada", "com va anar l'any", 'que van fer a la temporada', 'que van fer a l\'any'],
            "concurs_ranking": ["concurs", "concursos", "classificació concurs", "classificacio concurs", "guanyador concurs", "guanyadora concurs", "quina classificació", "quin concurs", "concurs de castells"],
            "concurs_history": ["història concurs", "historia concurs", "concursos celebrats", "història dels concursos"]
        }
        
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
        
        # Threshold for accepting a match (adjust as needed)
        threshold = 0.3
        
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
            "castells": self.castells,  # This is now a list of Castell objects
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
            lambda prompt: llm_call(prompt, model=MODEL_NAME)
        )

    def execute_sql_query(self, sql_query: str, params: dict) -> list:
        """
        Execute a SQL query safely and return the results.
        """
        return self.sql_generator.execute_sql_query(sql_query, params)

    def handle_rag(self) -> str:
        """
        Use RAG to answer the question by searching through embeddings.
        """
        try:
            # Search for relevant documents
            results = search_query(self.question, k=10)
            
            if not results:
                return "No he trobat informació rellevant per respondre la teva pregunta."
            
            # Prepare context from search results
            context_parts = []
            for i, (doc_info, score) in enumerate(results, 1):
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
                
                context_str = f"[Resultat {i}] " + "; ".join(context_info) + f"\n{text}"
                context_parts.append(context_str)
            
            context = "\n\n".join(context_parts)
            
            # Generate answer using RAG context
            rag_prompt = f"""
            Ets un expert en el món casteller. Utilitza la informació següent per respondre la pregunta de l'usuari.

            ### Pregunta de l'usuari:
            {self.question}

            ### Informació rellevant trobada:
            {context}

            ### Instruccions:
            1. Respon la pregunta utilitzant la informació proporcionada si es rellevant a la pregunta.
            2. Si hi ha informació sobre colles específiques, dates o llocs, inclou-la en la resposta.
            3. Completa la resposta amb informació contextual relevant si cal.

            """
            
            answer = llm_call(rag_prompt, model=MODEL_NAME)
            return f"{answer}\n\n*Font: Cerca semàntica en documents castellers*"
            
        except Exception as e:
            return f"Error en la cerca semàntica: {e}"

    def handle_sql(self) -> str:
        """
        Generate and execute a SQL query using the LLM,
        safely retrieve data from the SQLite DB, and explain results in Catalan.
        """
        try:
            # Generate SQL query and parameters
            sql_query, params = self.create_sql_query()
            
            # Execute the query
            rows = self.execute_sql_query(sql_query, params)

            # If no results
            if not rows:
                return f"No he trobat resultats per la teva consulta.\nConsulta SQL utilitzada:\n{sql_query}"

            # Summarize results into a readable answer
            # Convert rows to a friendly table
            header = rows[0].keys()
            table_str = "\n".join([" | ".join(header)] + [" | ".join(str(v) for v in r) for r in rows[:10]])
            print("[SQL Results]\n", table_str)
            
            # Get the SQL query type for specific prompt
            sql_query_type = getattr(self.response, 'sql_query_type', 'custom')
            
            # Use specific prompt for the query type
            summary_prompt = get_sql_summary_prompt(sql_query_type, self.question, table_str)

            try:
                final_answer = llm_call(summary_prompt, model=MODEL_NAME)
            except Exception as e:
                return f"He pogut obtenir dades, però no generar una explicació: {e}\nConsulta SQL:\n{sql_query}"

            # Return the final answer with provenance
            return f"{final_answer}\n```"
            
        except Exception as e:
            return str(e)


    def handle_hybrid(self) -> str:
        """
        Hybrid approach: Combine SQL query results with RAG context for comprehensive answers.
        """
        try:
            # Step 1: Try to get SQL results first
            sql_query, params = self.create_sql_query()
            sql_rows = self.execute_sql_query(sql_query, params)
            
            # Step 2: Get RAG context
            rag_results = search_query(self.question, k=3)
            
            # Step 3: Prepare SQL context
            sql_context = ""
            if sql_rows:
                header = sql_rows[0].keys()
                table_str = "\n".join([" | ".join(header)] + [" | ".join(str(v) for v in r) for r in sql_rows[:5]])
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
            
            # Step 5: Generate comprehensive answer using both sources
            hybrid_prompt = f"""
            Ets un expert en el món casteller. Utilitza tant les dades estructurades de la base de dades com la informació contextual dels documents per respondre la pregunta de l'usuari de manera completa i precisa.

            ### Pregunta de l'usuari:
            {self.question}

            {sql_context}

            {rag_context}

            ### Instruccions:
            1. **Combina** la informació de les dues fonts per donar una resposta completa.
            2. Si les dades SQL proporcionen informació específica (dates, nombres, estadístiques), utilitza-la com a base.
            3. Si la informació contextual dels documents proporciona context històric, explicacions o detalls addicionals, integra-la per enriquir la resposta.
            4. No donis valoracions ni opinions.
            """
            
            answer = llm_call(hybrid_prompt, model=MODEL_NAME)
            
            # Step 6: Add provenance information
            provenance = f"""
            *Fonts utilitzades:*
            - Dades estructurades de la base de dades (SQL)
            - Cerca semàntica en documents castellers (RAG)
            """
            
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
        response = self.decide_route(question)
        print(f"[Router] Ruta escollida: {response.tools}, {response.sql_query_type}")
        
        if response.tools == "direct":
            return self.handle_direct()
        elif response.tools == "rag":
            return self.handle_rag()
        elif response.tools == "sql":
            return self.handle_sql()
        elif response.tools == "hybrid":
            return self.handle_hybrid()
        else:
            return "No estic segur de com respondre això, però ho estic intentant!"

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
