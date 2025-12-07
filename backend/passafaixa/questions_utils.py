import random
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from passafaixa.db_pool import get_db_connection

load_dotenv()

# Probability distribution constants
PROB_YEARS_2016_2025 = 0.45  # 45% total probability
PROB_YEARS_2005_2015 = 0.25  # 25% total probability
PROB_YEARS_1990_2004 = 0.20  # 20% total probability
PROB_YEARS_1960_1989 = 0.10  # 10% total probability

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")


def get_random_year(min_year: int = 1960, max_year: int = 2025, excluded_years: set = {2020, 2021}) -> str:

    # Define year range
    start_year = min_year
    end_year = max_year
    
    # Define year ranges
    years_2016_2025 = [y for y in range(2016, end_year + 1) if y not in excluded_years and y >= start_year and y <= end_year]
    years_2005_2015 = [y for y in range(2005, 2016) if y not in excluded_years and y >= start_year and y <= end_year]
    years_1990_2004 = [y for y in range(1990, 2005) if y not in excluded_years and y >= start_year and y <= end_year]
    years_1960_1989 = [y for y in range(start_year, 1990) if y not in excluded_years and y >= start_year and y <= end_year]
    
    # Create list of all valid years
    all_years = years_1960_1989 + years_1990_2004 + years_2005_2015 + years_2016_2025
    
    # Calculate weights: distribute probability evenly within each range
    weights = []
    for year in all_years:
        if min_year <= year <= max_year and year in years_2016_2025:
            # Distribute 45% probability evenly across years in this range
            weight = PROB_YEARS_2016_2025 / len(years_2016_2025)
        elif min_year <= year <= max_year and year in years_2005_2015:
            # Distribute 25% probability evenly across years in this range
            weight = PROB_YEARS_2005_2015 / len(years_2005_2015)
        elif min_year <= year <= max_year and year in years_1990_2004:
            # Distribute 20% probability evenly across years in this range
            weight = PROB_YEARS_1990_2004 / len(years_1990_2004)
        elif min_year <= year <= max_year and year not in excluded_years and year in years_1960_1989:
            # Distribute 10% probability evenly across years in this range
            weight = PROB_YEARS_1960_1989 / len(years_1960_1989)
        else:
            weight = 0  # Should not happen
        
        weights.append(weight)
    
    # Select a year based on weighted probability
    selected_year = random.choices(all_years, weights=weights, k=1)[0]
    
    return str(selected_year)


def get_random_colla(year: str = None) -> str:
    """
    Get a random colla from json_colles.json file, applying boost weighting.
    If year is provided, filters by colles that were active in that year.
    
    Args:
        year: Optional year as a string (e.g., "2013"). If None, gets overall.
    
    Returns:
        str: Name of a random colla, weighted by boost value
    
    Example:
        Boost values determine selection probability. The weight is calculated as (boost + 1):
        
    """
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    json_file = script_dir / "json_colles.json"
    
    try:
        # Load JSON data
        with open(json_file, "r", encoding="utf-8") as f:
            colles_data = json.load(f)
        
        # Filter by year if provided
        if year:
            year_int = int(year)
            filtered_colles = [
                colla for colla in colles_data
                if colla["min_year"] <= year_int <= colla["max_year"]
            ]
        else:
            filtered_colles = colles_data
        
        if not filtered_colles:
            # Fallback if no colles match the year
            return "Castellers de Vilafranca"
        
        # Extract colla names and weights
        colla_names = [colla["colla_name"] for colla in filtered_colles]
        weights = [colla["boost"] for colla in filtered_colles]
        
        # Select a random colla based on weighted probability
        # random.choices uses weights to determine selection probability
        selected_colla = random.choices(colla_names, weights=weights, k=1)[0]
        
        return selected_colla
        
    except FileNotFoundError:
        print(f"Error: {json_file} not found")
        return "Castellers de Vilafranca"
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        return "Castellers de Vilafranca"
    except Exception as e:
        print(f"Error getting random colla: {e}")
        return "Castellers de Vilafranca"


def get_random_colla_query(year: str = None) -> str:
    """
    Get a random colla that had at least 10 events.
    If year is provided, filters by that year. Otherwise, gets colles overall.
    
    Args:
        year: Optional year as a string (e.g., "2013"). If None or empty, gets overall.
    
    Returns:
        str: Name of a random colla that had at least 10 events
    """
    if not DATABASE_URL:
        # Fallback if database is not configured
        return "Castellers de Vilafranca"
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
        
        # Query to find colles with at least 10 events
        # If year is provided, filter by year; otherwise get overall
        if year:
            # Query with year filter
            cur.execute("""
                SELECT c.name, COUNT(e.id) as event_count
                FROM colles c
                JOIN event_colles ec ON c.id = ec.colla_fk
                JOIN events e ON ec.event_fk = e.id
                WHERE EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) = %s::integer
                GROUP BY c.id, c.name
                HAVING COUNT(e.id) >= 10
            """, (year,))
        else:
            # Query without year filter - get overall
            cur.execute("""
                SELECT c.name, COUNT(e.id) as event_count
                FROM colles c
                JOIN event_colles ec ON c.id = ec.colla_fk
                JOIN events e ON ec.event_fk = e.id
                GROUP BY c.id, c.name
                HAVING COUNT(e.id) >= 10
            """)
        
            rows = cur.fetchall()
            cur.close()
            
            if not rows:
                # Fallback if no colles found with 10+ events
                # Try to get any colles (with or without year filter)
                with get_db_connection() as conn2:
                    cur2 = conn2.cursor()
            
                    if year:
                        cur2.execute("""
                            SELECT DISTINCT c.name
                            FROM colles c
                            JOIN event_colles ec ON c.id = ec.colla_fk
                            JOIN events e ON ec.event_fk = e.id
                            WHERE EXTRACT(YEAR FROM TO_DATE(e.date, 'DD/MM/YYYY')) = %s::integer
                            LIMIT 50
                        """, (year,))
                    else:
                        cur2.execute("""
                            SELECT DISTINCT c.name
                            FROM colles c
                            JOIN event_colles ec ON c.id = ec.colla_fk
                            JOIN events e ON ec.event_fk = e.id
                            LIMIT 50
                        """)
                    
                    rows = cur2.fetchall()
                    cur2.close()
                    
                    if not rows:
                        # Ultimate fallback
                        return "Castellers de Vilafranca"
            
            # Extract colla names from results
            colles = [row[0] for row in rows]
            
            # Return a random colla with equal probability
            return random.choice(colles)
        
    except Exception as e:
        # Fallback on error
        year_str = year if year else "overall"
        print(f"Error getting random colla for year {year_str}: {e}")
        return "Castellers de Vilafranca"