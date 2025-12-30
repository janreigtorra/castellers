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

# Limits for SQL queries and LLM context
SQL_RESULT_LIMIT = 20      # Results shown in frontend table
LLM_CONTEXT_LIMIT = 5      # Results fed to LLM for summarization
DEFAULT_LIMIT = SQL_RESULT_LIMIT

# Placeholder message for no results found
NO_RESULTS_MESSAGE = "No he trobat cap resultat a la base de dades referent a la teva pregunta."


def escape_sql_string(value: str) -> str:
    """Escape single quotes in SQL string values to prevent SQL injection"""
    if value is None:
        return value
    return value.replace("'", "''")


class NoResultsFoundError(Exception):
    """Exception raised when a SQL query returns no results"""
    def __init__(self, message: str = NO_RESULTS_MESSAGE):
        self.message = message
        super().__init__(self.message)

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
                            CASE
                                WHEN c.castell_name ~ '^[0-9]' THEN 'castell'
                                WHEN c.castell_name ~ '^[Pp]' THEN 'pilar'
                                ELSE 'altres'
                            END AS tipus
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
                    ),
                    ranked AS (
                        SELECT
                            *,
                            ROW_NUMBER() OVER (
                                PARTITION BY event_id, colla_id, tipus
                                ORDER BY punts DESC
                            ) AS rn_tipus
                        FROM castells_punts
                    ),
                    millors_castells AS (
                        SELECT *
                        FROM ranked
                        WHERE
                            (tipus = 'castell' AND rn_tipus <= 3)
                            OR
                            (tipus = 'pilar' AND rn_tipus = 1)
                    ),
                    aggregated AS (
                    SELECT
                        event_id,
                        event_name,
                        event_date,
                        colla_name,
                        event_place,
                        event_city,
                        STRING_AGG(
                            castell_name || ' (' || status || ')',
                            ', '
                            ORDER BY punts DESC
                        ) AS castells_fets,
                        SUM(punts) AS total_punts
                    FROM millors_castells
                    GROUP BY
                        event_id,
                        event_name,
                        event_date,
                        event_place,
                        event_city,
                        colla_name
                    HAVING 1=1
                    {castell_having_filter}
                    {status_having_filter}
                    )
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY total_punts DESC) AS ranking,
                        event_name,
                        event_date,
                        colla_name,
                        event_place,
                        event_city,
                        castells_fets,
                        total_punts
                    FROM aggregated
                    ORDER BY ranking
                    LIMIT %(limit)s;

            """,
            required_params=[],
            optional_params=["colla", "year", "location", "diada", "castell", "status"],
            description="Find the best diada/actuació (can be filtered by colla, year, location, castell, status), summing only the top 4 castells per event, excluding Pde4",
            default_limit=SQL_RESULT_LIMIT
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
            default_limit=SQL_RESULT_LIMIT
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
            default_limit=SQL_RESULT_LIMIT
        )
        
      
        # Template for year of best actuation (quin any s'ha fet la millor actuació)
        templates[QuestionType.LOCATION_ACTUATIONS] = QueryTemplate(
            question_type=QuestionType.LOCATION_ACTUATIONS,
            sql_template="""
            WITH castells_punts AS (
                SELECT 
                    e.id AS event_id,
                    EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) AS year,
                    e.name AS event_name,
                    e.date,
                    e.place,
                    e.city,
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
                    CASE
                        WHEN c.castell_name ~ '^[0-9]' THEN 'castell'
                        WHEN c.castell_name ~ '^[Pp]' THEN 'pilar'
                        ELSE 'altres'
                    END AS tipus
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
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY event_id, colla_id, tipus
                        ORDER BY punts DESC
                    ) AS rn_tipus
                FROM castells_punts
            ),
            millors_castells AS (
                SELECT *
                FROM ranked
                WHERE
                    (tipus = 'castell' AND rn_tipus <= 3)
                    OR
                    (tipus = 'pilar' AND rn_tipus = 1)
            )
            SELECT
                year,
                event_name,
                date,
                place,
                city,
                colla_name,
                COUNT(castell_id) AS num_castells,
                STRING_AGG(
                    castell_name || ' (' || status || ')',
                    ', '
                    ORDER BY punts DESC
                ) AS castells_fets,
                SUM(punts) AS total_punts
            FROM millors_castells
            GROUP BY
                event_id,
                year,
                event_name,
                date,
                place,
                city,
                colla_name
            ORDER BY total_punts DESC, date DESC
            LIMIT %(limit)s
            """,
            required_params=[],
            optional_params=["colla", "year", "location"],
            description="Quin any o quin lloc s'ha fet la millor actuació (filtrable per colla i/o lloc)",
            default_limit=SQL_RESULT_LIMIT
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
                SUM(CASE WHEN c.status = 'Carregat' THEN 1 ELSE 0 END) AS castells_carregats, 
                SUM(CASE WHEN c.status = 'Intent desmuntat' THEN 1 ELSE 0 END) AS castells_intent_desmuntat,
                SUM(CASE WHEN c.status = 'Intent' THEN 1 ELSE 0 END) AS castells_intent
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
                WHEN c.status = 'Descarregat' THEN COALESCE(p.punts_descarregat, 0)
                WHEN c.status = 'Carregat' THEN COALESCE(p.punts_carregat, 0)
                ELSE 0 
            END) DESC
            LIMIT %(limit)s
            """,
            required_params=["year"],
            optional_params=["location", "colla"],
            description="Get summary for a specific year (filtrable per colla i/o lloc)",
            default_limit=SQL_RESULT_LIMIT
        )
        
        # Template for first castell (quin any s'ha fet el primer castell)
        templates[QuestionType.FIRST_CASTELL] = QueryTemplate(
            question_type=QuestionType.FIRST_CASTELL,
            sql_template="""
            SELECT DISTINCT ON (c.status)
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
            ORDER BY c.status, e.date ASC
            LIMIT 4
            """,
            required_params=["castell"],
            optional_params=["colla", "year", "location", "diada", "status"],
            description="Quin any s'ha fet el primer castell (castell requerit, colla, lloc, diada opcionals)",
            default_limit=SQL_RESULT_LIMIT
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
                MIN(CASE WHEN c.status = 'Descarregat' THEN TO_DATE(e.date, 'DD/MM/YYYY') END) AS primera_data_descarregat,
                MIN(CASE WHEN c.status = 'Carregat' THEN TO_DATE(e.date, 'DD/MM/YYYY') END) AS primera_data_carregat,
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
            default_limit=SQL_RESULT_LIMIT
        )
        
        # Template for concurs queries (unified for all concurs questions)
        templates[QuestionType.CONCURS_RANKING] = QueryTemplate(
            question_type=QuestionType.CONCURS_RANKING,
            sql_template="""
            SELECT 
                c.edition,
                c.title,
                c.plaça,
                {position_select},
                cr.colla_name,
                cr.total_points,
                cr.jornada,
                CASE
                    WHEN cr.ronda_1_json IS NOT NULL AND cr.ronda_1_json <> ''
                    THEN
                        jsonb_extract_path_text(cr.ronda_1_json::jsonb, 'castell')
                        || ' ('
                        || jsonb_extract_path_text(cr.ronda_1_json::jsonb, 'status')
                        || ')'
                END AS primera_ronda, 
                CASE
                    WHEN cr.ronda_2_json IS NOT NULL AND cr.ronda_2_json <> ''
                    THEN
                        jsonb_extract_path_text(cr.ronda_2_json::jsonb, 'castell')
                        || ' ('
                        || jsonb_extract_path_text(cr.ronda_2_json::jsonb, 'status')
                        || ')'
                END AS segona_ronda,
                CASE
                    WHEN cr.ronda_3_json IS NOT NULL AND cr.ronda_3_json <> ''
                    THEN
                        jsonb_extract_path_text(cr.ronda_3_json::jsonb, 'castell')
                        || ' ('
                        || jsonb_extract_path_text(cr.ronda_3_json::jsonb, 'status')
                        || ')'
                END AS tercera_ronda,

                CASE
                    WHEN cr.ronda_4_json IS NOT NULL AND cr.ronda_4_json <> ''
                    THEN
                        jsonb_extract_path_text(cr.ronda_4_json::jsonb, 'castell')
                        || ' ('
                        || jsonb_extract_path_text(cr.ronda_4_json::jsonb, 'status')
                        || ')'
                END AS quarta_ronda,

                CASE
                    WHEN cr.ronda_5_json IS NOT NULL AND cr.ronda_5_json <> ''
                    THEN
                        jsonb_extract_path_text(cr.ronda_5_json::jsonb, 'castell')
                        || ' ('
                        || jsonb_extract_path_text(cr.ronda_5_json::jsonb, 'status')
                        || ')'
                END AS cinquena_ronda
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
            default_limit=SQL_RESULT_LIMIT
        )
        
        # Template for concurs history (història de concursos)
        templates[QuestionType.CONCURS_HISTORY] = QueryTemplate(
            question_type=QuestionType.CONCURS_HISTORY,
            sql_template="""
            SELECT 
                cr."any" as any,
                cr.jornada,
                COUNT(DISTINCT cr.colla_name) AS colles_participants,
                (array_agg(cr.colla_name ORDER BY cr.total_points DESC))[1] AS colla_guanyadora,
                MAX(cr.total_points) AS punts_guanyador,
                STRING_AGG(
                    DISTINCT CASE 
                        WHEN cr.ronda_1_json IS NOT NULL AND cr.ronda_1_json <> '' 
                             AND jsonb_extract_path_text(cr.ronda_1_json::jsonb, 'status') = 'Descarregat'
                        THEN jsonb_extract_path_text(cr.ronda_1_json::jsonb, 'castell')
                    END, ', '
                ) AS castells_r1_descarregats,
                STRING_AGG(
                    DISTINCT CASE 
                        WHEN cr.ronda_2_json IS NOT NULL AND cr.ronda_2_json <> '' 
                             AND jsonb_extract_path_text(cr.ronda_2_json::jsonb, 'status') = 'Descarregat'
                        THEN jsonb_extract_path_text(cr.ronda_2_json::jsonb, 'castell')
                    END, ', '
                ) AS castells_r2_descarregats,
                STRING_AGG(
                    DISTINCT CASE 
                        WHEN cr.ronda_3_json IS NOT NULL AND cr.ronda_3_json <> '' 
                             AND jsonb_extract_path_text(cr.ronda_3_json::jsonb, 'status') = 'Descarregat'
                        THEN jsonb_extract_path_text(cr.ronda_3_json::jsonb, 'castell')
                    END, ', '
                ) AS castells_r3_descarregats,
                STRING_AGG(
                    DISTINCT CASE 
                        WHEN cr.ronda_4_json IS NOT NULL AND cr.ronda_4_json <> '' 
                             AND jsonb_extract_path_text(cr.ronda_4_json::jsonb, 'status') = 'Descarregat'
                        THEN jsonb_extract_path_text(cr.ronda_4_json::jsonb, 'castell')
                    END, ', '
                ) AS castells_r4_descarregats,
                STRING_AGG(
                    DISTINCT CASE 
                        WHEN cr.ronda_5_json IS NOT NULL AND cr.ronda_5_json <> '' 
                             AND jsonb_extract_path_text(cr.ronda_5_json::jsonb, 'status') = 'Descarregat'
                        THEN jsonb_extract_path_text(cr.ronda_5_json::jsonb, 'castell')
                    END, ', '
                ) AS castells_r5_descarregats
            FROM concurs_rankings cr
            WHERE 1=1
            {year_filter}
            GROUP BY cr."any", cr.jornada
            ORDER BY cr."any" DESC, cr.jornada ASC
            LIMIT %(limit)s
            """,
            required_params=[],
            optional_params=["year"],
            description="Història de concursos amb estadístiques (filtrable per any)",
            default_limit=SQL_RESULT_LIMIT
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
        position_select = "cr.position AS position"
        
        if extracted_entities.get("colla"):
            if len(extracted_entities["colla"]) == 1:
                colla = extracted_entities["colla"][0]
                # For concurs queries, use cr.colla_name; for other queries, use co.name
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    colla_filter = "AND cr.colla_name = %(colla_param)s"
                else:
                    colla_filter = "AND co.name = %(colla_param)s"
                params["colla_param"] = colla
                params["colla"] = colla
            elif len(extracted_entities["colla"]) > 1:
                # For concurs queries, use cr.colla_name; for other queries, use co.name
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    colla_filter = "AND cr.colla_name IN %(colla_param)s"
                else:
                    colla_filter = "AND co.name IN %(colla_param)s"
                params["colla_param"] = tuple(extracted_entities["colla"])
                params["colla"] = extracted_entities["colla"]

        # Handle castell filter for WHERE clause (different from castell_having_filter for BEST_DIADA)
        if extracted_entities.get("castells"):
            if len(extracted_entities["castells"]) == 1:
                castell = extracted_entities["castells"][0]
                if isinstance(castell, Castell):
                    # For WHERE clause, we can filter by castell name directly
                    castell_filter = "AND c.castell_name = %(castell_param)s"
                    params["castell_param"] = code_to_name(castell.castell_code)
                    params["castell"] = castell.castell_code
                else:
                    # Fallback for string format
                    castell_filter = "AND c.castell_name = %(castell_param)s"
                    params["castell_param"] = code_to_name(castell)
                    params["castell"] = castell
            elif len(extracted_entities["castells"]) > 1:
                # Multiple castells - use IN condition
                castell_codes = []
                for castell in extracted_entities["castells"]:
                    if isinstance(castell, Castell):
                        castell_codes.append(code_to_name(castell.castell_code))
                    else:
                        castell_codes.append(code_to_name(castell))
                
                castell_filter = "AND c.castell_name IN %(castell_param)s"
                params["castell_param"] = tuple(castell_codes)
                params["castell"] = castell_codes
         
        if extracted_entities.get("castells") and question_type == QuestionType.BEST_DIADA:
            if len(extracted_entities["castells"]) == 1:
                castell = extracted_entities["castells"][0]
                if isinstance(castell, Castell):
                    # Create combined filter for castell code and status
                    escaped_code = escape_sql_string(castell.castell_code)
                    if castell.status:
                        # Match both castell code and status together
                        escaped_status = escape_sql_string(castell.status)
                        castell_having_filter = f"AND STRING_AGG(p.castell_code || ' (' || c.status || ')', ', ') LIKE '%%{escaped_code} ({escaped_status})%%'"
                        params["castell"] = castell.castell_code
                        params["status"] = castell.status
                    else:
                        # Only match castell code (no status specified)
                        castell_having_filter = f"AND STRING_AGG(p.castell_code, ', ') LIKE '%%{escaped_code}%%'"
                        params["castell"] = castell.castell_code
                else:
                    # Fallback for string format
                    escaped_castell = escape_sql_string(castell)
                    castell_having_filter = f"AND STRING_AGG(p.castell_code, ', ') LIKE '%%{escaped_castell}%%'"
                    params["castell"] = castell
            elif len(extracted_entities["castells"]) > 1:
                # Multiple castells - use OR conditions
                castell_conditions = []
                for castell in extracted_entities["castells"]:
                    if isinstance(castell, Castell):
                        escaped_code = escape_sql_string(castell.castell_code)
                        if castell.status:
                            # Match both castell code and status together
                            escaped_status = escape_sql_string(castell.status)
                            castell_conditions.append(f"STRING_AGG(p.castell_code || ' (' || c.status || ')', ', ') LIKE '%%{escaped_code} ({escaped_status})%%'")
                        else:
                            # Only match castell code (no status specified)
                            castell_conditions.append(f"STRING_AGG(p.castell_code, ', ') LIKE '%%{escaped_code}%%'")
                    else:
                        # Fallback for string format
                        escaped_castell = escape_sql_string(castell)
                        castell_conditions.append(f"STRING_AGG(p.castell_code, ', ') LIKE '%%{escaped_castell}%%'")
                
                castell_having_filter = f"AND ({' OR '.join(castell_conditions)})"
                params["castell"] = [c.castell_code if isinstance(c, Castell) else c for c in extracted_entities["castells"]]
                params["status"] = [c.status for c in extracted_entities["castells"] if isinstance(c, Castell) and c.status]

        if extracted_entities.get("anys"):
            if len(extracted_entities["anys"]) == 1:
                year = extracted_entities["anys"][0]
                # For concurs queries, use cr.any; for other queries, use e.date
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    year_filter = "AND cr.any = %(year_param)s"
                else:
                    year_filter = "AND EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) = %(year_param)s"
                params["year_param"] = year
                params["year"] = year
            elif len(extracted_entities["anys"]) > 1:
                # For concurs queries, use cr.any; for other queries, use e.date
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    year_filter = "AND cr.any IN %(year_param)s"
                else:
                    year_filter = "AND EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) IN %(year_param)s"
                params["year_param"] = tuple(extracted_entities["anys"])
                params["year"] = extracted_entities["anys"]
        
        if extracted_entities.get("llocs"):
            if len(extracted_entities["llocs"]) == 1:
                location = extracted_entities["llocs"][0]
                # For concurs queries, use c.location; for other queries, use e.city
                # Use LIKE with wildcards for partial matching
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    location_filter = "AND c.location LIKE %(location_param)s"
                else:
                    location_filter = "AND e.city LIKE %(location_param)s"
                params["location_param"] = f"%{location}%"
                params["location"] = location
            elif len(extracted_entities["llocs"]) > 1:
                # For concurs queries, use c.location; for other queries, use e.city
                if question_type in [QuestionType.CONCURS_RANKING, QuestionType.CONCURS_HISTORY]:
                    location_filter = "AND c.location IN %(location_param)s"
                else:
                    location_filter = "AND e.city IN %(location_param)s"
                params["location_param"] = tuple(extracted_entities["llocs"])
                params["location"] = extracted_entities["llocs"]
        
        if extracted_entities.get("diades"):
            if len(extracted_entities["diades"]) == 1:
                diada = extracted_entities["diades"][0]
                diada_filter = "AND e.name LIKE %(diada_param)s"
                params["diada_param"] = f"%{diada}%"
                params["diada"] = diada
            elif len(extracted_entities["diades"]) > 1:
                diada_filter = "AND e.name IN %(diada_param)s"
                params["diada_param"] = tuple(extracted_entities["diades"])
                params["diada"] = extracted_entities["diades"]

        # Handle status filter for WHERE clause (different from castell status in BEST_DIADA)
        if extracted_entities.get("status"):
            if len(extracted_entities["status"]) == 1:
                status = extracted_entities["status"][0]
                status_filter = "AND c.status = %(status_param)s"
                params["status_param"] = status
                params["status"] = status
            elif len(extracted_entities["status"]) > 1:
                status_filter = "AND c.status IN %(status_param)s"
                params["status_param"] = tuple(extracted_entities["status"])
                params["status"] = extracted_entities["status"]

        # Handle concurs-related filters
        if extracted_entities.get("editions"):
            if len(extracted_entities["editions"]) == 1:
                edition = extracted_entities["editions"][0]
                edition_filter = "AND c.edition = %(edition_param)s"
                params["edition_param"] = edition
                params["edition"] = edition
            elif len(extracted_entities["editions"]) > 1:
                edition_filter = "AND c.edition IN %(edition_param)s"
                params["edition_param"] = tuple(extracted_entities["editions"])
                params["edition"] = extracted_entities["editions"]

        if extracted_entities.get("jornades"):
            # When filtering by jornada, use posicio_jornada for position
            position_select = "cr.posicio_jornada AS position"
            if len(extracted_entities["jornades"]) == 1:
                jornada = extracted_entities["jornades"][0]
                jornada_filter = "AND cr.jornada LIKE %(jornada_param)s"
                params["jornada_param"] = f"%{jornada}%"
                params["jornada"] = jornada
            elif len(extracted_entities["jornades"]) > 1:
                jornada_filter = "AND cr.jornada IN %(jornada_param)s"
                params["jornada_param"] = tuple(extracted_entities["jornades"])
                params["jornada"] = extracted_entities["jornades"]

        if extracted_entities.get("positions"):
            if len(extracted_entities["positions"]) == 1:
                position = extracted_entities["positions"][0]
                if extracted_entities["jornades"]:
                    position_filter = "AND cr.posicio_jornada = %(position_param)s"
                    params["position_param"] = position
                    params["position"] = position
                else:
                    position_filter = "AND cr.position = %(position_param)s"
                    params["position_param"] = position
                    params["position"] = position

            elif len(extracted_entities["positions"]) > 1:
                if extracted_entities["jornades"]:
                    position_filter = "AND cr.posicio_jornada IN %(position_param)s"
                    params["position_param"] = tuple(extracted_entities["positions"])
                    params["position"] = extracted_entities["positions"]
                else:
                    position_filter = "AND cr.position IN %(position_param)s"
                    params["position_param"] = tuple(extracted_entities["positions"])
                    params["position"] = extracted_entities["positions"]

        # Handle castell and status filters for concurs queries (search in JSON data)
        if question_type == QuestionType.CONCURS_RANKING:
            if extracted_entities.get("castells"):
                castell_conditions = []
                for castell in extracted_entities["castells"]:
                    if isinstance(castell, Castell):
                        castell_code = escape_sql_string(castell.castell_code)
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
                        escaped_castell = escape_sql_string(castell)
                        castell_conditions.append(f"""
                            (cr.ronda_1_json LIKE '%"castell": "{escaped_castell}"%' OR 
                             cr.ronda_2_json LIKE '%"castell": "{escaped_castell}"%' OR 
                             cr.ronda_3_json LIKE '%"castell": "{escaped_castell}"%' OR 
                             cr.ronda_4_json LIKE '%"castell": "{escaped_castell}"%' OR 
                             cr.ronda_5_json LIKE '%"castell": "{escaped_castell}"%' OR 
                             cr.ronda_6_json LIKE '%"castell": "{escaped_castell}"%' OR 
                             cr.ronda_7_json LIKE '%"castell": "{escaped_castell}"%' OR 
                             cr.rondes_json LIKE '%"castell": "{escaped_castell}"%')
                        """)
                
                castell_filter = f"AND ({' OR '.join(castell_conditions)})"
                params["castell"] = [c.castell_code if isinstance(c, Castell) else c for c in extracted_entities["castells"]]

            if extracted_entities.get("status"):
                status_conditions = []
                for status in extracted_entities["status"]:
                    # Search for exact status match in JSON (more precise)
                    # Look for "status": "Descarregat" pattern
                    escaped_status = escape_sql_string(status)
                    status_conditions.append(f"""
                        (cr.ronda_1_json LIKE '%"status": "{escaped_status}"%' OR 
                         cr.ronda_2_json LIKE '%"status": "{escaped_status}"%' OR 
                         cr.ronda_3_json LIKE '%"status": "{escaped_status}"%' OR 
                         cr.ronda_4_json LIKE '%"status": "{escaped_status}"%' OR 
                         cr.ronda_5_json LIKE '%"status": "{escaped_status}"%' OR 
                         cr.ronda_6_json LIKE '%"status": "{escaped_status}"%' OR 
                         cr.ronda_7_json LIKE '%"status": "{escaped_status}"%' OR 
                         cr.rondes_json LIKE '%"status": "{escaped_status}"%')
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
            position_filter=position_filter,
            position_select=position_select
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
            
            # Check if no results were found
            if not result:
                raise NoResultsFoundError(NO_RESULTS_MESSAGE)
            
            return result
        except NoResultsFoundError:
            # Re-raise NoResultsFoundError without wrapping it
            raise
        except Exception as e:
            raise Exception(f"Hi ha hagut un error executant la consulta SQL: {e}\nConsulta generada:\n{sql_query}")


# ---- Structured Prompt System ----

@dataclass
class StructuredPrompt:
    """Structured prompt with system, developer, and user components"""
    system_message: str
    developer_message: str
    user_prompt: str


# Base system message shared across all query types
BASE_SYSTEM_MESSAGE = """Ets un expert casteller amb criteri tècnic i rigor històric.
Sempre respons exclusivament en català.
Segueixes estrictament les instruccions de format i sortida."""


# Shared developer instructions (strict rules)
SHARED_DEVELOPER_RULES = """INSTRUCCIONS ESTRICTES (OBLIGATÒRIES):

PROHIBIT (MAI escriure això a la resposta):
- Taules
- Llistes amb guions o punts
- PUNTS/PUNTUACIONS: MAI dir "X punts", "total de X punts", "va aconseguir X punts" - PROHIBIT!
- Pilars de 4 o 5 (Pd4, Pd5, Pde4, Pde5)
- Notes finals o comentaris addicionals
- Donar opinions o valoracions personals
- Referencies a ranking
- Farciment, valoracions finals o conclusions innecesaries (res de "reeixida", "destacada", "impressionant", etc.)

FORMAT:
- Màxim 1-2 paràgrafs curts
- **negreta** només per destacar noms i dates
- Estil telegràfic i objectiu
- Respon de manera breu i directa"""


def get_sql_summary_prompt(query_type: str, question: str, table_str: str) -> StructuredPrompt:
    """
    Retorna un prompt estructurat amb system, developer i user components.
    
    Args:
        query_type: Tipus de consulta SQL
        question: Pregunta de l'usuari
        table_str: Resultats de la consulta en format string
    
    Returns:
        StructuredPrompt amb els tres components separats
    """
    
    # Query-type specific developer instructions
    developer_instructions = {
        "millor_diada": f"""{SHARED_DEVELOPER_RULES}""",

        "millor_castell": f"""{SHARED_DEVELOPER_RULES}""",

        "castell_historia": f"""{SHARED_DEVELOPER_RULES}""",

        "location_actuations": f"""{SHARED_DEVELOPER_RULES}""",

        "first_castell": f"""{SHARED_DEVELOPER_RULES}""",

        "castell_statistics": f"""{SHARED_DEVELOPER_RULES}""",

        "year_summary": f"""{SHARED_DEVELOPER_RULES}""",

        "concurs_ranking": f"""{SHARED_DEVELOPER_RULES}""",

        "concurs_history": f"""{SHARED_DEVELOPER_RULES}""",
    }
    
    # Get developer message for this query type, or use default
    developer_message = developer_instructions.get(query_type, SHARED_DEVELOPER_RULES)
    
    # User prompt with the actual question and data
    user_prompt = f"""Pregunta:
{question}

Resultats:
{table_str}"""

    return StructuredPrompt(
        system_message=BASE_SYSTEM_MESSAGE,
        developer_message=developer_message,
        user_prompt=user_prompt
    )


# Legacy function for backward compatibility (returns single string)
def get_sql_summary_prompt_legacy(query_type: str, question: str, table_str: str) -> str:
    """
    Legacy function that returns a single prompt string.
    Use get_sql_summary_prompt() for the new structured format.
    """
    structured = get_sql_summary_prompt(query_type, question, table_str)
    return f"""{structured.system_message}

{structured.developer_message}

{structured.user_prompt}"""


