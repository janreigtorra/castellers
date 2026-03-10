"""
LLM SQL Query Generator V2 - Simplified Approach

This module uses a general query to fetch all relevant data, then organizes it
based on the query type through post-processing.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import psycopg2
import os
import json
from dotenv import load_dotenv
from .utility_functions import Castell, code_to_name
from .util_dics import GAMMA_CASTELLS
from datetime import datetime
from collections import defaultdict
from itertools import groupby

# Limits for SQL queries and LLM context
SQL_RESULT_LIMIT = 20      # Results shown in frontend table
LLM_CONTEXT_LIMIT = 10     # Results fed to LLM for summarization

# Placeholder message for no results found
NO_RESULTS_MESSAGE = "No he trobat cap resultat a la base de dades referent a la teva pregunta."


def escape_sql_string(value: str) -> str:
    if value is None:
        return value
    return value.replace("'", "''")


def sort_key_by_punts_and_date(row: Dict, punts_key: str = 'punts', date_key: str = 'event_date') -> Tuple:
    """
    Sort key function for sorting by points (descending) then date (ascending).
    
    Args:
        row: Dictionary with punts and date fields
        punts_key: Key for points field (default: 'punts')
        date_key: Key for date field (default: 'event_date')
    
    Returns:
        Tuple for sorting: (-punts, date_tuple)
    """
    punts = row.get(punts_key, 0)
    # For date sorting, convert DD/MM/YYYY to tuple for proper comparison
    date_str = row.get(date_key, '')
    try:
        if date_str:
            day, month, year = date_str.split('/')
            date_tuple = (int(year), int(month), int(day))
        else:
            date_tuple = (0, 0, 0)
    except:
        date_tuple = (0, 0, 0)
    return (-punts, date_tuple)  # Negative punts for descending


def format_castells_fets(castells_list: List[Dict]) -> str:
    """
    Format castells list for display, counting occurrences of pd4, pde4, pd5, pde5.
    
    Args:
        castells_list: List of dicts with 'castell_name' and 'status' keys
    
    Returns:
        Formatted string like "3d8 (Descarregat), 4d8 (Descarregat), 2 X PD4 (Descarregat), 1 X PDE4 (Carregat)"
        (counted pilars appear at the end)
    """
    pilar_types_to_count = {'pd4', 'Pd4', 'pd5', 'Pde5', 'pde4', 'Pde4', 'pde5', 'Pde5'}
    castell_counts = defaultdict(lambda: defaultdict(int))
    other_castells = []
    
    for r in castells_list:
        castell_name = r.get('castell_name', '')
        status = r.get('status', '')
        if castell_name in pilar_types_to_count:
            castell_counts[castell_name][status] += 1
        else:
            other_castells.append(r)
    
    # Format counted pilars
    counted_pilars = []
    for castell_name in sorted(castell_counts.keys()):
        for status, count in sorted(castell_counts[castell_name].items()):
            castell_display = castell_name
            if count > 1:
                counted_pilars.append(f"{count} X {castell_display} ({status})")
            else:
                counted_pilars.append(f"{castell_display} ({status})")
    
    # Format other castells normally
    other_formatted = [f"{r.get('castell_name', '')} ({r.get('status', '')})" for r in other_castells]
    
    # Combine: other castells first, then counted pilars at the end
    return ', '.join(other_formatted + counted_pilars)


class NoResultsFoundError(Exception):
    def __init__(self, message: str = NO_RESULTS_MESSAGE):
        self.message = message
        super().__init__(self.message)


class SQLExecutionError(Exception):
    def __init__(self, message: str = "No he pogut analitzar la pregunta. Torna-ho a intentar amb una pregunta diferent."):
        self.message = message
        super().__init__(self.message)

load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")


class LLMSQLGeneratorV2:
    
    def __init__(self):
        pass
    
    def create_sql_query(self, question: str, entities: Dict, sql_query_type: str = "custom", llm_call_func=None) -> Tuple[str, Dict[str, any]]:

        # Special handling for concurs queries
        if sql_query_type in ["concurs_ranking", "concurs_history"]:
            return self._create_concurs_query(question, entities, sql_query_type, llm_call_func)
        
        # For all other queries, use general query
        return self._create_general_query(question, entities, sql_query_type)
    
    def _create_general_query(self, question: str, entities: Dict, sql_query_type: str) -> Tuple[str, Dict[str, any]]:

        # Build filters based on entities
        params = {}
        filters = []
        
        # Colla filter
        if entities.get("colla"):
            if len(entities["colla"]) == 1:
                filters.append("AND co.name = %(colla_param)s")
                params["colla_param"] = entities["colla"][0]
            else:
                filters.append("AND co.name IN %(colla_param)s")
                params["colla_param"] = tuple(entities["colla"])
        
        # Castell filter
        if entities.get("castells"):
            castell_codes = []
            for castell in entities["castells"]:
                if isinstance(castell, Castell):
                    castell_codes.append(code_to_name(castell.castell_code))
                else:
                    castell_codes.append(code_to_name(castell))
            
            if len(castell_codes) == 1:
                filters.append("AND c.castell_name = %(castell_param)s")
                params["castell_param"] = castell_codes[0]
            else:
                filters.append("AND c.castell_name IN %(castell_param)s")
                params["castell_param"] = tuple(castell_codes)
        
        # Year filter
        if entities.get("anys"):
            if len(entities["anys"]) == 1:
                filters.append("AND EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) = %(year_param)s")
                params["year_param"] = entities["anys"][0]
            else:
                filters.append("AND EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) IN %(year_param)s")
                params["year_param"] = tuple(entities["anys"])
        
        # Location filter
        if entities.get("llocs"):
            if len(entities["llocs"]) == 1:
                filters.append("AND e.city LIKE %(location_param)s")
                params["location_param"] = f"%{entities['llocs'][0]}%"
            else:
                filters.append("AND e.city IN %(location_param)s")
                params["location_param"] = tuple(entities["llocs"])
        
        # Diada filter
        if entities.get("diades"):
            if len(entities["diades"]) == 1:
                filters.append("AND e.name LIKE %(diada_param)s")
                params["diada_param"] = f"%{entities['diades'][0]}%"
            else:
                filters.append("AND e.name IN %(diada_param)s")
                params["diada_param"] = tuple(entities["diades"])
        
        # Status filter
        if entities.get("status"):
            if len(entities["status"]) == 1:
                filters.append("AND c.status = %(status_param)s")
                params["status_param"] = entities["status"][0]
            else:
                filters.append("AND c.status IN %(status_param)s")
                params["status_param"] = tuple(entities["status"])
        
        # Gamma filter
        if entities.get("gamma"):
            gamma_name = entities["gamma"]
            gamma_def = GAMMA_CASTELLS.get(gamma_name, {})
            
            if "specific" in gamma_def:
                specific_castells = gamma_def["specific"]
                specific_castells_lower = [c.lower() for c in specific_castells]
                
                # Create variations for pilars (pd8fm <-> pde8fm)
                specific_castells_variations = set(specific_castells_lower)
                for c in specific_castells_lower:
                    if c.startswith('p') and len(c) > 1 and c[1] == 'd' and 'de' not in c:
                        variation = 'p' + 'de' + c[2:]
                        specific_castells_variations.add(variation)
                    elif c.startswith('p') and 'de' in c:
                        variation = c.replace('de', 'd', 1)
                        specific_castells_variations.add(variation)
                
                filters.append("AND (LOWER(c.castell_name) IN %(gamma_param)s OR LOWER(p.castell_code) IN %(gamma_param)s OR LOWER(p.castell_code_external) IN %(gamma_param)s)")
                params["gamma_param"] = tuple(sorted(specific_castells_variations))
        
        # Build the general query - fetch all relevant columns
        filter_clause = "\n".join(filters) if filters else ""
        
        sql_query = f"""
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
            p.punts_descarregat,
            p.punts_carregat,
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
        {filter_clause}
        ORDER BY e.date DESC, punts DESC
        """
        
        return sql_query, params
    
    def _create_concurs_query(self, question: str, entities: Dict, sql_query_type: str, llm_call_func=None) -> Tuple[str, Dict[str, any]]:
        """
        Create special query for concurs queries.
        Uses concurs and concurs_rankings tables.
        """
        # Build filters based on entities
        params = {}
        filters = []
        
        # Edition filter
        if entities.get("editions"):
            if len(entities["editions"]) == 1:
                filters.append("AND c.edition = %(edition_param)s")
                params["edition_param"] = entities["editions"][0]
            else:
                filters.append("AND c.edition IN %(edition_param)s")
                params["edition_param"] = tuple(entities["editions"])
        
        # Jornada filter
        if entities.get("jornades"):
            if len(entities["jornades"]) == 1:
                filters.append("AND cr.jornada LIKE %(jornada_param)s")
                params["jornada_param"] = f"%{entities['jornades'][0]}%"
            else:
                filters.append("AND cr.jornada IN %(jornada_param)s")
                params["jornada_param"] = tuple(entities["jornades"])
        
        # Colla filter (for concurs, use cr.colla_name)
        if entities.get("colla"):
            if len(entities["colla"]) == 1:
                filters.append("AND cr.colla_name = %(colla_param)s")
                params["colla_param"] = entities["colla"][0]
            else:
                filters.append("AND cr.colla_name IN %(colla_param)s")
                params["colla_param"] = tuple(entities["colla"])
        
        # Position filter
        if entities.get("positions"):
            if entities.get("jornades"):
                # Use posicio_jornada if jornada filter exists
                if len(entities["positions"]) == 1:
                    filters.append("AND cr.posicio_jornada = %(position_param)s")
                    params["position_param"] = entities["positions"][0]
                else:
                    filters.append("AND cr.posicio_jornada IN %(position_param)s")
                    params["position_param"] = tuple(entities["positions"])
            else:
                # Use position if no jornada filter
                if len(entities["positions"]) == 1:
                    filters.append("AND cr.position = %(position_param)s")
                    params["position_param"] = entities["positions"][0]
                else:
                    filters.append("AND cr.position IN %(position_param)s")
                    params["position_param"] = tuple(entities["positions"])
        
        # Year filter (for concurs, use cr.any)
        if entities.get("anys"):
            if len(entities["anys"]) == 1:
                filters.append("AND cr.any = %(year_param)s")
                params["year_param"] = entities["anys"][0]
            else:
                filters.append("AND cr.any IN %(year_param)s")
                params["year_param"] = tuple(entities["anys"])
        
        # Castell filter (search in JSON fields)
        if entities.get("castells") and sql_query_type == "concurs_ranking":
            castell_conditions = []
            for castell in entities["castells"]:
                if isinstance(castell, Castell):
                    castell_code = escape_sql_string(castell.castell_code)
                else:
                    castell_code = escape_sql_string(castell)
                
                # Search in all ronda JSON fields
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
            
            if castell_conditions:
                filters.append(f"AND ({' OR '.join(castell_conditions)})")
        
        # Status filter (search in JSON fields)
        if entities.get("status") and sql_query_type == "concurs_ranking":
            status_conditions = []
            for status in entities["status"]:
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
            
            if status_conditions:
                filters.append(f"AND ({' OR '.join(status_conditions)})")
        
        filter_clause = "\n".join(filters) if filters else ""
        
        # Determine position column based on jornada filter
        position_select = "cr.position AS position"
        if entities.get("jornades"):
            position_select = "cr.posicio_jornada AS position"
        
        # Build the general concurs query
        sql_query = f"""
        SELECT 
            c.edition,
            c.title,
            c.plaça,
            {position_select},
            cr.colla_name,
            cr.total_points,
            cr.jornada,
            cr.any,
            cr.ronda_1_json,
            cr.ronda_2_json,
            cr.ronda_3_json,
            cr.ronda_4_json,
            cr.ronda_5_json,
            cr.ronda_6_json,
            cr.ronda_7_json,
            cr.rondes_json
        FROM concurs c
        JOIN concurs_rankings cr ON c.id = cr.concurs_fk
        WHERE 1=1
        {filter_clause}
        ORDER BY cr.position ASC
        """
        
        return sql_query, params
    
    def execute_sql_query(self, sql_query: str, params: Dict[str, any]) -> List:        
        try:
            conn_start = datetime.now()
            conn = psycopg2.connect(DATABASE_URL)
            conn_time = (datetime.now() - conn_start).total_seconds() * 1000
            if conn_time > 10:
                print(f"[TIMING] SQL connection: {conn_time:.2f}ms")
            
            exec_start = datetime.now()
            cursor = conn.cursor()
            
            query_preview = sql_query[:200] + "..." if len(sql_query) > 200 else sql_query
            print(f"[SQL] Executing query: {query_preview}")
            print(f"[SQL] Params: {params}")
            
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            exec_time = (datetime.now() - exec_start).total_seconds() * 1000
            print(f"[TIMING] SQL query execution: {exec_time:.2f}ms (rows: {len(rows)})")
            
            if exec_time > 1000:
                print(f"[WARNING] SQL query took {exec_time:.2f}ms - consider optimization!")
            
            convert_start = datetime.now()
            columns = [desc[0] for desc in cursor.description]
            result = [dict(zip(columns, row)) for row in rows]
            convert_time = (datetime.now() - convert_start).total_seconds() * 1000
            if convert_time > 10:
                print(f"[TIMING] SQL result conversion: {convert_time:.2f}ms")
            
            conn.close()
            
            if not result:
                raise NoResultsFoundError(NO_RESULTS_MESSAGE)
            
            return result
        except NoResultsFoundError:
            raise
        except Exception as e:
            print(f"[SQL ERROR] Technical error: {e}\nQuery: {sql_query[:200]}...")
            raise SQLExecutionError("No he pogut analitzar la pregunta. Torna-ho a intentar amb una pregunta diferent.")
    
    def organize_results(self, raw_results: List[Dict], sql_query_type: str, entities: Dict) -> List[Dict]:

        if sql_query_type == "custom":
            # For custom queries, organize with aggregations
            return self._organize_custom_query(raw_results, entities)
        
        # Route to specific organizer function
        organizer_map = {
            "millor_diada": self._organize_millor_diada,
            "millor_castell": self._organize_millor_castell,
            "castell_historia": self._organize_castell_historia,
            "castells_list": self._organize_castells_list,
            "location_actuations": self._organize_location_actuations,
            "first_castell": self._organize_first_castell,
            "castell_statistics": self._organize_castell_statistics,
            "year_summary": self._organize_year_summary,
            "colles": self._organize_colles,
            "concurs_ranking": self._organize_concurs_ranking,
            "concurs_history": self._organize_concurs_history,
        }
        
        organizer_func = organizer_map.get(sql_query_type)
        if organizer_func:
            return organizer_func(raw_results, entities)
        
        # Fallback: return top results
        return raw_results[:SQL_RESULT_LIMIT]
    
    # ============================================================
    # POST-PROCESSING ORGANIZERS (DRAFT - TO BE IMPLEMENTED)
    # ============================================================
    
    def _organize_millor_diada(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        # Sort by (event_id, colla_id) for grouping, then by tipus and punts within groups
        raw_results.sort(key=lambda r: (r['event_id'], r['colla_id'], r.get('tipus', ''), -r.get('punts', 0)))
        
        # Group by event_id and colla_id
        aggregated_results = []
        for (event_id, colla_id), group in groupby(raw_results, key=lambda r: (r['event_id'], r['colla_id'])):
            group_list = list(group)
            if not group_list:
                continue
            
            # Get event metadata from first row
            first_row = group_list[0]
            
            # Separate castells and pilars (already sorted by points descending due to sort key)
            castells = [r for r in group_list if r.get('tipus') == 'castell']
            pilars = [r for r in group_list if r.get('tipus') == 'pilar']
            
            # For points calculation: take top 3 castells + top 1 pilar
            selected_for_points = castells[:3] + (pilars[:1] if pilars else [])
            
            if not selected_for_points:
                continue
            
            # Calculate total points from selected castells
            total_punts = sum(r.get('punts', 0) for r in selected_for_points)
            
            # For castells_fets: include ALL castells and pilars (sorted by points)
            all_castells = castells + pilars
            castells_fets = format_castells_fets(all_castells)
            
            aggregated_results.append({
                'event_name': first_row['event_name'],
                'event_date': first_row['event_date'],
                'colla_name': first_row['colla_name'],
                'event_city': first_row['event_city'],
                'castells_fets': castells_fets,
                'total_punts': total_punts
            })
        
        # Sort by total_punts (descending) and add ranking
        aggregated_results.sort(key=lambda x: x['total_punts'], reverse=True)
        
        # Add ranking
        return [
            {**result, 'ranking': rank}
            for rank, result in enumerate(aggregated_results[:SQL_RESULT_LIMIT], start=1)
        ]
    
    def _organize_millor_castell(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        # Sort by punts DESC, then date ASC
        sorted_results = sorted(raw_results, key=sort_key_by_punts_and_date)
        
        # Add gamma_filtrada if gamma filter was used
        gamma_name = entities.get('gamma')
        
        # Format results
        formatted_results = []
        for r in sorted_results[:SQL_RESULT_LIMIT]:
            result = {
                'castell_name': r['castell_name'],
                'event_name': r['event_name'],
                'date': r['event_date'],
                'colla_name': r['colla_name'],
                'city': r['event_city'],
                'status': r['status']
            }
            
            # Add gamma_filtrada if gamma was used
            if gamma_name:
                result['gamma_filtrada'] = gamma_name
            
            formatted_results.append(result)
        
        return formatted_results
    
    def _organize_castell_historia(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        
        # Check if colla filter was used
        has_colla_filter = bool(entities.get('colla'))
        
        # Group by (castell_name, status) and optionally by colla_name
        groups = defaultdict(lambda: {
            'castell_name': None,
            'status': None,
            'colla_name': None,  # Only used if has_colla_filter
            'occurrences': [],
            'colles': set(),  # For aggregation when no colla filter
            'cities': set(),
            'dates': []
        })
        
        # Group raw results
        for row in raw_results:
            castell_name = row['castell_name']
            status = row['status']
            colla_name = row['colla_name']
            city = row.get('event_city', '')
            date = row.get('event_date', '')
            
            # Create group key
            if has_colla_filter:
                key = (castell_name, status, colla_name)
            else:
                key = (castell_name, status)
            
            group = groups[key]
            group['castell_name'] = castell_name
            group['status'] = status
            if has_colla_filter:
                group['colla_name'] = colla_name
            
            group['occurrences'].append(row)
            if not has_colla_filter:
                group['colles'].add(colla_name)
            if city:
                group['cities'].add(city)
            if date:
                group['dates'].append(date)
        
        # Convert groups to results
        aggregated_results = []
        for key, group in groups.items():
            count_occurrences = len(group['occurrences'])
            
            # Get first and last date (convert DD/MM/YYYY to comparable format for sorting)
            def parse_date(date_str):
                try:
                    if date_str:
                        day, month, year = date_str.split('/')
                        return (int(year), int(month), int(day))
                    return (0, 0, 0)
                except:
                    return (0, 0, 0)
            
            dates_sorted = sorted(group['dates'], key=parse_date)
            first_date = dates_sorted[0] if dates_sorted else None
            last_date = dates_sorted[-1] if dates_sorted else None
            
            # Build result
            result = {
                'castell_name': group['castell_name'],
                'status': group['status'],
                'count_occurrences': count_occurrences,
                'first_date': first_date,
                'last_date': last_date,
                'cities': ', '.join(sorted(group['cities'])) if group['cities'] else None
            }
            
            # Add colla_name or colles based on filter
            if has_colla_filter:
                result['colla_name'] = group['colla_name']
            else:
                result['colles'] = ', '.join(sorted(group['colles'])) if group['colles'] else None
            
            # Add gamma_filtrada if gamma was used
            if entities.get('gamma'):
                result['gamma_filtrada'] = entities['gamma']
            
            aggregated_results.append(result)
        
        # Sort by count_occurrences DESC, castell_name, status
        aggregated_results.sort(key=lambda r: (-r['count_occurrences'], r['castell_name'], r['status']))
        
        return aggregated_results[:SQL_RESULT_LIMIT]
    
    def _organize_castells_list(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        """
        Organize results for 'castells_list' query type.
        
        Expected output: gamma_filtrada, castell_name, status, diades, places, cities, colles, first_date
        """
        # Group by castell_name and status
        groups = defaultdict(lambda: {
            'castell_name': None,
            'status': None,
            'diades': set(),
            'places': set(),
            'cities': set(),
            'colles': set(),
            'dates': [],
            'max_punts': 0
        })
        
        for row in raw_results:
            key = (row['castell_name'], row['status'])
            group = groups[key]
            group['castell_name'] = row['castell_name']
            group['status'] = row['status']
            
            if row.get('event_name'):
                group['diades'].add(row['event_name'])
            if row.get('event_place'):
                group['places'].add(row['event_place'])
            if row.get('event_city'):
                group['cities'].add(row['event_city'])
            if row.get('colla_name'):
                group['colles'].add(row['colla_name'])
            if row.get('event_date'):
                group['dates'].append(row['event_date'])
            
            punts = row.get('punts', 0)
            if punts > group['max_punts']:
                group['max_punts'] = punts
        
        # Convert to results
        results = []
        for key, group in groups.items():
            # Parse dates for sorting
            def parse_date(d):
                try:
                    day, month, year = d.split('/')
                    return (int(year), int(month), int(day))
                except:
                    return (0, 0, 0)
            
            dates_sorted = sorted(group['dates'], key=parse_date)
            first_date = dates_sorted[0] if dates_sorted else None
            
            result = {
                'castell_name': group['castell_name'],
                'status': group['status'],
                'diades': ', '.join(sorted(group['diades'])) if group['diades'] else None,
                'places': ', '.join(sorted(group['places'])) if group['places'] else None,
                'cities': ', '.join(sorted(group['cities'])) if group['cities'] else None,
                'colles': ', '.join(sorted(group['colles'])) if group['colles'] else None,
                'first_date': first_date,
                '_sort_key': (-group['max_punts'], parse_date(first_date) if first_date else (0, 0, 0), group['castell_name'])
            }
            
            if entities.get('gamma'):
                result['gamma_filtrada'] = entities['gamma']
            
            results.append(result)
        
        # Sort by max_punts DESC, first_date ASC, castell_name ASC
        results.sort(key=lambda r: r['_sort_key'])
        for r in results:
            del r['_sort_key']
        
        return results[:SQL_RESULT_LIMIT]
    
    def _organize_location_actuations(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        """
        Organize results for 'location_actuations' query type.
        
        Expected output: event_name, date, city, colla_name, castells_fets
        Similar to millor_diada: group by event, take top 3 castells + top 1 pilar for points calculation
        """
        # Sort for grouping (same logic as millor_diada)
        raw_results.sort(key=lambda r: (r['event_id'], r['colla_id'], r.get('tipus', ''), -r.get('punts', 0)))
        
        aggregated_results = []
        for (event_id, colla_id), group in groupby(raw_results, key=lambda r: (r['event_id'], r['colla_id'])):
            group_list = list(group)
            if not group_list:
                continue
            
            first_row = group_list[0]
            castells = [r for r in group_list if r.get('tipus') == 'castell']
            pilars = [r for r in group_list if r.get('tipus') == 'pilar']
            
            # For points: top 3 castells + top 1 pilar
            selected_for_points = castells[:3] + (pilars[:1] if pilars else [])
            if not selected_for_points:
                continue
            
            total_punts = sum(r.get('punts', 0) for r in selected_for_points)
            
            # For display: all castells and pilars
            all_castells = castells + pilars
            castells_fets = ', '.join(f"{r['castell_name']} ({r['status']})" for r in sorted(all_castells, key=lambda x: x.get('punts', 0), reverse=True))
            
            aggregated_results.append({
                'event_name': first_row['event_name'],
                'date': first_row['event_date'],
                'city': first_row['event_city'],
                'colla_name': first_row['colla_name'],
                'castells_fets': castells_fets,
                '_total_punts': total_punts,
                '_date_sort': sort_key_by_punts_and_date({'event_date': first_row['event_date']})[1]
            })
        
        # Sort by total_punts DESC, date DESC
        aggregated_results.sort(key=lambda r: (-r['_total_punts'], r['_date_sort']), reverse=True)
        for r in aggregated_results:
            del r['_total_punts'], r['_date_sort']
        
        return aggregated_results[:SQL_RESULT_LIMIT]
    
    def _organize_first_castell(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        """
        Organize results for 'first_castell' query type.
        
        Expected output: castell_name, status, event_name, date, colla_name, city
        Find first occurrence per (castell_name, status)
        """
        # Sort by castell_name, status, then date ASC
        raw_results.sort(key=lambda r: (r['castell_name'], r['status'], sort_key_by_punts_and_date({'event_date': r.get('event_date', '')})[1]))
        
        # Group by (castell_name, status) and take first occurrence
        seen = set()
        results = []
        for row in raw_results:
            key = (row['castell_name'], row['status'])
            if key not in seen:
                seen.add(key)
                results.append({
                    'castell_name': row['castell_name'],
                    'status': row['status'],
                    'event_name': row['event_name'],
                    'date': row['event_date'],
                    'colla_name': row['colla_name'],
                    'city': row['event_city']
                })
        
        # Sort by date ASC
        results.sort(key=lambda r: sort_key_by_punts_and_date({'event_date': r['date']})[1])
        
        return results[:SQL_RESULT_LIMIT]
    
    def _organize_castell_statistics(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        """
        Organize results for 'castell_statistics' query type.
        
        Expected output: castell_name, cops_descarregat, cops_carregat, cops_intent_desmuntat, cops_intent, 
                        primera_data_descarregat, primera_data_carregat, colles_descarregat, colles_carregat, etc.
        """
        # Group by castell_name
        groups = defaultdict(lambda: {
            'castell_name': None,
            'descarregat': [],
            'carregat': [],
            'intent_desmuntat': [],
            'intent': [],
            'punts_descarregat': 0,
            'punts_carregat': 0
        })
        
        for row in raw_results:
            castell_name = row['castell_name']
            status = row['status']
            group = groups[castell_name]
            group['castell_name'] = castell_name
            
            # Get points from first row (should be same for all rows with same castell_name)
            if row.get('punts_descarregat'):
                group['punts_descarregat'] = row['punts_descarregat']
            if row.get('punts_carregat'):
                group['punts_carregat'] = row['punts_carregat']
            
            # Categorize by status
            if status == 'Descarregat':
                group['descarregat'].append(row)
            elif status == 'Carregat':
                group['carregat'].append(row)
            elif status == 'Intent desmuntat':
                group['intent_desmuntat'].append(row)
            elif status == 'Intent':
                group['intent'].append(row)
        
        # Convert to results
        results = []
        for castell_name, group in groups.items():
            def parse_date(d):
                try:
                    day, month, year = d.split('/')
                    return (int(year), int(month), int(day))
                except:
                    return (9999, 12, 31)
            
            # Get first dates per status
            desc_dates = sorted([r['event_date'] for r in group['descarregat'] if r.get('event_date')], key=parse_date)
            carr_dates = sorted([r['event_date'] for r in group['carregat'] if r.get('event_date')], key=parse_date)
            
            # Get distinct colles per status
            colles_desc = set(r['colla_name'] for r in group['descarregat'] if r.get('colla_name'))
            colles_carr = set(r['colla_name'] for r in group['carregat'] if r.get('colla_name'))
            colles_intent = set(r['colla_name'] for r in group['intent_desmuntat'] + group['intent'] if r.get('colla_name'))
            
            # Aggregate colles lists (truncate to 400 chars like SQL SUBSTR)
            def truncate_colles(colles_set, max_chars=400):
                colles_list = sorted(colles_set)
                result = ', '.join(colles_list)
                if len(result) > max_chars:
                    # Find last complete colla name that fits
                    truncated = result[:max_chars]
                    last_comma = truncated.rfind(',')
                    if last_comma > 0:
                        return truncated[:last_comma]
                    return truncated
                return result
            
            results.append({
                'castell_name': castell_name,
                'cops_descarregat': len(group['descarregat']),
                'cops_carregat': len(group['carregat']),
                'cops_intent_desmuntat': len(group['intent_desmuntat']),
                'cops_intent': len(group['intent']),
                'primera_data_descarregat': desc_dates[0] if desc_dates else None,
                'primera_data_carregat': carr_dates[0] if carr_dates else None,
                'colles_descarregat': len(colles_desc),
                'colles_carregat': len(colles_carr),
                'colles_intentat': len(colles_intent),
                'total_colles_carregat_o_descarregat': len(colles_desc | colles_carr),
                'primeres_colles_descarregat': truncate_colles(colles_desc),
                'primeres_colles_carregat': truncate_colles(colles_carr),
                'primeres_colles_intentat': truncate_colles(colles_intent),
                'punts_descarregat': group['punts_descarregat'],
                'punts_carregat': group['punts_carregat']
            })
        
        return results[:SQL_RESULT_LIMIT]
    
    def _organize_year_summary(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        """
        Organize results for 'year_summary' query type.
        
        Expected output: gamma_filtrada, colla_name, num_actuacions, num_castells, castells_descarregats, etc.
        """
        # Group by colla_name
        groups = defaultdict(lambda: {
            'colla_name': None,
            'events': set(),
            'castells': [],
            'total_punts': 0
        })
        
        for row in raw_results:
            colla_name = row['colla_name']
            group = groups[colla_name]
            group['colla_name'] = colla_name
            
            if row.get('event_id'):
                group['events'].add(row['event_id'])
            
            group['castells'].append(row)
            group['total_punts'] += row.get('punts', 0)
        
        # Convert to results
        results = []
        for colla_name, group in groups.items():
            status_counts = {
                'Descarregat': 0,
                'Carregat': 0,
                'Intent desmuntat': 0,
                'Intent': 0
            }
            
            for castell in group['castells']:
                status = castell.get('status')
                if status in status_counts:
                    status_counts[status] += 1
            
            result = {
                'colla_name': colla_name,
                'num_actuacions': len(group['events']),
                'num_castells': len(group['castells']),
                'castells_descarregats': status_counts['Descarregat'],
                'castells_carregats': status_counts['Carregat'],
                'castells_intent_desmuntat': status_counts['Intent desmuntat'],
                'castells_intent': status_counts['Intent'],
                '_total_punts': group['total_punts']
            }
            
            if entities.get('gamma'):
                result['gamma_filtrada'] = entities['gamma']
            
            results.append(result)
        
        # Sort by total points DESC
        results.sort(key=lambda r: -r['_total_punts'])
        for r in results:
            del r['_total_punts']
        
        return results[:SQL_RESULT_LIMIT]
    
    def _organize_colles(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        """
        Organize results for 'colles' query type.
        
        Expected output: depends on filters (diada/location vs castell/gamma)
        - If diada/location: colla_name, diada, lloc, any, castells_fets
        - If castell/gamma: colla_name, castell_name, cops_descarregat, cops_carregat, etc.
        - Default: variant 1 (diada/location format)
        """
        has_diada_or_location = bool(entities.get("diades") or entities.get("llocs"))
        has_castell_or_gamma = bool(entities.get("castells") or entities.get("gamma"))
        
        if has_diada_or_location or (not has_diada_or_location and not has_castell_or_gamma):
            # Variant 1: Group by colla, event - show colla, diada, lloc, any, castells_fets
            raw_results.sort(key=lambda r: (r['colla_name'], r['event_id'], -r.get('punts', 0)))
            
            aggregated_results = []
            for (colla_name, event_id), group in groupby(raw_results, key=lambda r: (r['colla_name'], r['event_id'])):
                group_list = list(group)
                if not group_list:
                    continue
                
                first_row = group_list[0]
                
                # Extract year from date
                year = None
                if first_row.get('event_date'):
                    try:
                        day, month, year_str = first_row['event_date'].split('/')
                        year = int(year_str)
                    except:
                        pass
                
                # Aggregate castells sorted by points
                castells_sorted = sorted(group_list, key=lambda r: r.get('punts', 0), reverse=True)
                castells_fets = ', '.join(f"{r['castell_name']} ({r['status']})" for r in castells_sorted)
                
                aggregated_results.append({
                    'colla_name': colla_name,
                    'diada': first_row['event_name'],
                    'lloc': first_row['event_city'],
                    'any': year,
                    'castells_fets': castells_fets,
                    '_sort_key': (-year if year else 0, sort_key_by_punts_and_date({'event_date': first_row.get('event_date', '')})[1])
                })
            
            # Sort by year DESC, date DESC
            aggregated_results.sort(key=lambda r: r['_sort_key'], reverse=True)
            for r in aggregated_results:
                del r['_sort_key']
            
            return aggregated_results[:SQL_RESULT_LIMIT]
        
        elif has_castell_or_gamma:
            # Variant 2: Group by colla and castell - show colla, castell, statistics per status
            groups = defaultdict(lambda: {
                'colla_name': None,
                'castell_name': None,
                'descarregat': [],
                'carregat': [],
                'intent': [],
                'intent_desmuntat': []
            })
            
            for row in raw_results:
                key = (row['colla_name'], row['castell_name'])
                group = groups[key]
                group['colla_name'] = row['colla_name']
                group['castell_name'] = row['castell_name']
                
                status = row.get('status')
                if status == 'Descarregat':
                    group['descarregat'].append(row)
                elif status == 'Carregat':
                    group['carregat'].append(row)
                elif status == 'Intent':
                    group['intent'].append(row)
                elif status == 'Intent desmuntat':
                    group['intent_desmuntat'].append(row)
            
            results = []
            for key, group in groups.items():
                def parse_date(d):
                    try:
                        day, month, year = d.split('/')
                        return (int(year), int(month), int(day))
                    except:
                        return (9999, 12, 31)
                
                desc_dates = sorted([r['event_date'] for r in group['descarregat'] if r.get('event_date')], key=parse_date)
                carr_dates = sorted([r['event_date'] for r in group['carregat'] if r.get('event_date')], key=parse_date)
                all_dates = sorted([r['event_date'] for r in group['descarregat'] + group['carregat'] + group['intent'] + group['intent_desmuntat'] if r.get('event_date')], key=parse_date)
                
                results.append({
                    'colla_name': group['colla_name'],
                    'castell_name': group['castell_name'],
                    'cops_descarregat': len(group['descarregat']),
                    'cops_carregat': len(group['carregat']),
                    'cops_intent': len(group['intent']),
                    'cops_intent_desmuntat': len(group['intent_desmuntat']),
                    'primera_data_descarregat': desc_dates[0] if desc_dates else None,
                    'primera_data_carregat': carr_dates[0] if carr_dates else None,
                    'primera_data': all_dates[0] if all_dates else None,
                    '_sort_key': (all_dates[0] if all_dates else (0, 0, 0), group['colla_name'], group['castell_name'])
                })
            
            # Sort by max date DESC, colla_name, castell_name
            results.sort(key=lambda r: r['_sort_key'], reverse=True)
            for r in results:
                del r['_sort_key']
            
            return results[:SQL_RESULT_LIMIT]
        
        # Fallback (shouldn't happen)
        return raw_results[:SQL_RESULT_LIMIT]
    
    def _organize_concurs_ranking(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        """
        Organize results for 'concurs_ranking' query type.
        
        Expected output: edition, title, plaça, position, colla_name, total_points, jornada,
                        primera_ronda, segona_ronda, tercera_ronda, quarta_ronda, cinquena_ronda
        """
        results = []
        for row in raw_results:
            # Extract castell and status from JSON fields for each ronda
            def extract_ronda(ronda_json_str):
                if not ronda_json_str or ronda_json_str.strip() == '':
                    return None
                try:
                    ronda_data = json.loads(ronda_json_str)
                    castell = ronda_data.get('castell', '')
                    status = ronda_data.get('status', '')
                    if castell and status:
                        return f"{castell} ({status})"
                    return None
                except:
                    return None
            
            result = {
                'edition': row.get('edition'),
                'title': row.get('title'),
                'plaça': row.get('plaça'),
                'position': row.get('position'),
                'colla_name': row.get('colla_name'),
                'total_points': row.get('total_points'),
                'jornada': row.get('jornada'),
                'primera_ronda': extract_ronda(row.get('ronda_1_json')),
                'segona_ronda': extract_ronda(row.get('ronda_2_json')),
                'tercera_ronda': extract_ronda(row.get('ronda_3_json')),
                'quarta_ronda': extract_ronda(row.get('ronda_4_json')),
                'cinquena_ronda': extract_ronda(row.get('ronda_5_json'))
            }
            
            results.append(result)
        
        # Results are already sorted by position ASC from SQL query
        return results[:SQL_RESULT_LIMIT]
    
    def _organize_concurs_history(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        """
        Organize results for 'concurs_history' query type.
        
        Expected output: any, jornada, colles_participants, colla_guanyadora, punts_guanyador,
                        castells_r1_descarregats, castells_r2_descarregats, etc.
        """
        # Group by (any, jornada)
        groups = defaultdict(lambda: {
            'any': None,
            'jornada': None,
            'rankings': []
        })
        
        for row in raw_results:
            key = (row.get('any'), row.get('jornada'))
            group = groups[key]
            group['any'] = row.get('any')
            group['jornada'] = row.get('jornada')
            group['rankings'].append(row)
        
        # Process each group
        results = []
        for key, group in groups.items():
            # Sort by total_points DESC to get winner
            rankings_sorted = sorted(group['rankings'], key=lambda r: r.get('total_points', 0), reverse=True)
            
            colla_guanyadora = rankings_sorted[0].get('colla_name') if rankings_sorted else None
            punts_guanyador = rankings_sorted[0].get('total_points') if rankings_sorted else None
            colles_participants = len(set(r.get('colla_name') for r in group['rankings'] if r.get('colla_name')))
            
            # Extract castells descarregats from each ronda
            def extract_castells_descarregats(ronda_num):
                castells = set()
                for ranking in group['rankings']:
                    ronda_json = ranking.get(f'ronda_{ronda_num}_json')
                    if ronda_json and ronda_json.strip():
                        try:
                            ronda_data = json.loads(ronda_json)
                            if ronda_data.get('status') == 'Descarregat':
                                castell = ronda_data.get('castell')
                                if castell:
                                    castells.add(castell)
                        except:
                            pass
                return ', '.join(sorted(castells)) if castells else None
            
            result = {
                'any': group['any'],
                'jornada': group['jornada'],
                'colles_participants': colles_participants,
                'colla_guanyadora': colla_guanyadora,
                'punts_guanyador': punts_guanyador,
                'castells_r1_descarregats': extract_castells_descarregats(1),
                'castells_r2_descarregats': extract_castells_descarregats(2),
                'castells_r3_descarregats': extract_castells_descarregats(3),
                'castells_r4_descarregats': extract_castells_descarregats(4),
                'castells_r5_descarregats': extract_castells_descarregats(5)
            }
            
            results.append(result)
        
        # Sort by any DESC, jornada ASC
        results.sort(key=lambda r: (-r['any'] if r['any'] else 0, r['jornada'] or ''))
        
        return results[:SQL_RESULT_LIMIT]
    
    def _organize_custom_query(self, raw_results: List[Dict], entities: Dict) -> List[Dict]:
        """
        Organize results for 'custom' query type.
        
        Returns:
        - Top 10 results sorted by punts DESC, date ASC (punts removed from output)
        - Aggregations (top 5 each):
          1. By castell+status: castell, status, first_date, first_diada, count
          2. By colla+year: colla, top_5_castells, best_diada, num_diades, num_castells
          3. By diada+colla: colla, castells_fets, date, location
        """
        # Sort all results by punts DESC, date ASC
        sorted_results = sorted(raw_results, key=sort_key_by_punts_and_date)
        
        # Get top 10 results and remove punts field and IDs
        # IDs to exclude: event_id, colla_id, castell_id
        top_results = []
        for row in sorted_results[:10]:
            result_row = {k: v for k, v in row.items() 
                          if k not in ['punts', 'punts_descarregat', 'punts_carregat', 
                                      'event_id', 'colla_id', 'castell_id']}
            top_results.append(result_row)
        
        # Build aggregations if entity is not filtered
        aggregations = []
        
        # 1. Aggregate by castell AND status (if castell is not an entity filter)
        if not entities.get("castells"):
            castell_groups = defaultdict(lambda: {
                'castell_name': None,
                'status': None,
                'occurrences': [],
                'first_date': None,
                'first_diada': None
            })
            
            for row in sorted_results:
                castell_name = row.get('castell_name')
                status = row.get('status')
                if castell_name and status:
                    key = (castell_name, status)
                    group = castell_groups[key]
                    group['castell_name'] = castell_name
                    group['status'] = status
                    group['occurrences'].append(row)
                    
                    # Track first occurrence (by date)
                    if not group['first_date'] or sort_key_by_punts_and_date({'event_date': row.get('event_date', '')})[1] < sort_key_by_punts_and_date({'event_date': group['first_date'] or ''})[1]:
                        group['first_date'] = row.get('event_date')
                        group['first_diada'] = row.get('event_name')
            
            # Get top 5 by points (max punts), then date
            top_castells = sorted(
                castell_groups.values(),
                key=lambda g: (
                    -max((r.get('punts', 0) for r in g['occurrences']), default=0),
                    sort_key_by_punts_and_date({'event_date': g['first_date'] or ''})[1]
                )
            )[:5]
            
            for group in top_castells:
                aggregations.append({
                    '_is_aggregation': True,
                    'aggregation_type': 'castell',
                    'castell': group['castell_name'],
                    'status': group['status'],
                    'first_date': group['first_date'],
                    'first_diada': group['first_diada'],
                    'count': len(group['occurrences'])
                })
        
        # 2. Aggregate by colla AND year (if colla is not an entity filter)
        if not entities.get("colla"):
            colla_year_groups = defaultdict(lambda: {
                'colla_name': None,
                'year': None,
                'occurrences': [],
                'events': set()
            })
            
            for row in sorted_results:
                colla_name = row.get('colla_name')
                if colla_name:
                    # Extract year from date
                    year = None
                    if row.get('event_date'):
                        try:
                            day, month, year_str = row['event_date'].split('/')
                            year = int(year_str)
                        except:
                            pass
                    
                    if year:
                        key = (colla_name, year)
                        group = colla_year_groups[key]
                        group['colla_name'] = colla_name
                        group['year'] = year
                        group['occurrences'].append(row)
                        if row.get('event_id'):
                            group['events'].add(row['event_id'])
            
            # Get top 5 by max points, then date
            top_colla_years = sorted(
                colla_year_groups.values(),
                key=lambda g: (
                    -max((r.get('punts', 0) for r in g['occurrences']), default=0),
                    sort_key_by_punts_and_date({'event_date': min((r.get('event_date', '') for r in g['occurrences'] if r.get('event_date')), default='')})[1]
                )
            )[:5]
            
            for group in top_colla_years:
                # Get top 5 castells by points
                castells_sorted = sorted(group['occurrences'], key=lambda r: r.get('punts', 0), reverse=True)
                top_5_castells = [
                    f"{r['castell_name']} ({r['status']})"
                    for r in castells_sorted[:5]
                ]
                
                # Find best diada (top 3 castells + top 1 pilar per event)
                event_groups = defaultdict(lambda: {'castells': [], 'pilars': []})
                for r in group['occurrences']:
                    event_id = r.get('event_id')
                    if event_id:
                        tipus = r.get('tipus', '')
                        if tipus == 'castell':
                            event_groups[event_id]['castells'].append(r)
                        elif tipus == 'pilar':
                            event_groups[event_id]['pilars'].append(r)
                
                best_diada = None
                best_total_punts = 0
                for event_id, event_data in event_groups.items():
                    castells = sorted(event_data['castells'], key=lambda r: r.get('punts', 0), reverse=True)[:3]
                    pilars = sorted(event_data['pilars'], key=lambda r: r.get('punts', 0), reverse=True)[:1]
                    total = sum(r.get('punts', 0) for r in castells + pilars)
                    if total > best_total_punts:
                        best_total_punts = total
                        # Get diada name from first row
                        if castells or pilars:
                            first_row = (castells + pilars)[0]
                            best_diada = first_row.get('event_name')
                
                aggregations.append({
                    '_is_aggregation': True,
                    'aggregation_type': 'colla',
                    'colla': group['colla_name'],
                    'year': group['year'],
                    'top_5_castells': ', '.join(top_5_castells),
                    'best_diada': best_diada,
                    'num_diades': len(group['events']),
                    'num_castells': len(group['occurrences'])
                })
        
        # 3. Aggregate by diada AND colla (if diada is not an entity filter)
        if not entities.get("diades"):
            diada_colla_groups = defaultdict(lambda: {
                'diada_name': None,
                'colla_name': None,
                'occurrences': [],
                'event_id': None,
                'date': None,
                'location': None
            })
            
            for row in sorted_results:
                diada_name = row.get('event_name')
                colla_name = row.get('colla_name')
                if diada_name and colla_name:
                    key = (diada_name, colla_name)
                    group = diada_colla_groups[key]
                    group['diada_name'] = diada_name
                    group['colla_name'] = colla_name
                    group['occurrences'].append(row)
                    if not group['event_id']:
                        group['event_id'] = row.get('event_id')
                        group['date'] = row.get('event_date')
                        group['location'] = row.get('event_city')
            
            # Get top 5 by max points, then date
            top_diada_colles = sorted(
                diada_colla_groups.values(),
                key=lambda g: (
                    -max((r.get('punts', 0) for r in g['occurrences']), default=0),
                    sort_key_by_punts_and_date({'event_date': g['date'] or ''})[1]
                )
            )[:5]
            
            for group in top_diada_colles:
                # Aggregate castells sorted by points
                castells_sorted = sorted(group['occurrences'], key=lambda r: r.get('punts', 0), reverse=True)
                castells_fets = ', '.join(f"{r['castell_name']} ({r['status']})" for r in castells_sorted)
                
                aggregations.append({
                    '_is_aggregation': True,
                    'aggregation_type': 'diada',
                    'colla': group['colla_name'],
                    'castells_fets': castells_fets,
                    'date': group['date'],
                    'location': group['location']
                })
        
        # Return structured result with separate tables
        # Each table will have a _table_type identifier for frontend formatting
        result = []
        
        # Table 1: Top 10 results
        if top_results:
            for row in top_results:
                row['_table_type'] = 'top_results'
            result.extend(top_results)
        
        # Table 2: Aggregations by castell+status
        castell_aggregations = [a for a in aggregations if a.get('aggregation_type') == 'castell']
        if castell_aggregations:
            for row in castell_aggregations:
                row['_table_type'] = 'castell_aggregations'
            result.extend(castell_aggregations)
        
        # Table 3: Aggregations by colla+year
        colla_aggregations = [a for a in aggregations if a.get('aggregation_type') == 'colla']
        if colla_aggregations:
            for row in colla_aggregations:
                row['_table_type'] = 'colla_aggregations'
            result.extend(colla_aggregations)
        
        # Table 4: Aggregations by diada+colla
        diada_aggregations = [a for a in aggregations if a.get('aggregation_type') == 'diada']
        if diada_aggregations:
            for row in diada_aggregations:
                row['_table_type'] = 'diada_aggregations'
            result.extend(diada_aggregations)
        
        return result
    
    def get_llm_context_limit(self, sql_query_type: str) -> int:
        """
        Get the LLM context limit for a specific query type.
        """
        # Map query types to their context limits
        limits = {
            "millor_diada": 5,
            "millor_castell": 10,
            "castell_historia": 15,
            "castells_list": 20,
            "location_actuations": 8,
            "first_castell": 15,
            "castell_statistics": 5,
            "year_summary": 15,
            "concurs_ranking": 24,
            "concurs_history": 24,
            "colles": 20,
            "custom": LLM_CONTEXT_LIMIT,
        }
        return limits.get(sql_query_type, LLM_CONTEXT_LIMIT)


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
- Referencia a Pde4
- Notes finals o comentaris addicionals
- Donar opinions o valoracions personals
- Referencies a ranking
- Farciment, valoracions finals o conclusions innecesaries (res de "reeixida", "destacada", "impressionant", etc.)

FORMAT:
- Màxim 1-2 paràgrafs curts
- **negreta** només per destacar noms i dates
- Estil telegràfic i objectiu
- Respon de manera breu i directa"""


def get_sql_summary_prompt(
    query_type: str, 
    question: str, 
    table_str: str,
    previous_question: str = None,
    previous_response: str = None,
    previous_context_max_chars: int = 200
) -> StructuredPrompt:
    """
    Retorna un prompt estructurat amb system, developer i user components.
    
    Args:
        query_type: Tipus de consulta SQL
        question: Pregunta de l'usuari
        table_str: Resultats de la consulta en format string
        previous_question: Pregunta anterior (opcional, per context de seguiment)
        previous_response: Resposta anterior (opcional, per context de seguiment)
        previous_context_max_chars: Màxim de caràcters a mostrar de la resposta anterior
    
    Returns:
        StructuredPrompt amb els tres components separats
    """
    
    # Query-type specific developer instructions
    developer_instructions = {
        "millor_diada": f"""{SHARED_DEVELOPER_RULES}""",
        "millor_castell": f"""{SHARED_DEVELOPER_RULES}""",
        "castell_historia": f"""{SHARED_DEVELOPER_RULES}""",
        "castells_list": f"""{SHARED_DEVELOPER_RULES}""",
        "location_actuations": f"""{SHARED_DEVELOPER_RULES}""",
        "first_castell": f"""{SHARED_DEVELOPER_RULES}""",
        "castell_statistics": f"""{SHARED_DEVELOPER_RULES}""",
        "year_summary": f"""{SHARED_DEVELOPER_RULES}""",
        "concurs_ranking": f"""{SHARED_DEVELOPER_RULES}""",
        "concurs_history": f"""{SHARED_DEVELOPER_RULES}""",
        "colles": f"""{SHARED_DEVELOPER_RULES}""",
    }
    
    # Get developer message for this query type, or use default
    developer_message = developer_instructions.get(query_type, SHARED_DEVELOPER_RULES)
    
    # Build previous context section
    previous_context_str = ""
    if previous_question and previous_response:
        truncated_resp = previous_response[:previous_context_max_chars]
        if len(previous_response) > previous_context_max_chars:
            truncated_resp += "..."
        truncated_q = previous_question[:150]
        if len(previous_question) > 150:
            truncated_q += "..."
        previous_context_str = f"""CONTEXT ANTERIOR de l'últim missatge de la conversa (pot ser rellevant a l'hora d'entendre la pregunta actual):
- Pregunta: "{truncated_q}"
- Resposta: "{truncated_resp}"

"""
    
    # User prompt with the actual question and data
    user_prompt = f"""{previous_context_str}Pregunta actual:
{question}

Resultats:
{table_str}"""

    return StructuredPrompt(
        system_message=BASE_SYSTEM_MESSAGE,
        developer_message=developer_message,
        user_prompt=user_prompt
    )

