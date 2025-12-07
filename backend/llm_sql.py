"""
LLM SQL Query Generator with Predetermined Templates

This module provides predefined SQL query templates for different types of castellers questions,
allowing for more consistent and accurate responses.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import psycopg2
import json
import os
from dotenv import load_dotenv
from utility_functions import Castell, code_to_name

DEFAULT_LIMIT = 10

load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")

# Database schema description
DB_SCHEMA_DESCRIPTION = """
Tables:
- colles(id SERIAL PRIMARY KEY, name TEXT)
- events(id SERIAL PRIMARY KEY, date TEXT, city TEXT, place TEXT)
- event_colles(id SERIAL PRIMARY KEY, event_fk INTEGER, colla_fk INTEGER)
- castells(id SERIAL PRIMARY KEY, event_colla_fk INTEGER, castell_name TEXT, status TEXT, raw_text TEXT)
- puntuacions(castell_code TEXT, punts_descarregat INTEGER, punts_carregat INTEGER, castell_code_name TEXT)
- concurs(id SERIAL PRIMARY KEY, edition TEXT, title TEXT, date TEXT, location TEXT, colla_guanyadora TEXT, num_colles INTEGER, castells_intentats INTEGER, maxim_castell TEXT, espectadors TEXT, plaça TEXT, infobox_json TEXT, paragraphs_json TEXT)
- concurs_rankings(id SERIAL PRIMARY KEY, concurs_fk INTEGER, colla_fk INTEGER, position INTEGER, colla_name TEXT, total_points INTEGER, "any" INTEGER, jornada TEXT, ronda_1_json TEXT, ronda_2_json TEXT, ronda_3_json TEXT, ronda_4_json TEXT, ronda_5_json TEXT, ronda_6_json TEXT, ronda_7_json TEXT, ronda_8_json TEXT, rondes_json TEXT)
"""

class QuestionType(Enum):
    """Types of questions that can be asked about castellers"""
    BEST_DIADA = "best_diada"           # Millor diada/actuació d'una colla
    BEST_CASTELL = "best_castell"       # Millor castell d'una colla
    CASTELL_HISTORIA = "castell_historia"  # Si una colla ha fet mai un castell específic
    LOCATION_ACTUATIONS = "location_actuations"  # Actuacions en un lloc
    YEAR_SUMMARY = "year_summary"       # Resum d'un any
    FIRST_CASTELL = "first_castell"     # Primer castell d'un tipus fet per una colla
    CASTELL_STATISTICS = "castell_statistics"  # Estadístiques d'un castell específic
    CONCURS_RANKING = "concurs_ranking"  # Consultes sobre concursos de castells
    CONCURS_HISTORY = "concurs_history"  # Història de concursos (guanyadors, estadístiques)


@dataclass
class QueryTemplate:
    """Template for a SQL query with parameters"""
    question_type: QuestionType
    sql_template: str
    required_params: List[str]
    optional_params: List[str]
    description: str
    default_limit: int = DEFAULT_LIMIT


class LLMSQLGenerator:
    """Generates SQL queries using predefined templates based on question analysis"""
    
    def __init__(self):
        self.templates = self._create_query_templates()
    
    def _create_query_templates(self) -> Dict[QuestionType, QueryTemplate]:
        """Create all predefined query templates"""
        templates = {}
        
        # # Template for best diada/actuació
        # templates[QuestionType.BEST_DIADA] = QueryTemplate(
        #     question_type=QuestionType.BEST_DIADA,
        #     sql_template="""
        #     SELECT 
        #         e.id AS event_id,
        #         e.name AS event_name,
        #         e.date AS event_date,
        #         e.place AS event_place,
        #         e.city AS event_city,
        #         co.name AS colla_name,
        #         STRING_AGG(
        #             CASE 
        #                 WHEN c.castell_name != 'Pde4' THEN c.castell_name || ' (' || c.status || ')'
        #                 ELSE NULL
        #             END, ', ' ORDER BY 
        #             CASE 
        #                 WHEN c.status = 'Descarregat' THEN COALESCE(p.punts_descarregat, 0)
        #                 WHEN c.status = 'Carregat' THEN COALESCE(p.punts_carregat, 0)
        #                 ELSE 0 
        #             END DESC) AS castells_fets,
        #         COUNT(c.id) AS num_castells,
        #         SUM(CASE 
        #             WHEN c.status = 'Descarregat' AND c.castell_name != 'Pde4' THEN COALESCE(p.punts_descarregat, 0)
        #             WHEN c.status = 'Carregat' AND c.castell_name != 'Pde4' THEN COALESCE(p.punts_carregat, 0)
        #             ELSE 0 
        #         END) AS total_punts
        #     FROM events e
        #     JOIN event_colles ec ON e.id = ec.event_fk
        #     JOIN colles co ON ec.colla_fk = co.id
        #     JOIN castells c ON ec.id = c.event_colla_fk
        #     LEFT JOIN puntuacions p ON (
        #         c.castell_name = p.castell_code_external 
        #         OR c.castell_name = p.castell_code
        #         OR c.castell_name = p.castell_code_name
        #     )
        #     WHERE 1=1
        #     {colla_filter}
        #     {year_filter}
        #     {location_filter}
        #     {diada_filter}
            
        #     GROUP BY e.id, e.name, e.date, e.place, e.city, co.name
        #     HAVING 1=1
        #     {castell_having_filter}
        #     {status_having_filter}
        #     ORDER BY total_punts DESC
        #     LIMIT %(limit)s
        #     """,
        #     required_params=[],
        #     optional_params=["colla", "year", "location", "diada", "castell", "status"],
        #     description="Find the best diada/actuació (can be filtered by colla, year, location, castell, status)",
        #     default_limit=5
        # )
        # Template for best diada/actuació
        templates[QuestionType.BEST_DIADA] = QueryTemplate(
            question_type=QuestionType.BEST_DIADA,
            sql_template="""
            WITH castells_punts AS (
                SELECT 
                    e.id AS event_id,
                    e.name AS event_name,
                    e.date AS event_date,
                    e.place AS event_place,
                    e.city AS event_city,
                    co.id AS colla_id,
                    co.name AS colla_name,
                    c.id AS castell_id,
                    c.castell_name,
                    c.status,
                    CASE 
                        WHEN c.status = 'Descarregat' THEN COALESCE(p.punts_descarregat, 0)
                        WHEN c.status = 'Carregat' THEN COALESCE(p.punts_carregat, 0)
                        ELSE 0
                    END AS punts,
                    ROW_NUMBER() OVER (
                        PARTITION BY e.id, co.id
                        ORDER BY 
                            CASE 
                                WHEN c.status = 'Descarregat' THEN COALESCE(p.punts_descarregat, 0)
                                WHEN c.status = 'Carregat' THEN COALESCE(p.punts_carregat, 0)
                                ELSE 0
                            END DESC
                    ) AS rn
                FROM events e
                JOIN event_colles ec ON e.id = ec.event_fk
                JOIN colles co ON ec.colla_fk = co.id
                JOIN castells c ON ec.id = c.event_colla_fk
                LEFT JOIN puntuacions p ON (
                    c.castell_name = p.castell_code_external 
                    OR c.castell_name = p.castell_code
                    OR c.castell_name = p.castell_code_name
                )
                WHERE 1=1
                {colla_filter}
                {year_filter}
                {location_filter}
                {diada_filter}
            )
            
            SELECT
                event_id,
                event_name,
                event_date,
                colla_name,
                event_place,
                event_city,
                STRING_AGG(
                    CASE 
                        WHEN castell_name != 'Pde4' THEN castell_name || ' (' || status || ')'
                        ELSE NULL
                    END,
                    ', '
                    ORDER BY punts DESC
                ) AS castells_fets,
                COUNT(castell_id) AS num_castells,
                SUM(CASE WHEN rn <= 4 THEN punts ELSE 0 END) AS total_punts
            FROM castells_punts
            GROUP BY event_id, event_name, event_date, event_place, event_city, colla_name
            HAVING 1=1
            {castell_having_filter}
            {status_having_filter}
            ORDER BY total_punts DESC
            LIMIT %(limit)s
            """,
            required_params=[],
            optional_params=["colla", "year", "location", "diada", "castell", "status"],
            description="Find the best diada/actuació (can be filtered by colla, year, location, castell, status), summing only the top 4 castells per event, excluding Pde4",
            default_limit=5
        )

        # Template for best castell
        templates[QuestionType.BEST_CASTELL] = QueryTemplate(
            question_type=QuestionType.BEST_CASTELL,
            sql_template="""
            SELECT 
                e.name AS event_name,
                e.date,
                e.place,
                e.city,
                co.name AS colla_name,
                c.castell_name,
                c.status,
                COALESCE(p.punts_descarregat, 0) AS punts_descarregat,
                COALESCE(p.punts_carregat, 0) AS punts_carregat
            FROM castells c
            JOIN event_colles ec ON c.event_colla_fk = ec.id
            JOIN events e ON ec.event_fk = e.id
            JOIN colles co ON ec.colla_fk = co.id
            LEFT JOIN puntuacions p ON (
                c.castell_name = p.castell_code_external 
                OR c.castell_name = p.castell_code
                OR c.castell_name = p.castell_code_name
            )
            WHERE 1=1
            {colla_filter}
            {year_filter}
            {location_filter}
            {diada_filter}
            {status_filter}
            ORDER BY 
                CASE 
                    WHEN c.status = 'Descarregat' THEN COALESCE(p.punts_descarregat, 0)
                    WHEN c.status = 'Carregat' THEN COALESCE(p.punts_carregat, 0)
                    ELSE 0 
                END DESC
            LIMIT %(limit)s
            """,
            required_params=[],
            optional_params=["colla", "year", "location", "status"],
            description="Find the best castell (can be filtered by colla, year, location, status)",
            default_limit=5
        )
        
        # Template for castell historia (quants castells ha fet una colla)
        templates[QuestionType.CASTELL_HISTORIA] = QueryTemplate(
            question_type=QuestionType.CASTELL_HISTORIA,
            sql_template="""
            SELECT 
                c.castell_name,
                c.status,
                COUNT(*) AS count_occurrences,
                co.name AS colla_name,
                MIN(e.date) AS first_date,
                MAX(e.date) AS last_date,
                STRING_AGG(DISTINCT e.city, ', ') AS cities
            FROM castells c
            JOIN event_colles ec ON c.event_colla_fk = ec.id
            JOIN events e ON ec.event_fk = e.id
            JOIN colles co ON ec.colla_fk = co.id
            LEFT JOIN puntuacions p ON (
                c.castell_name = p.castell_code_external 
                OR c.castell_name = p.castell_code
                OR c.castell_name = p.castell_code_name
            )
            WHERE 1=1
            {colla_filter}
            {castell_filter}
            {year_filter}
            {location_filter}
            {status_filter}
            GROUP BY c.castell_name, c.status, co.name, p.punts_descarregat, p.punts_carregat
            ORDER BY count_occurrences DESC, c.castell_name, c.status
            LIMIT %(limit)s
            """,
            required_params=[],
            optional_params=["colla", "castell", "year", "location", "status"],
            description="Count castell occurrences (can be filtered by colla, castell, year, location, status)",
            default_limit=10
        )
        
      
        # Template for year of best actuation (quin any s'ha fet la millor actuació)
        templates[QuestionType.LOCATION_ACTUATIONS] = QueryTemplate(
            question_type=QuestionType.LOCATION_ACTUATIONS,
            sql_template="""
            SELECT 
                EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) AS year,
                e.name AS event_name,
                e.date,
                e.place,
                e.city,
                co.name AS colla_name,
                COUNT(c.id) AS num_castells,
                STRING_AGG(
                    CASE 
                        WHEN c.castell_name != 'Pde4' THEN c.castell_name || ' (' || c.status || ')'
                        ELSE NULL
                    END, ', ' ORDER BY 
                    CASE 
                        WHEN c.status = 'Descarregat' THEN COALESCE(p.punts_descarregat, 0)
                        WHEN c.status = 'Carregat' THEN COALESCE(p.punts_carregat, 0)
                        ELSE 0 
                    END DESC) AS castells_fets
            FROM events e
            JOIN event_colles ec ON e.id = ec.event_fk
            JOIN colles co ON ec.colla_fk = co.id
            JOIN castells c ON ec.id = c.event_colla_fk
            LEFT JOIN puntuacions p ON (
                c.castell_name = p.castell_code_external 
                OR c.castell_name = p.castell_code
                OR c.castell_name = p.castell_code_name
            )
            WHERE 1=1
            {colla_filter}
            {year_filter}
            {location_filter}
            GROUP BY e.id, e.name, e.date, e.place, e.city, co.name
            ORDER BY SUM(CASE 
                WHEN c.status = 'Descarregat' AND c.castell_name != 'Pde4' THEN COALESCE(p.punts_descarregat, 0)
                WHEN c.status = 'Carregat' AND c.castell_name != 'Pde4' THEN COALESCE(p.punts_carregat, 0)
                ELSE 0 
            END) DESC, e.date DESC
            LIMIT %(limit)s
            """,
            required_params=[],
            optional_params=["colla", "year", "location"],
            description="Quin any o quin lloc s'ha fet la millor actuació (filtrable per colla i/o lloc)",
            default_limit=5
        )
        
        # Template for year summary
        templates[QuestionType.YEAR_SUMMARY] = QueryTemplate(
            question_type=QuestionType.YEAR_SUMMARY,
            sql_template="""
            SELECT 
                co.name AS colla_name,
                COUNT(DISTINCT e.id) AS num_actuacions,
                COUNT(c.id) AS num_castells,
                SUM(CASE WHEN c.status = 'Descarregat' THEN 1 ELSE 0 END) AS castells_descarregats,
                SUM(CASE WHEN c.status = 'Carregat' THEN 1 ELSE 0 END) AS castells_carregats
            FROM colles co
            JOIN event_colles ec ON co.id = ec.colla_fk
            JOIN events e ON ec.event_fk = e.id
            JOIN castells c ON ec.id = c.event_colla_fk
            LEFT JOIN puntuacions p ON (
                c.castell_name = p.castell_code_external 
                OR c.castell_name = p.castell_code
                OR c.castell_name = p.castell_code_name
            )
            WHERE 1=1
            {year_filter}
            {location_filter}
            {colla_filter}
            GROUP BY co.id, co.name
            ORDER BY SUM(CASE 
                WHEN c.status = 'Descarregat' AND c.castell_name != 'Pde4' THEN COALESCE(p.punts_descarregat, 0)
                WHEN c.status = 'Carregat' AND c.castell_name != 'Pde4' THEN COALESCE(p.punts_carregat, 0)
                ELSE 0 
            END) DESC
            LIMIT %(limit)s
            """,
            required_params=["year"],
            optional_params=["location", "colla"],
            description="Get summary for a specific year (filtrable per colla i/o lloc)",
            default_limit=10
        )
        
        # Template for first castell (quin any s'ha fet el primer castell)
        templates[QuestionType.FIRST_CASTELL] = QueryTemplate(
            question_type=QuestionType.FIRST_CASTELL,
            sql_template="""
            SELECT 
                EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) AS year,
                e.name AS event_name,
                e.date,
                e.place,
                e.city,
                co.name AS colla_name,
                c.castell_name,
                c.status
            FROM castells c
            JOIN event_colles ec ON c.event_colla_fk = ec.id
            JOIN events e ON ec.event_fk = e.id
            JOIN colles co ON ec.colla_fk = co.id
            LEFT JOIN puntuacions p ON (
                c.castell_name = p.castell_code_external 
                OR c.castell_name = p.castell_code
                OR c.castell_name = p.castell_code_name
            )
            WHERE 1=1
            {colla_filter}
            {castell_filter}
            {location_filter}
            {diada_filter}
            {status_filter}
            ORDER BY e.date ASC
            LIMIT 1
            """,
            required_params=["castell"],
            optional_params=["colla", "year", "location", "diada", "status"],
            description="Quin any s'ha fet el primer castell (castell requerit, colla, lloc, diada opcionals)",
            default_limit=3
        )
        
        # Template for castell statistics (estadístiques d'un castell específic)
        templates[QuestionType.CASTELL_STATISTICS] = QueryTemplate(
            question_type=QuestionType.CASTELL_STATISTICS,
            sql_template="""
            SELECT 
                c.castell_name,
                COUNT(CASE WHEN c.status = 'Descarregat' THEN 1 END) AS cops_descarregat,
                COUNT(CASE WHEN c.status = 'Carregat' THEN 1 END) AS cops_carregat,
                COUNT(CASE WHEN c.status = 'Intent desmuntat' THEN 1 END) AS cops_intent_desmuntat,
                COUNT(CASE WHEN c.status = 'Intent' THEN 1 END) AS cops_intent,
                MIN(CASE WHEN c.status = 'Descarregat' THEN e.date END) AS primera_data_descarregat,
                MIN(CASE WHEN c.status = 'Carregat' THEN e.date END) AS primera_data_carregat,
                COUNT(DISTINCT CASE WHEN c.status = 'Descarregat' THEN co.name END) AS colles_descarregat,
                COUNT(DISTINCT CASE WHEN c.status = 'Carregat' THEN co.name END) AS colles_carregat,
                COUNT(DISTINCT CASE WHEN c.status = 'Intent desmuntat' OR c.status = 'Intent' THEN co.name END) AS colles_intentat,
                COUNT(DISTINCT CASE WHEN c.status = 'Descarregat' OR c.status = 'Carregat' THEN co.name END) AS total_colles_carregat_o_descarregat,
                SUBSTR(STRING_AGG(DISTINCT CASE WHEN c.status = 'Descarregat' THEN co.name END, ', '), 1, 400) AS primeres_colles_descarregat,
                SUBSTR(STRING_AGG(DISTINCT CASE WHEN c.status = 'Carregat' THEN co.name END, ', '), 1, 400) AS primeres_colles_carregat,
                SUBSTR(STRING_AGG(DISTINCT CASE WHEN c.status = 'Intent desmuntat' OR c.status = 'Intent' THEN co.name END, ', '), 1, 400) AS primeres_colles_intentat,
                COALESCE(p.punts_descarregat, 0) AS punts_descarregat,
                COALESCE(p.punts_carregat, 0) AS punts_carregat
            FROM castells c
            JOIN event_colles ec ON c.event_colla_fk = ec.id
            JOIN events e ON ec.event_fk = e.id
            JOIN colles co ON ec.colla_fk = co.id
            LEFT JOIN puntuacions p ON (
                c.castell_name = p.castell_code_external 
                OR c.castell_name = p.castell_code
                OR c.castell_name = p.castell_code_name
            )
            WHERE 1=1
            {colla_filter}
            {castell_filter}
            {year_filter}
            {location_filter}
            {diada_filter}
            GROUP BY c.castell_name, p.punts_descarregat, p.punts_carregat
            """,
            required_params=["castell"],
            optional_params=["colla", "year", "location", "diada"],
            description="Estadístiques completes d'un castell específic (castell requerit, filtrable per colla, any, plaça, etc.)",
            default_limit=1
        )
        
        # Template for concurs queries (unified for all concurs questions)
        templates[QuestionType.CONCURS_RANKING] = QueryTemplate(
            question_type=QuestionType.CONCURS_RANKING,
            sql_template="""
            SELECT 
                c.edition,
                c.title,
                c.date,
                c.location,
                c.plaça,
                c.colla_guanyadora,
                cr.position,
                cr.colla_name,
                cr.total_points,
                cr.jornada,
                cr.ronda_1_json as primera_ronda,
                cr.ronda_2_json as segona_ronda,
                cr.ronda_3_json as tercera_ronda,
                cr.ronda_4_json as quarta_ronda,
                cr.ronda_5_json as cinquena_ronda,
                cr.ronda_6_json as sisena_ronda,
                cr.ronda_7_json as setmana_ronda
            FROM concurs c
            JOIN concurs_rankings cr ON c.id = cr.concurs_fk
            WHERE 1=1
            {edition_filter}
            {jornada_filter}
            {colla_filter}
            {position_filter}
            {year_filter}
            {castell_filter}
            {status_filter}
            ORDER BY cr.position ASC
            LIMIT %(limit)s
            """,
            required_params=[],
            optional_params=["edition", "jornada", "colla", "position", "year", "castell", "status"],
            description="Consultes sobre concursos de castells (classificació, resultats, estadístiques)",
            default_limit=5
        )
        
        # Template for concurs history (història de concursos)
        templates[QuestionType.CONCURS_HISTORY] = QueryTemplate(
            question_type=QuestionType.CONCURS_HISTORY,
            sql_template="""
            SELECT 
                c.edition,
                c.title,
                c.date,
                c.location,
                c.plaça,
                c.colla_guanyadora,
                c.num_colles,
                c.castells_intentats,
                c.maxim_castell,
                c.espectadors,
                COUNT(cr.id) AS colles_participants,
                AVG(cr.total_points) AS avg_points,
                MAX(cr.total_points) AS max_points,
                MIN(cr.total_points) AS min_points
            FROM concurs c
            LEFT JOIN concurs_rankings cr ON c.id = cr.concurs_fk
            WHERE 1=1
            {edition_filter}
            {location_filter}
            {year_filter}
            GROUP BY c.id, c.edition, c.title, c.date, c.location, c.plaça, c.colla_guanyadora, c.num_colles, c.castells_intentats, c.maxim_castell, c.espectadors
            ORDER BY c.date DESC
            LIMIT %(limit)s
            """,
            required_params=[],
            optional_params=["edition", "location", "year"],
            description="Història de concursos amb estadístiques (filtrable per edició, lloc, any)",
            default_limit=10
        )
        
        return templates
    
    
    def generate_sql_query_from_template(self, question: str, extracted_entities: Dict, question_type: QuestionType) -> Tuple[str, Dict[str, any]]:
        """
        Generate SQL query and parameters using a specific template
        
        Args:
            question: The user's question
            extracted_entities: Dictionary with colla, castells, anys, llocs, diades
            question_type: The specific QuestionType to use
            
        Returns:
            Tuple of (sql_query, parameters_dict)
        """
        # Get the appropriate template
        template = self.templates[question_type]
        
        # Check if we have the required parameters
        missing_required = []
        for param in template.required_params:
            if param == "colla" and not extracted_entities.get("colla"):
                missing_required.append("colla")
            elif param == "castell" and not extracted_entities.get("castells"):
                missing_required.append("castell")
            elif param == "year" and not extracted_entities.get("anys"):
                missing_required.append("year")
            elif param == "location" and not extracted_entities.get("llocs"):
                missing_required.append("location")
        
        # If we're missing required parameters, return None to trigger fallback
        if missing_required:
            return None, {}
        
        # Build parameters
        params = {}
        
        # Add optional parameters
        colla_filter = ""
        castell_filter = ""
        castell_having_filter = ""
        year_filter = ""
        location_filter = ""
        diada_filter = ""
        status_filter = ""
        edition_filter = ""
        jornada_filter = ""
        position_filter = ""
        
        if extracted_entities.get("colla"):
            if len(extracted_entities["colla"]) == 1:
                colla = extracted_entities["colla"][0]
                # For concurs queries, use cr.colla_name; for other queries, use co.name
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    colla_filter = f'''AND cr.colla_name = '{colla}' '''
                else:
                    colla_filter = f'''AND co.name = '{colla}' '''
                params["colla"] = colla
            elif len(extracted_entities["colla"]) > 1:
                colles = ', '.join(f"'{colla}'" for colla in extracted_entities["colla"])
                # For concurs queries, use cr.colla_name; for other queries, use co.name
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    colla_filter = f'''AND cr.colla_name IN ({colles}) '''
                else:
                    colla_filter = f'''AND co.name IN ({colles}) '''
                params["colla"] = extracted_entities["colla"]

        # Handle castell filter for WHERE clause (different from castell_having_filter for BEST_DIADA)
        if extracted_entities.get("castells"):
            if len(extracted_entities["castells"]) == 1:
                castell = extracted_entities["castells"][0]
                if isinstance(castell, Castell):
                    # For WHERE clause, we can filter by castell name directly
                    castell_filter = f"AND c.castell_name = '{code_to_name(castell.castell_code)}'"
                    params["castell"] = castell.castell_code
                else:
                    # Fallback for string format
                    castell_filter = f"AND c.castell_name = '{code_to_name(castell)}'"
                    params["castell"] = castell
            elif len(extracted_entities["castells"]) > 1:
                # Multiple castells - use IN condition
                castell_codes = []
                for castell in extracted_entities["castells"]:
                    if isinstance(castell, Castell):
                        castell_codes.append(code_to_name(castell.castell_code))
                    else:
                        castell_codes.append(code_to_name(castell))
                
                castell_list = ', '.join(f"'{code}'" for code in castell_codes)
                castell_filter = f"AND c.castell_name IN ({castell_list})"
                params["castell"] = castell_codes
         
        if extracted_entities.get("castells") and question_type == QuestionType.BEST_DIADA:
            if len(extracted_entities["castells"]) == 1:
                castell = extracted_entities["castells"][0]
                if isinstance(castell, Castell):
                    # Create combined filter for castell code and status
                    if castell.status:
                        # Match both castell code and status together
                        castell_having_filter = f"AND STRING_AGG(p.castell_code || ' (' || c.status || ')', ', ') LIKE '%{castell.castell_code} ({castell.status})%'"
                        params["castell"] = castell.castell_code
                        params["status"] = castell.status
                    else:
                        # Only match castell code (no status specified)
                        castell_having_filter = f"AND STRING_AGG(p.castell_code, ', ') LIKE '%{castell.castell_code}%'"
                        params["castell"] = castell.castell_code
                else:
                    # Fallback for string format
                    castell_having_filter = f"AND STRING_AGG(p.castell_code, ', ') LIKE '%{castell}%'"
                    params["castell"] = castell
            elif len(extracted_entities["castells"]) > 1:
                # Multiple castells - use OR conditions
                castell_conditions = []
                for castell in extracted_entities["castells"]:
                    if isinstance(castell, Castell):
                        if castell.status:
                            # Match both castell code and status together
                            castell_conditions.append(f"STRING_AGG(p.castell_code || ' (' || c.status || ')', ', ') LIKE '%{castell.castell_code} ({castell.status})%'")
                        else:
                            # Only match castell code (no status specified)
                            castell_conditions.append(f"STRING_AGG(p.castell_code, ', ') LIKE '%{castell.castell_code}%'")
                    else:
                        # Fallback for string format
                        castell_conditions.append(f"STRING_AGG(p.castell_code, ', ') LIKE '%{castell}%'")
                
                castell_having_filter = f"AND ({' OR '.join(castell_conditions)})"
                params["castell"] = [c.castell_code if isinstance(c, Castell) else c for c in extracted_entities["castells"]]
                params["status"] = [c.status for c in extracted_entities["castells"] if isinstance(c, Castell) and c.status]

        if extracted_entities.get("anys"):
            if len(extracted_entities["anys"]) == 1:
                year = extracted_entities["anys"][0]
                # For concurs queries, use cr.any; for other queries, use e.date
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    year_filter = f"AND cr.any = {year}"
                else:
                    year_filter = f"AND EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) = '{year}'"
                params["year"] = year
            elif len(extracted_entities["anys"]) > 1:
                anys = ', '.join(f"'{year}'" for year in extracted_entities["anys"])
                # For concurs queries, use cr.any; for other queries, use e.date
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    year_filter = f"AND cr.any IN ({anys})"
                else:
                    year_filter = f"AND EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) IN ({anys})"
                params["year"] = extracted_entities["anys"]
        
        if extracted_entities.get("llocs"):
            if len(extracted_entities["llocs"]) == 1:
                location = extracted_entities["llocs"][0]
                # For concurs queries, use c.location; for other queries, use e.city
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    location_filter = f"AND c.location LIKE '%{location}%'"
                else:
                    location_filter = f"AND e.city LIKE '%{location}%'"
                params["location"] = location
            elif len(extracted_entities["llocs"]) > 1:
                llocs = ', '.join(f"'{lloc}'" for lloc in extracted_entities["llocs"])
                # For concurs queries, use c.location; for other queries, use e.city
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    location_filter = f"AND c.location IN ({llocs})"
                else:
                    location_filter = f"AND e.city IN ({llocs})"
                params["location"] = extracted_entities["llocs"]
        
        if extracted_entities.get("diades"):
            if len(extracted_entities["diades"]) == 1:
                diada = extracted_entities["diades"][0]
                diada_filter = f"AND e.name LIKE '%{diada}%'"
                params["diada"] = diada
            elif len(extracted_entities["diades"]) > 1:
                diades = ', '.join(f"'{diada}'" for diada in extracted_entities["diades"])
                diada_filter = f"AND e.name IN ({diades})"
                params["diada"] = extracted_entities["diades"]

        # Handle status filter for WHERE clause (different from castell status in BEST_DIADA)
        if extracted_entities.get("status"):
            if len(extracted_entities["status"]) == 1:
                status = extracted_entities["status"][0]
                status_filter = f"AND c.status = '{status}'"
                params["status"] = status
            elif len(extracted_entities["status"]) > 1:
                statuses = ', '.join(f"'{status}'" for status in extracted_entities["status"])
                status_filter = f"AND c.status IN ({statuses})"
                params["status"] = extracted_entities["status"]

        # Handle concurs-related filters
        if extracted_entities.get("editions"):
            if len(extracted_entities["editions"]) == 1:
                edition = extracted_entities["editions"][0]
                edition_filter = f"AND c.edition = '{edition}'"
                params["edition"] = edition
            elif len(extracted_entities["editions"]) > 1:
                editions = ', '.join(f"'{edition}'" for edition in extracted_entities["editions"])
                edition_filter = f"AND c.edition IN ({editions})"
                params["edition"] = extracted_entities["editions"]

        if extracted_entities.get("jornades"):
            if len(extracted_entities["jornades"]) == 1:
                jornada = extracted_entities["jornades"][0]
                jornada_filter = f"AND cr.jornada LIKE '%{jornada}%'"
                params["jornada"] = jornada
            elif len(extracted_entities["jornades"]) > 1:
                jornades = ', '.join(f"'{jornada}'" for jornada in extracted_entities["jornades"])
                jornada_filter = f"AND cr.jornada IN ({jornades})"
                params["jornada"] = extracted_entities["jornades"]

        if extracted_entities.get("positions"):
            if len(extracted_entities["positions"]) == 1:
                position = extracted_entities["positions"][0]
                position_filter = f"AND cr.position = {position}"
                params["position"] = position
            elif len(extracted_entities["positions"]) > 1:
                positions = ', '.join(str(pos) for pos in extracted_entities["positions"])
                position_filter = f"AND cr.position IN ({positions})"
                params["position"] = extracted_entities["positions"]

        # Handle castell and status filters for concurs queries (search in JSON data)
        if question_type == QuestionType.CONCURS_RANKING:
            if extracted_entities.get("castells"):
                castell_conditions = []
                for castell in extracted_entities["castells"]:
                    if isinstance(castell, Castell):
                        castell_code = castell.castell_code
                        # Search for exact castell code match in JSON (more precise)
                        # Look for "castell": "4d9af" pattern to avoid partial matches
                        castell_conditions.append(f"""
                            (cr.ronda_1_json LIKE '%"castell": "{castell_code}"%' OR 
                             cr.ronda_2_json LIKE '%"castell": "{castell_code}"%' OR 
                             cr.ronda_3_json LIKE '%"castell": "{castell_code}"%' OR 
                             cr.ronda_4_json LIKE '%"castell": "{castell_code}"%' OR 
                             cr.ronda_5_json LIKE '%"castell": "{castell_code}"%' OR 
                             cr.ronda_6_json LIKE '%"castell": "{castell_code}"%' OR 
                             cr.ronda_7_json LIKE '%"castell": "{castell_code}"%' OR 
                             cr.rondes_json LIKE '%"castell": "{castell_code}"%')
                        """)
                    else:
                        # Fallback for string format
                        castell_conditions.append(f"""
                            (cr.ronda_1_json LIKE '%"castell": "{castell}"%' OR 
                             cr.ronda_2_json LIKE '%"castell": "{castell}"%' OR 
                             cr.ronda_3_json LIKE '%"castell": "{castell}"%' OR 
                             cr.ronda_4_json LIKE '%"castell": "{castell}"%' OR 
                             cr.ronda_5_json LIKE '%"castell": "{castell}"%' OR 
                             cr.ronda_6_json LIKE '%"castell": "{castell}"%' OR 
                             cr.ronda_7_json LIKE '%"castell": "{castell}"%' OR 
                             cr.rondes_json LIKE '%"castell": "{castell}"%')
                        """)
                
                castell_filter = f"AND ({' OR '.join(castell_conditions)})"
                params["castell"] = [c.castell_code if isinstance(c, Castell) else c for c in extracted_entities["castells"]]

            if extracted_entities.get("status"):
                status_conditions = []
                for status in extracted_entities["status"]:
                    # Search for exact status match in JSON (more precise)
                    # Look for "status": "Descarregat" pattern
                    status_conditions.append(f"""
                        (cr.ronda_1_json LIKE '%"status": "{status}"%' OR 
                         cr.ronda_2_json LIKE '%"status": "{status}"%' OR 
                         cr.ronda_3_json LIKE '%"status": "{status}"%' OR 
                         cr.ronda_4_json LIKE '%"status": "{status}"%' OR 
                         cr.ronda_5_json LIKE '%"status": "{status}"%' OR 
                         cr.ronda_6_json LIKE '%"status": "{status}"%' OR 
                         cr.ronda_7_json LIKE '%"status": "{status}"%' OR 
                         cr.rondes_json LIKE '%"status": "{status}"%')
                    """)
                
                status_filter = f"AND ({' OR '.join(status_conditions)})"
                params["status"] = extracted_entities["status"]

        # Set limit (use from entities if provided, otherwise use template's default)
        params["limit"] = extracted_entities.get("limit", template.default_limit)
        
        # Build the final SQL query
        sql_query = template.sql_template.format(
            colla_filter=colla_filter,
            castell_filter=castell_filter,
            year_filter=year_filter,
            location_filter=location_filter,
            diada_filter=diada_filter,
            status_filter=status_filter,
            castell_having_filter=castell_having_filter,
            status_having_filter="",  # No longer used since status is combined with castell
            edition_filter=edition_filter,
            jornada_filter=jornada_filter,
            position_filter=position_filter
        )
        
        # Clean up the query
        sql_query = sql_query.replace("  ", " ").strip()
        
        return sql_query, params
    
    def get_available_templates(self) -> Dict[str, str]:
        """Get list of available query templates for debugging"""
        return {
            template.question_type.value: template.description 
            for template in self.templates.values()
        }
    
    def create_sql_query(self, question: str, entities: Dict, sql_query_type: str = "custom", llm_call_func=None) -> Tuple[str, Dict[str, any]]:
        """
        Generate a SQL query and parameters using the predefined template system or custom generation.
        Returns (sql_query, params) tuple.
        """
        # Check if we should use a predefined template
        if sql_query_type != "custom":
            # Try predefined template first
            result = self._create_predefined_sql_query(question, entities, sql_query_type)
            
            # If predefined template failed (missing required params), fallback to custom
            if result[0] is None:
                print(f"[SQL] Predefined template failed for {sql_query_type}, falling back to custom LLM generation")
                return self._create_custom_sql_query(question, entities, llm_call_func)
            
            return result
        else:
            return self._create_custom_sql_query(question, entities, llm_call_func)
    
    def _create_predefined_sql_query(self, question: str, entities: Dict, sql_query_type: str) -> Tuple[str, Dict[str, any]]:
        """Create SQL query using predefined templates"""
        # Map sql_query_type to QuestionType
        query_type_mapping = {
            "millor_diada": QuestionType.BEST_DIADA,
            "millor_castell": QuestionType.BEST_CASTELL, 
            "castell_historia": QuestionType.CASTELL_HISTORIA,
            "location_actuations": QuestionType.LOCATION_ACTUATIONS,
            "first_castell": QuestionType.FIRST_CASTELL,
            "castell_statistics": QuestionType.CASTELL_STATISTICS,
            "year_summary": QuestionType.YEAR_SUMMARY,
            "concurs_ranking": QuestionType.CONCURS_RANKING,
            "concurs_history": QuestionType.CONCURS_HISTORY
        }
        
        # Get the specific QuestionType
        question_type = query_type_mapping.get(sql_query_type)
        if not question_type:
            raise Exception(f"Tipus de consulta SQL no reconegut: {sql_query_type}")
        
        # Try to use the specific template
        result = self.generate_sql_query_from_template(question, entities, question_type)
        
        # If template generation failed (missing required params), return None to trigger fallback
        if result[0] is None:
            return None, {}
        
        return result
    
    def _make_entities_serializable(self, entities: Dict) -> Dict:
        """Convert Castell objects to dictionaries for JSON serialization"""
        serializable = {}
        for key, value in entities.items():
            if key == "castells" and isinstance(value, list):
                # Convert Castell objects to dictionaries
                serializable[key] = []
                for castell in value:
                    if hasattr(castell, 'castell_code'):
                        castell_dict = {"castell_code": castell.castell_code}
                        if hasattr(castell, 'status') and castell.status:
                            castell_dict["status"] = castell.status
                        serializable[key].append(castell_dict)
                    else:
                        serializable[key].append(castell)
            else:
                serializable[key] = value
        return serializable
    
    def _create_custom_sql_query(self, question: str, entities: Dict, llm_call_func) -> Tuple[str, Dict[str, any]]:
        """Create SQL query using the original LLM generation method"""
        if not llm_call_func:
            raise Exception("llm_call_func is required for custom SQL generation")

        # Convert Castell objects to dictionaries for JSON serialization
        serializable_entities = self._make_entities_serializable(entities)

        # The model sees the schema, the entities, and the question
        sql_prompt = f"""
            Ets un expert en bases de dades castelleres. 
            Tens una base de dades PostgreSQL amb l'estructura següent:

            {DB_SCHEMA_DESCRIPTION}

            L'usuari ha fet la pregunta:
            > "{question}"

            Entitats detectades:
            {json.dumps(serializable_entities, ensure_ascii=False, indent=2)}

            Genera una única consulta SQL **completa i vàlida per PostgreSQL** que respongui aquesta pregunta.
            - Usa noms exactes de taules i columnes segons l'esquema.
            - Si cal filtrar per any, pots utilitzar `EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) = %(year)s`.
            - Fes JOINs només si són necessaris.
            - Prioritza les columnes `punts_descarregat` i `punts_carregat` de la taula `puntuacions` per calcular el millor castell.
            - Per unir castells amb puntuacions, usa `c.castell_name = p.castell_code_name`.
            - Els valors de status són: 'Descarregat', 'Carregat', 'Intent desmuntat', 'Intent'.
            - No facis DROP, DELETE ni UPDATE.
            - La consulta ha de retornar un màxim de 15 files.
            - Utilitza paràmetres amb `%(nom)s` en lloc d'inserir valors directament.
            - Si no tens tots els paràmetres necessaris, simplifica la consulta o usa LIKE per fer cerques més flexibles.
            - **IMPORTANT**: Si la pregunta és sobre actuacions, inclou informació contextual com:
              - e.name (nom de l'event/diada)
              - e.date (data)
              - e.place (lloc/plaça)
              - e.city (ciutat)
              - co.name (nom de la colla)
              - c.castell_name (nom del castell)
            - **CRÍTIC**: Quan la pregunta és sobre "millor castell aconseguit":
              - "Aconseguit" = status = 'Descarregat' OR status = 'Carregat'
              - "Intent" = status = 'Intent desmuntat' (NO és aconseguit o completat)
              - Sempre inclou el nom de la colla que el va fer
            - Retorna **només el codi SQL**, sense comentaris ni explicacions.
            """

        # Call LLM to generate SQL
        try:
            sql_query = llm_call_func(sql_prompt)
            
            # Clean the SQL query - remove markdown formatting if present
            sql_query = sql_query.strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]  # Remove ```sql
            if sql_query.startswith("```"):
                sql_query = sql_query[3:]   # Remove ```
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]  # Remove trailing ```
            sql_query = sql_query.strip()
            
        except Exception as e:
            raise Exception(f"No he pogut generar la consulta SQL personalitzada: {e}")

        # Build parameters dictionary
        params = {}
        if entities.get("colla"):
            params["colla_name"] = entities["colla"][0]
            params["nom"] = entities["colla"][0]  # Alternative parameter name
            params["colla"] = entities["colla"][0]  # Another alternative parameter name
        if entities.get("anys"):
            params["year"] = str(entities["anys"][0])
            params["any"] = str(entities["anys"][0])  # Alternative parameter name
        if entities.get("llocs"):
            params["city"] = entities["llocs"][0]
            params["place"] = entities["llocs"][0]  # Alternative parameter name
        if entities.get("diades"):
            params["diada_name"] = entities["diades"][0]
        if entities.get("castells"):
            castell = entities["castells"][0]
            if isinstance(castell, Castell):
                params["castell_name"] = castell.castell_code
                if castell.status:
                    params["status"] = castell.status
            else:
                params["castell_name"] = castell

        return sql_query, params
    
    def execute_sql_query(self, sql_query: str, params: Dict[str, any]) -> List:
        """
        Execute a SQL query safely and return the results.
        """
        from datetime import datetime
        
        try:
            # Connection timing
            conn_start = datetime.now()
            conn = psycopg2.connect(DATABASE_URL)
            conn_time = (datetime.now() - conn_start).total_seconds() * 1000
            if conn_time > 10:
                print(f"[TIMING] SQL connection: {conn_time:.2f}ms")
            
            # Query execution timing
            exec_start = datetime.now()
            cursor = conn.cursor()
            
            # Log the query for debugging (truncate if too long)
            query_preview = sql_query[:200] + "..." if len(sql_query) > 200 else sql_query
            print(f"[SQL] Executing query: {query_preview}")
            print(f"[SQL] Params: {params}")
            
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            exec_time = (datetime.now() - exec_start).total_seconds() * 1000
            print(f"[TIMING] SQL query execution: {exec_time:.2f}ms (rows: {len(rows)})")
            
            # Warn if query is slow
            if exec_time > 1000:
                print(f"[WARNING] SQL query took {exec_time:.2f}ms - consider optimization!")
            
            # Convert to list of dictionaries for compatibility
            convert_start = datetime.now()
            columns = [desc[0] for desc in cursor.description]
            result = [dict(zip(columns, row)) for row in rows]
            convert_time = (datetime.now() - convert_start).total_seconds() * 1000
            if convert_time > 10:
                print(f"[TIMING] SQL result conversion: {convert_time:.2f}ms")
            
            conn.close()
            return result
        except Exception as e:
            raise Exception(f"Hi ha hagut un error executant la consulta SQL: {e}\nConsulta generada:\n{sql_query}")


# ---- Specific Prompts for Each Query Type ----

def get_sql_summary_prompt(query_type: str, question: str, table_str: str) -> str:
    """
    Retorna un prompt específic per a cada tipus de consulta SQL.
    """
    
#     if query_type == "millor_diada":
#         return f"""
# Ets un expert en el món casteller. Respon la pregunta següent utilitzant els resultats de la base de dades.

# **Pregunta:** {question}

# **Resultats obtinguts:**
# {table_str}

# **Instruccions específiques per a respondre la pregunta:**
# 1. Dona informacio de les millors diades/ actuacions en funcio de la pregunta.
# 2. Proporciona **TOT EL CONTEXT** de la millor actuació:
#    - Data exacta i lloc/plaça
#    - Nom de la diada o esdeveniment 
#    - Els castells fets (excloent Pde4/Pd4/Pde5/Pd5) amb el seu estat (Descarregat/Carregat/Intent desmuntat)
#    - No incloguis informacio dels punts obtinguts (a menys que la pregunta ho demani específicament)
# 3. **NO donis opinions** ni valoracions. 
# 4. **NO** afeixis cap 'Nota' al final ni informació irrellevant. Respon amb naturalitat sense repetir informacio.
# 5. Respon en format Markdown. No afageixis títol. 
# """

    
    if query_type == "millor_diada":
        return f"""
Ets un expert en el món casteller. Respon la pregunta següent utilitzant els resultats de la base de dades.

**Pregunta:** {question}

**Resultats obtinguts (llista de les millors diades/actuacions en ordre):**
{table_str}

**Instruccions específiques per a respondre la pregunta:**

- Proporciona primer un paràgraf responent a la pregunta amb informació de la diada, el lloc, la data, els castells realitzats (amb el seu estat) - sense incloure els Pd4/Pd5/Pde4/Pde5.
- No afeixis cap 'Nota' al final ni informació irrellevant 
- No indiquis el nombre total de castells realitzats. 
- Respon amb naturalitat sense repetir informació.
- Respòn en format Markdown, amb **negreta** per a destacar les dades més rellevants al paràgraf.
- **Afegix una taula al final** amb les seguents columnes: Diada, Colla, Lloc (event_place i event_city), Data, Castells
- No afegeixis informació dels punts obtinguts dels castells realitzats.
"""

    elif query_type == "millor_castell":
        return f"""
Ets un expert en el món casteller. Respon la pregunta següent utilitzant els resultats de la base de dades.

**Pregunta:** {question}

**Resultats obtinguts:**
{table_str}

**Instruccions específiques per a millor castell:**
1. Identifica el millor castell (o els millors castells) en funcio de la pregunta, estan per ordre de dificultat i punts.
2. Proporciona **TOT EL CONTEXT** del millor castell:
   - Data exacta i lloc/plaça
   - Nom de la diada o esdeveniment
   - Estat del castell que hagin completat (Descarregat/Carregat/Intent desmuntat)
3. Si parla de castell aconseguit, vol dir que és descarregat. Si el castell és intentat o intent desmuntat, vol dir que el castell s'ha provat pero no s'ha aconseguit o fet.
4. **NO donis opinions** ni valoracions. Respon de manera natural. 
"""

    elif query_type == "castell_historia":
        return f"""
Ets un expert en el món casteller. Respon la pregunta següent utilitzant els resultats de la base de dades.

**Pregunta:** {question}

**Resultats obtinguts:**
{table_str}

**Instruccions específiques per a castell història:**
1. Resumeix quantes vegades s'ha fet aquest castell i en quins estats.
2. Proporciona **estadístiques clares**:
   - Nombre total d'ocasions
   - Quantitat descarregat vs carregat
   - Primera i última data
   - Ciutats on s'ha fet
3. Si hi ha múltiples colles, organitza la informació per colla.
4. **NO donis opinions** ni valoracions.
"""

    elif query_type == "location_actuations":
        return f"""
Ets un expert en el món casteller. Respon la pregunta següent utilitzant els resultats de la base de dades.

**Pregunta:** {question}

**Resultats obtinguts:**
{table_str}

**Instruccions específiques per a actuacions per lloc:**
1. Identifica l'any o lloc de la millor actuació basant-te en els punts totals.
2. Proporciona **TOT EL CONTEXT** dque tinguis en funcio de la pregunta:
   - Any i lloc/plaça
   - Nom de la diada o esdeveniment
   - Estat de cada castell
3. **NO donis opinions** ni valoracions.
"""

    elif query_type == "first_castell":
        return f"""
Ets un expert en el món casteller. Respon la pregunta següent utilitzant els resultats de la base de dades.

**Pregunta:** {question}

**Resultats obtinguts:**
{table_str}

**Instruccions específiques per a primer castell:**
1. Identifica la primera vegada que es va aconseguir aquest castell.
2. Proporciona **TOT EL CONTEXT** que sigui rellevant en funcio de la pregunta:
   - Data exacta (any, mes, dia)
   - Lloc/plaça on es va fer
   - Nom de la diada o esdeveniment
   - Estat del castell (Descarregat/Carregat)
3. **NO donis opinions** ni valoracions.
"""

    elif query_type == "castell_statistics":
        return f"""
Ets un expert en el món casteller. Respon la pregunta següent utilitzant els resultats de la base de dades.

**Pregunta:** {question}

**Resultats obtinguts:**
{table_str}

**Instruccions específiques per a estadístiques de castell:**
1. Resumeix les estadístiques completes d'aquest castell.
2. Proporciona **dades estructurades**:
   - Nombre de cops descarregat vs carregat
   - Primera data aconseguit (descarregat i carregat)
   - Nombre de colles que l'han aconseguit
   - Llista de colles que l'han descarregat i carregat
   - Punts que val cada estat
3. Organitza la informació de manera clara i fàcil de llegir.
4. Destaca fets rellevants com la primera colla que el va aconseguir.
5. **NO donis opinions** sobre la dificultat o importància, només fets objectius.

Resposta:
"""

    elif query_type == "year_summary":
        return f"""
Ets un expert en el món casteller. Respon la pregunta següent utilitzant els resultats de la base de dades.

**Pregunta:** {question}

**Resultats obtinguts:**
{table_str}

**Instruccions específiques per a resum d'any:**
1. Resumeix l'activitat castellera de l'any en qüestió.
2. Proporciona **estadístiques clares**:
   - Nombre d'actuacions per colla
   - Nombre total de castells fets
   - Nombre de castells descarregats vs carregats
   - Classificació de les colles per punts totals
3. Si la pregunta es refereix a una colla específica, centra't en aquesta colla.
4. Si la pregunta es refereix a un lloc específic, centra't en aquest lloc.
5. Organitza la informació de manera clara i fàcil de llegir.
6. **NO donis opinions** ni valoracions.

"""

    elif query_type == "concurs_ranking":
        return f"""
Ets un expert en el món casteller. Respon la pregunta sobre el concurs de castells següent utilitzant els resultats de la base de dades.

**Pregunta:** {question}

**Resultats obtinguts:**
{table_str}

**Instruccions:**
1. Respon la pregunta sobre concursos de castells utilitzant les dades proporcionades.
2. Proporciona **informació completa** segons la pregunta.
3. **IMPORTANT**: Si hi ha dades de rondes (ronda_1_json, ronda_2_json, etc.), inclou informació sobre els castells fets:
   - Castell code i estat (Descarregat, Carregat, Intent desmuntat, Intent)
   - Ignora rondes que no tinguis informació sobre castells
4. NO donis opinions ni valoracions.
"""

    elif query_type == "concurs_history":
        return f"""
Ets un expert en el món casteller. Respon la pregunta següent referent a la història de concursos de castells utilitzant els resultats de la base de dades.

**Pregunta:** {question}

**Resultats obtinguts:**
{table_str}

**Instruccions:**
1. Proporciona estadístiques completes referents a la pregunta.
2. NO donis opinions ni valoracions.
"""

    else:  # custom o altres
        return f"""
Ets un expert en el mon casteller. La teva tasca és respondre la pregunta següent utilitzant el resultat d'una consulta SQL a la base de dades.

### Context
- **Resultats obtinguts de la base de dades:**
{table_str}

- **Pregunta original de l'usuari:**
{question}

### Instruccions
1. Utilitza **la informació de la consulta** per **respondre directament la pregunta** de l'usuari.
2. **IMPORTANT**: Si la pregunta és sobre una actuació específica, proporciona **TOT EL CONTEXT**:
   - On es va fer (lloc/plaça)
   - Quina diada era
   - Tots els castells que es van fer (normalment 3 castells + 1 pilar)
   - Les dates i detalls específics
4. **CRÍTIC**: Quan parles de castells aconseguits, fets o realitzats:
   - "Descarregat" = castell completament aconseguit (màxim valor)
   - "Carregat" = castell aconseguit però no descarregat (valor mitjà)
   - "Intent desmuntat" = castell NO aconseguit (només intentat)
   - Sempre especifica quin estat tenia el castell
5. **NO afegeixis comentaris genèrics**, no donis opinions ni valoracions.
6. **SIGUES ESPECÍFIC**: Si hi ha dades sobre dates, llocs, castells, colles, inclou-les totes.
7. No cal que mencionis els punts o puntuacions dels castells (a menys que la pregunta ho demani específicament).

"""


