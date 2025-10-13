import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
import os
import time


edicions = ['I', 'II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX','XXI', 'XXII', 'XXIII', 'XXIV', 'XXV', 'XXVI', 'XXVII', 'XXVIII', 'XXIX']

def clean_text(text):
    """Clean and normalize text content"""
    if not text:
        return ""
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text.strip())
    # Remove common Wikipedia artifacts
    text = text.replace('[editar]', '').replace('[modificar]', '')
    return text

def extract_infobox_data(soup):
    """Extract structured data from Wikipedia infobox"""
    infobox = soup.find('table', {'class': 'infobox'})
    if not infobox:
        return {}
    
    infobox_data = {}
    rows = infobox.find_all('tr')
    
    for row in rows:
        cells = row.find_all(['th', 'td'])
        if len(cells) >= 2:
            key = clean_text(cells[0].get_text())
            value = clean_text(cells[1].get_text())
            if key and value:
                infobox_data[key] = value
        elif len(cells) == 1:
            # Handle single cell rows that might contain important info
            text = clean_text(cells[0].get_text())
            if text and len(text) > 20:
                infobox_data[f'info_{len(infobox_data)}'] = text
    
    return infobox_data

def extract_paragraphs(soup):
    """Extract main content paragraphs from Wikipedia page"""
    paragraphs = []
    
    # Find the main content area
    content_div = soup.find('div', {'class': 'mw-content-ltr'})
    if not content_div:
        content_div = soup.find('div', {'id': 'mw-content-text'})
    
    if content_div:
        # Extract paragraphs from the main content
        para_elements = content_div.find_all('p')
        
        for i, para in enumerate(para_elements):
            text = clean_text(para.get_text())
            if text and len(text) > 30:  # Include shorter paragraphs too
                paragraphs.append({
                    f'info{i+1}': text
                })
        
        # Also extract content from divs that might contain important text
        content_divs = content_div.find_all('div', {'class': 'mw-parser-output'})
        for div in content_divs:
            div_text = clean_text(div.get_text())
            if div_text and len(div_text) > 50:
                paragraphs.append({
                    f'info{len(paragraphs)+1}': div_text
                })
    
    return paragraphs

def extract_page_info(soup, edicio):
    """Extract general page information and text content"""
    page_info = {
        'edicio': edicio,
        'title': '',
        'date': '',
        'location': '',
        'infobox': {},
        'paragraphs': []
    }
    
    # Extract page title
    title_elem = soup.find('h1', {'class': 'firstHeading'})
    if title_elem:
        page_info['title'] = clean_text(title_elem.get_text())
    
    # Extract infobox data
    page_info['infobox'] = extract_infobox_data(soup)
    
    # Extract paragraphs
    page_info['paragraphs'] = extract_paragraphs(soup)
    
    # Look for date information in the page
    date_patterns = [
        r'(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',
        r'(\d{4})',
        r'(\d{1,2}/\d{1,2}/\d{4})'
    ]
    
    page_text = soup.get_text()
    for pattern in date_patterns:
        match = re.search(pattern, page_text)
        if match:
            page_info['date'] = match.group(1)
            break
    
    return page_info

def scrape_edition(edicio):
    """Scrape a single edition of the Concurs de Castells"""
    BASE_URL = f"https://ca.wikipedia.org/wiki/{edicio}_Concurs_de_castells_de_Tarragona"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print(f"Scraping {edicio} edition...")
        response = requests.get(BASE_URL, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract page information and text content
        page_info = extract_page_info(soup, edicio)
        
        print(f"Extracted {len(page_info['paragraphs'])} paragraphs for {edicio}")
        
        return page_info
        
    except requests.RequestException as e:
        print(f"Error scraping {edicio}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error scraping {edicio}: {e}")
        return None

def main():
    """Main function to scrape all editions"""
    all_editions = []
    
    for edicio in edicions:
        edition_data = scrape_edition(edicio)
        if edition_data:
            all_editions.append(edition_data)
        
        # Be respectful to Wikipedia servers
        time.sleep(2)
    
    # Save to JSON file
    output_dir = 'data_basic'
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, 'concurs_de_castells_editions.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_editions, f, ensure_ascii=False, indent=2)
    
    print(f"\nScraping completed! Data saved to {output_file}")
    print(f"Successfully scraped {len(all_editions)} editions")
    
    # Print summary
    for edition in all_editions:
        print(f"\n{edition['edicio']}: {edition['title']}")
        print(f"  Date: {edition['date']}")
        print(f"  Infobox fields: {len(edition['infobox'])}")
        print(f"  Paragraphs extracted: {len(edition['paragraphs'])}")

if __name__ == "__main__":
    main()

