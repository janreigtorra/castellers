import json
import re
from datetime import datetime

def clean_castell_string(castell_str):
    """
    Clean castell string by removing '*' and spaces
    """
    if not castell_str:
        return ""
    
    # Remove all '*' and spaces
    cleaned = castell_str.replace('*', '').replace(' ', '')
    return cleaned

def determine_castell_status(castell_str):
    """
    Determine the status of a castell based on suffixes/prefixes
    """
    if not castell_str:
        return ""
    
    # Convert to lowercase for easier matching
    castell_lower = castell_str.lower()
    
    # Check for 'id' or '(id)' at end or beginning
    if castell_lower.endswith('id') or castell_lower.endswith('(id)') or \
       castell_lower.startswith('id') or castell_lower.startswith('(id)'):
        return "Intent desmuntat"
    
    # Check for 'i' or '(i)' at end or beginning
    if castell_lower.endswith('i') or castell_lower.endswith('(i)') or \
       castell_lower.startswith('i') or castell_lower.startswith('(i)'):
        return "Intent"
    
    # Check for 'c' or '(c)' at end
    if castell_lower.endswith('c') or castell_lower.endswith('(c)'):
        return "Carregat"

    # Check for '-' or ''
    if castell_lower.endswith('-') or castell_lower.endswith('—'):
        return ""
    
    # Default case
    return "Descarregat"

def clean_castell_string_post_status(castell_str):
    """
    Clean castell string after removing status indicators
    """
    if not castell_str:
        return ""

    # Remove status indicators
    castell_str = castell_str.replace('(id)', '').replace('(i)', '').replace('(c)', '')
    
    # Change 'de' for 'd'
    castell_str = castell_str.replace('de', 'd')

    # Change 'fa' for 'af'
    castell_str = castell_str.replace('fa', 'af')

   # Change 'ps' for 's'
    castell_str = castell_str.replace('ps', 's')

    # Change 'pd' for 'Pd'
    castell_str = castell_str.replace('pd', 'Pd')

    return castell_str

def process_rondes(rondes_dict):
    """
    Process rondes dictionary and convert to the required format
    """
    processed_rondes = {}
    
    for ronda_key, castell_str in rondes_dict.items():
        if castell_str:  # Only process non-empty strings
            # Clean the castell string
            cleaned_castell = clean_castell_string(castell_str)
            
            # Determine status
            status = determine_castell_status(cleaned_castell)
            
            cleaned_castell_post_status = clean_castell_string_post_status(cleaned_castell)
            # Create the new format
            processed_rondes[ronda_key] = {
                'castell': cleaned_castell_post_status,
                'status': status
            }
        else:
            # Handle empty strings
            processed_rondes[ronda_key] = {
                'castell': '',
                'status': ''
            }
    
    return processed_rondes

def clean_concurs_data(input_file, output_file):
    """
    Main function to clean the concurs data
    """
    # Read the input JSON file (now properly formatted as an array)
    with open(input_file, 'r', encoding='utf-8') as f:
        json_objects = json.load(f)
    
    # Process each edition's results
    for edition in json_objects:
        if 'results' in edition:
            for result in edition['results']:
                if 'rondes' in result:
                    # Process the rondes
                    result['rondes'] = process_rondes(result['rondes'])

        # Fix day 2014 edition
        if edition['any'] == 2014:
            if 'results' in edition:
                for result in edition['results']:
                    # Extract day from colla field pattern like "Colla Name (5/10)"
                    colla_name = result['colla']
                    day_match = re.search(r'\(([^)]+)\)', colla_name)
                    if day_match:
                        day_content = day_match.group(1)
                        result['day'] = day_content
                        # Remove the day part from colla name
                        result['colla'] = re.sub(r'\s*\([^)]+\)', '', colla_name)

    
        # Create field jornada for editions superior 2014
        if edition['any'] >= 2014:
            if 'results' in edition:
                # Extract unique days from all results in this edition
                unique_days = set()
                for result in edition['results']:
                    if 'day' in result:
                        day = result['day']
                        # remove the 'Ds' or 'Dg' from the day
                        day = day.replace('Ds. ', '').replace('Dg. ', '').replace('Ds ', '').replace('Dg ', '')
                        # Normalize day/month format (remove leading zeros)
                        day_parts = day.split('/')
                        if len(day_parts) == 2:
                            day = f"{int(day_parts[0])}/{int(day_parts[1])}"
                        unique_days.add(day)
                
                # Convert days to actual dates and sort them properly
                def day_to_date(day_str):
                    try:
                        # Parse day/month format
                        day, month = day_str.split('/')
                        # Normalize month format (remove leading zeros)
                        month = str(int(month))
                        day = str(int(day))
                        # Create date with the edition year
                        return datetime(edition['any'], int(month), int(day))
                    except:
                        # If parsing fails, return a default date
                        return datetime(edition['any'], 1, 1)
                
                # Sort days by their actual date
                sorted_days = sorted(list(unique_days), key=day_to_date)
                
                # Create mapping from day to jornada
                day_to_jornada = {}
                for i, day in enumerate(sorted_days):
                    if i == 0:  # First day (usually September)
                        day_to_jornada[day] = 'Jornada Torredembarra'
                    elif i == 1:  # Second day (usually Saturday October)
                        day_to_jornada[day] = 'Jornada Dissabte Tarragona'
                    elif i == 2:  # Third day (usually Sunday October)
                        day_to_jornada[day] = 'Jornada Diumenge Tarragona'
                
                # Assign jornada to each result
                for result in edition['results']:
                    if 'day' in result:
                        cleaned_day = result['day'].replace('Ds. ', '').replace('Dg. ', '').replace('Ds ', '').replace('Dg ', '')
                        if cleaned_day in day_to_jornada:
                            result['jornada'] = day_to_jornada[cleaned_day]


    # Save the cleaned data as a JSON array
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_objects, f, ensure_ascii=False, indent=2)
    
    print(f"Cleaned data saved to {output_file}")
    print(f"Processed {len(json_objects)} editions")

if __name__ == "__main__":
    input_file = "../data_basic/concurs/concurs_ranking_preclean.json"
    output_file = "../data_basic/concurs/concurs_ranking_clean.json"
    
    clean_concurs_data(input_file, output_file)
