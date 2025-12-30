import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
import os

BASE_URL = "https://castellscat.cat/ca/base-de-dades"

# Configuration
MAX_PAGES = 1000  # Set to 10 for testing, 1000+ for production
OUTPUT_FORMAT = "json"  # "json" or "txt"
OUTPUT_FILE = "../backend/data_basic/castellers_data.json"  # Path to output file

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
})

def parse_date_location(date_location_text):
    """Parse date and location information from the text"""
    # Clean up the text
    text = date_location_text.replace('\n', ' ').strip()
    
    # Try to extract date (DD/MM/YYYY format)
    date_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
    date = date_match.group(1) if date_match else None
    
    # Try to extract time (HH:MM format)
    time_match = re.search(r'(\d{1,2}:\d{2})', text)
    time = time_match.group(1) if time_match else None
    
    # Extract location (everything after the time)
    if time_match:
        location_part = text[time_match.end():].strip()
    elif date_match:
        location_part = text[date_match.end():].strip()
    else:
        location_part = text
    
    # Find the boundary between place and city
    # Cities start with uppercase letters, and there's no space between place and city
    # Look for pattern: lowercase letter immediately followed by uppercase letter
    city_start_index = None
    
    for i in range(len(location_part) - 1):
        current_char = location_part[i]
        next_char = location_part[i + 1]
        
        # Check if current char is lowercase and next char is uppercase
        if current_char.islower() and next_char.isupper():
            city_start_index = i + 1
            break
    
    if city_start_index is not None:
        # Split at the boundary
        place = location_part[:city_start_index].strip()
        city = location_part[city_start_index:].strip()
    else:
        # Fallback: if no boundary found, treat entire string as city
        place = ""
        city = location_part
    
    return {
        "date": date,
        "time": time,
        "place": place,
        "city": city,
        "raw_text": date_location_text
    }

def parse_castell_result(result_text):
    """Parse castell result text to extract castell name and status"""
    # Remove extra whitespace
    text = result_text.strip()
    
    # Extract status in parentheses
    status_match = re.search(r'\(([^)]+)\)', text)
    status = status_match.group(1) if status_match else None
    
    # Extract castell name (everything before the parentheses)
    castell_name = text
    if status_match:
        castell_name = text[:status_match.start()].strip()
    
    return {
        "castell_name": castell_name,
        "status": status,
        "raw_text": result_text
    }

def clean_event_name(event_name):
    """
    Clean event name by detecting concatenated text.
    If we find a lowercase letter immediately followed by an uppercase letter,
    we keep only the part starting from the uppercase letter.
    
    Example:
        'Sant Fèlix a Vilafranca del PenedèsDiada de Sant Fèlix...'
        -> 'Diada de Sant Fèlix...'
    """
    if not event_name:
        return event_name
    
    # Find the pattern: lowercase letter followed by uppercase letter
    # We want to extract everything from the uppercase letter onwards
    match = re.search(r'[a-z]([A-Z].*)', event_name)
    if match:
        # Return the part starting from the uppercase letter
        return match.group(1)
    
    # No pattern found, return original
    return event_name

def event_key(event):
    """Create a unique key for an event to check for duplicates"""
    # Use date, event_name, city, and time to identify unique events
    return (
        event.get("date", ""),
        event.get("event_name", ""),
        event.get("city", ""),
        event.get("time", "")
    )

def load_existing_events(file_path):
    """Load existing events from file if it exists"""
    if os.path.exists(file_path):
        print(f"Loading existing events from {file_path}...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            
            existing_events = existing_data.get("events", [])
            existing_metadata = existing_data.get("metadata", {})
            
            print(f"Found {len(existing_events)} existing events")
            return existing_events, existing_metadata
        except Exception as e:
            print(f"Error loading existing file: {e}")
            print("Starting fresh...")
            return [], {}
    else:
        print(f"File {file_path} does not exist. Starting fresh...")
        return [], {}

# Load existing events if file exists
existing_events, existing_metadata = load_existing_events(OUTPUT_FILE)
existing_event_keys = {event_key(event) for event in existing_events}
print(f"Loaded {len(existing_events)} existing events. Will skip duplicates.")

# Step 1: Get the page to retrieve CSRF token
resp = session.get(BASE_URL)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")
token = soup.find("input", {"name": "_token"})["value"]
print("Got CSRF token:", token)

# Step 2: Build POST data
payload = {
    "_token": token,
    "date_start": "01/09/2025",  # Scrape from September 2025
    "date_end": datetime.now().strftime("%d/%m/%Y"), # New date range: TODAY
    "diada": "",
    "colla[]": "",        
    "castell": "",
    "result": "",
    "city": "",
    "country": "",
    "colles_type": "all",
    "type": "search"
}

# Step 3: Process all pages
all_results = []
page = 1
total_events = 0


while True:
    print(f"Processing page {page}...")
    
    # Add page parameter to payload
    current_payload = payload.copy()
    if page > 1:
        current_payload["page"] = page
    
    # Submit POST request
    resp = session.post(BASE_URL, data=current_payload)
    resp.raise_for_status()
    
    # Parse results
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Extract results from ul.resultats elements 
    result_lists = soup.find_all("ul", class_="resultats")
    print(f"Found {len(result_lists)} events on page {page}")
    
    if len(result_lists) == 0:
        print("No more results found, stopping pagination")
        break
    
    # Process results from this page
    for result_list in result_lists:
        # Get the parent element to find the event info
        event_info = result_list.find_parent("div", class_="element")
        if event_info:
            # Extract event name and date
            event_header = event_info.find("div", class_="element-header")
            event_name_raw = event_header.get_text(strip=True) if event_header else "Unknown Event"
            # Clean the event name to fix concatenated text issues
            event_name = clean_event_name(event_name_raw)
            
            # Extract date and location info
            table_cell = event_info.find("div", class_="table1")
            if table_cell:
                # Clean up the date/location text
                date_location_text = table_cell.get_text(strip=True)
                # Split by common separators and clean up
                parts = date_location_text.replace('\n', ' ').split()
                date_location = ' '.join(parts)
            else:
                date_location = "Unknown Date/Location"
            
            # Parse date and location
            parsed_location = parse_date_location(date_location)
            
            # Extract colla names and their results
            colla_items = result_list.find_all("li")
            colles_data = []
            current_colla = None
            
            for item in colla_items:
                if "colla-name" in item.get("class", []):
                    # New colla found
                    if current_colla:
                        colles_data.append(current_colla)
                    current_colla = {
                        "colla_name": item.get_text(strip=True),
                        "castells": []
                    }
                else:
                    # Castell result for current colla
                    if current_colla:
                        castell_data = parse_castell_result(item.get_text(strip=True))
                        current_colla["castells"].append(castell_data)
            
            # Add the last colla if exists
            if current_colla:
                colles_data.append(current_colla)
            
            # Store the event data in structured format
            event_data = {
                "event_id": f"event_{len(existing_events) + len(all_results) + 1}",
                "event_name": event_name,
                "date": parsed_location["date"],
                "time": parsed_location["time"],
                "place": parsed_location["place"],
                "city": parsed_location["city"],
                "raw_date_location": parsed_location["raw_text"],
                "colles": colles_data,
                "total_colles": len(colles_data),
                "total_castells": sum(len(colla["castells"]) for colla in colles_data),
                "scraped_at": datetime.now().isoformat()
            }
            
            # Check if this event already exists
            event_key_val = event_key(event_data)
            if event_key_val in existing_event_keys:
                print(f"  Skipping duplicate event: {event_name} on {parsed_location['date']} in {parsed_location['city']}")
                continue
            
            # Add to results and track the key
            all_results.append(event_data)
            existing_event_keys.add(event_key_val)
            total_events += 1
    
    # Check if there's a next page
    next_page_link = soup.find("a", {"rel": "next"})
    if not next_page_link:
        print("No next page link found, stopping pagination")
        break
    
    page += 1
    
    # Safety check to prevent infinite loops
    if page > MAX_PAGES:
        print(f"Reached maximum page limit ({MAX_PAGES}), stopping")
        break

print(f"New events found in this scrape: {total_events}")
print(f"Existing events: {len(existing_events)}")

# Merge existing and new events
all_events = existing_events + all_results
total_events_merged = len(all_events)

print(f"Total events after merge: {total_events_merged}")

# Create comprehensive dataset structure with merged data
dataset = {
    "metadata": {
        "scraped_at": datetime.now().isoformat(),
        "total_events": total_events_merged,
        "total_pages_scraped": page - 1,
        "previous_scrape": existing_metadata.get("scraped_at"),
        "events_added_this_run": total_events,
        "search_parameters": {
            "date_start": payload.get("date_start"),
            "date_end": payload.get("date_end"),
            "diada": payload.get("diada"),
            "colla_filter": payload.get("colla[]"),
            "castell": payload.get("castell"),
            "result": payload.get("result"),
            "city": payload.get("city"),
            "country": payload.get("country"),
            "colles_type": payload.get("colles_type")
        },
        "statistics": {
            "events_with_results": len([e for e in all_events if e["total_castells"] > 0]),
            "events_without_results": len([e for e in all_events if e["total_castells"] == 0]),
            "total_colles": sum(e["total_colles"] for e in all_events),
            "total_castells": sum(e["total_castells"] for e in all_events),
            "unique_cities": len(set(e["city"] for e in all_events if e["city"])),
            "unique_colles": len(set(colla["colla_name"] for e in all_events for colla in e["colles"]))
        }
    },
    "events": all_events
}

# Output based on format
if OUTPUT_FORMAT == "json":
    # Ensure directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"Saved structured data to {OUTPUT_FILE}")
    
    # Also save a summary
    summary = {
        "total_events": dataset["metadata"]["total_events"],
        "events_with_results": dataset["metadata"]["statistics"]["events_with_results"],
        "total_castells": dataset["metadata"]["statistics"]["total_castells"],
        "unique_colles": dataset["metadata"]["statistics"]["unique_colles"],
        "unique_cities": dataset["metadata"]["statistics"]["unique_cities"]
    }
    with open("summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("Saved summary to summary.json")
    
else:
    # Legacy text format
    with open("results.txt", "w", encoding="utf-8") as f:
        for event_data in all_results:
            f.write(f"=== {event_data['event_name']} ===\n")
            f.write(f"Date/Location: {event_data['raw_date_location']}\n")
            for colla in event_data['colles']:
                f.write(f"\nColla: {colla['colla_name']}\n")
                for castell in colla['castells']:
                    f.write(f"  - {castell['raw_text']}\n")
            f.write("\n" + "="*50 + "\n\n")
    print("Saved results to results.txt")

print(f"\nDataset Statistics:")
print(f"- Total events: {dataset['metadata']['total_events']}")
print(f"- Events with results: {dataset['metadata']['statistics']['events_with_results']}")
print(f"- Total castells: {dataset['metadata']['statistics']['total_castells']}")
print(f"- Unique colles: {dataset['metadata']['statistics']['unique_colles']}")
print(f"- Unique cities: {dataset['metadata']['statistics']['unique_cities']}")
