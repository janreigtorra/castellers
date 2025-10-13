import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re
import time
import os
from urllib.parse import urljoin, urlparse
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CollesScraper:
    def __init__(self):
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Enhanced headers to avoid blocking
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
        self.base_url = "https://www.portalcasteller.cat"
        self.colles_url = "https://www.portalcasteller.cat/v2/colles/"
        self.colles_data = []
    
    def make_request(self, url, timeout=30, max_retries=3):
        """Make a request with retry logic and better error handling"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Making request to {url} (attempt {attempt + 1}/{max_retries})")
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1} for {url}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} attempts failed for {url}")
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for {url}: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    raise
        
    def get_colla_id_from_url(self, url):
        """Extract colla ID from URL like /v2/colles/colles-res/?colla=45&ActType=3cp"""
        match = re.search(r'colla=(\d+)', url)
        return match.group(1) if match else None
    
    def parse_location_and_diada(self, location_text):
        """Parse location text to separate city from diada information"""
        if not location_text:
            return "", ""
        
        # Clean up the text
        text = location_text.strip()
        
        # Look for the pattern where a city (lowercase ending) is immediately followed by a diada (uppercase starting)
        # Pattern: lowercase letter immediately followed by uppercase letter
        city_end_index = None
        
        for i in range(len(text) - 1):
            current_char = text[i]
            next_char = text[i + 1]
            
            # Check if current char is lowercase and next char is uppercase
            if current_char.islower() and next_char.isupper():
                city_end_index = i + 1
                break
        
        if city_end_index is not None:
            # Split at the boundary
            city = text[:city_end_index].strip()
            diada = text[city_end_index:].strip()
        else:
            # Fallback: if no boundary found, treat entire string as city
            city = text
            diada = ""
        
        return city, diada
    
    def scrape_wikipedia_info(self, wikipedia_url):
        """Scrape comprehensive information from Wikipedia page"""
        try:
            logger.info(f"Scraping Wikipedia: {wikipedia_url}")
            response = self.make_request(wikipedia_url, timeout=30)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract comprehensive info
            info = {
                "wikipedia_url": wikipedia_url,
                "title": "",
                "description": "",
                "founded": "",
                "location": "",
                "website": "",
                "instagram": "",
                "twitter": "",
                "youtube": "",
                "facebook": "",
                "history": "",
                "achievements": "",
                "info_wikipedia": [],
                "sections": {},
                "best_castells": [],
                "wiki_stats": {},
                "external_links": []
            }
            
            # Get title
            title_elem = soup.find('h1', {'class': 'firstHeading'})
            if title_elem:
                info["title"] = title_elem.get_text(strip=True)
            
            # Get main content area - look for mw-content-text div first, then fallback to mw-parser-output
            content_div = soup.find('div', {'id': 'mw-content-text'})
            if not content_div:
                content_div = soup.find('div', {'class': 'mw-parser-output'})
            
            if not content_div:
                return info
            
            # Extract only meaningful text chunks from the content div
            info_wikipedia = []
            
            # Get all paragraphs, but filter out references and navigation
            paragraphs = content_div.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                # Filter out references, citations, and navigation
                if (len(text) > 50 and 
                    not text.startswith('↑') and 
                    not text.startswith('[') and
                    not 'Consulta:' in text and
                    not 'Arxivat' in text and
                    not 'Wayback Machine' in text and
                    not 'PDF' in text and
                    not text.startswith('•')):
                    info_wikipedia.append(text)
            
            # Get headings and their content, but stop at References section
            headings = content_div.find_all(['h2', 'h3', 'h4', 'h5', 'h6'])
            for heading in headings:
                heading_text = heading.get_text(strip=True)
                
                # Stop processing if we reach References section
                if heading_text.lower() in ['referències', 'references', 'referencias', 'vegeu també', 'enllaços externs']:
                    break
                    
                if heading_text and heading_text not in ['Referències', 'Vegeu també', 'Enllaços externs']:
                    info_wikipedia.append(f"## {heading_text}")
                    
                    # Get content after this heading until next heading
                    current = heading.find_next_sibling()
                    while current and current.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        # Stop if we encounter References section
                        if current.name == 'div' and current.get('class') and 'reflist' in current.get('class'):
                            break
                        if current.name == 'h2' and current.get_text(strip=True).lower() in ['referències', 'references', 'referencias', 'vegeu també', 'enllaços externs']:
                            break
                            
                        if current.name == 'p':
                            text = current.get_text(strip=True)
                            if (text and len(text) > 50 and 
                                not text.startswith('↑') and 
                                not text.startswith('[') and
                                not 'Consulta:' in text and
                                not 'Arxivat' in text and
                                not 'Wayback Machine' in text):
                                info_wikipedia.append(text)
                        elif current.name == 'ul':
                            # Extract list items, but filter out navigation
                            items = current.find_all('li')
                            for item in items:
                                text = item.get_text(strip=True)
                                if (text and len(text) > 30 and
                                    not text.startswith('•')):
                                    info_wikipedia.append(f"• {text}")
                        current = current.find_next_sibling()
            
            # Remove duplicates while preserving order
            seen = set()
            unique_chunks = []
            for chunk in info_wikipedia:
                if chunk not in seen:
                    seen.add(chunk)
                    unique_chunks.append(chunk)
            
            info["info_wikipedia"] = unique_chunks
            
            # Get description from first paragraph
            if paragraphs:
                info["description"] = paragraphs[0].get_text(strip=True)
            
            # Extract all sections, but stop at References section
            headings = content_div.find_all(['h2', 'h3', 'h4'])
            for heading in headings:
                section_title = heading.get_text(strip=True)
                
                # Stop processing if we reach References section
                if section_title.lower() in ['referències', 'references', 'referencias']:
                    break
                    
                section_content = []
                
                # Get content until next heading
                current = heading.find_next_sibling()
                while current and current.name not in ['h1', 'h2', 'h3', 'h4']:
                    # Stop if we encounter References section
                    if current.name == 'div' and current.get('class') and 'reflist' in current.get('class'):
                        break
                    if current.name == 'h2' and current.get_text(strip=True).lower() in ['referències', 'references', 'referencias']:
                        break
                        
                    if current.name == 'p':
                        text = current.get_text(strip=True)
                        if text:
                            section_content.append(text)
                    elif current.name == 'ul':
                        # Extract list items
                        items = current.find_all('li')
                        for item in items:
                            text = item.get_text(strip=True)
                            if text:
                                section_content.append(f"• {text}")
                    current = current.find_next_sibling()
                
                if section_content:
                    info["sections"][section_title] = section_content
            
            # Extract comprehensive infobox data
            infobox = soup.find('table', {'class': 'infobox'})
            if infobox:
                # Get infobox caption/title
                caption = infobox.find('caption')
                if caption:
                    info["wiki_stats"]["title"] = caption.get_text(strip=True)
                
                # Extract all key-value pairs from infobox
                rows = infobox.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        key = th.get_text(strip=True).strip()
                        value = td.get_text(strip=True).strip()
                        
                        # Store all infobox data in wiki_stats
                        if key and value:
                            info["wiki_stats"][key] = value
                        
                        # Also extract specific fields for backward compatibility
                        key_lower = key.lower()
                        if 'founded' in key_lower or 'creat' in key_lower or 'fundat' in key_lower or 'any' in key_lower:
                            info["founded"] = value
                        elif 'location' in key_lower or 'ubicació' in key_lower or 'lloc' in key_lower or 'ciutat' in key_lower:
                            info["location"] = value
                        elif 'website' in key_lower or 'web' in key_lower or 'lloc web' in key_lower:
                            link = td.find('a')
                            if link:
                                info["website"] = link.get('href', '')
                
                # Extract social media links from infobox
                links = infobox.find_all('a')
                for link in links:
                    href = link.get('href', '')
                    if 'facebook.com' in href:
                        info["facebook"] = href
                    elif 'instagram.com' in href:
                        info["instagram"] = href
                    elif 'twitter.com' in href or 'x.com' in href:
                        info["twitter"] = href
                    elif 'youtube.com' in href:
                        info["youtube"] = href
            
            # Extract specific sections
            if "Història" in info["sections"]:
                info["history"] = ' '.join(info["sections"]["Història"])[:2000]
            elif "History" in info["sections"]:
                info["history"] = ' '.join(info["sections"]["History"])[:2000]
            
            # Look for achievements or notable events
            achievement_sections = ["Fets destacats", "Achievements", "Premis", "Awards", "Reconeixements"]
            for section in achievement_sections:
                if section in info["sections"]:
                    info["achievements"] = ' '.join(info["sections"][section])[:1500]
                    break
            
            # Extract best castells mentioned throughout the text
            all_text = ' '.join(info_wikipedia).lower()
            castell_patterns = [
                r'(\d+ de \d+)',  # Pattern like "2 de 7", "4 de 8"
                r'(\d+d\d+)',     # Pattern like "2d7", "4d8"
                r'(pilar de \d+)', # Pattern like "pilar de 5"
                r'(pd\d+)',       # Pattern like "pd5"
                r'(\d+ de \d+ amb)', # Pattern like "4 de 7 amb"
                r'(\d+ de \d+ aixecat)', # Pattern like "3 de 7 aixecat"
            ]
            
            for pattern in castell_patterns:
                matches = re.findall(pattern, all_text)
                for match in matches:
                    if match not in info["best_castells"]:
                        info["best_castells"].append(match)
            
            
            # Extract external links
            ext_links_section = soup.find('h2', string=re.compile(r'Enllaços externs|External links'))
            if ext_links_section:
                current = ext_links_section.find_next_sibling()
                while current and current.name not in ['h1', 'h2']:
                    if current.name == 'ul':
                        links = current.find_all('a')
                        for link in links:
                            href = link.get('href', '')
                            text = link.get_text(strip=True)
                            if href and text:
                                info["external_links"].append({
                                    "url": href,
                                    "text": text
                                })
                    current = current.find_next_sibling()
            
            return info
            
        except Exception as e:
            logger.error(f"Error scraping Wikipedia {wikipedia_url}: {str(e)}")
            return {
                "wikipedia_url": wikipedia_url,
                "error": str(e)
            }
    
    def scrape_colla_detail(self, colla_id, colla_name, colla_basic=None):
        """Scrape detailed information from individual colla page"""
        try:
            detail_url = f"{self.base_url}/v2/colles/colles-res/?colla={colla_id}&ActType=3cp"
            logger.info(f"Scraping colla detail: {colla_name} (ID: {colla_id})")
            
            response = self.make_request(detail_url, timeout=30)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Initialize colla data
            colla_data = {
                "colla_id": colla_id,
                "colla_name": colla_name,
                "detail_url": detail_url,
                "logo_url": "",
                "basic_info": {
                    "description": "",
                    "founded": "",
                    "location": "",
                    "website": "",
                    "instagram": "",
                    "twitter": "",
                    "youtube": "",
                    "facebook": ""
                },
                "wikipedia": {
                    "url": "",
                    "title": "",
                    "description": "",
                    "history": "",
                    "achievements": "",
                    "info_wikipedia": [],
                    "sections": {},
                    "best_castells_wiki": [],
                    "wiki_stats": {},
                    "external_links": []
                },
                "performance": {
                    "first_actuacio": "",
                    "last_actuacio": "",
                    "best_actuacions": [],
                    "best_castells": []
                },
                "scraped_at": datetime.now().isoformat()
            }
            
            # Extract logo from the specific structure
            logo_img = soup.find('img', {'src': re.compile(r'images/colles/')})
            if logo_img:
                colla_data["logo_url"] = urljoin(self.base_url, logo_img.get('src', ''))
            
            # Extract social media links from the specific format
            # Look for the div with social media links
            social_div = soup.find('div', style='vertical-align:middle; line-height:100%')
            if social_div:
                links = social_div.find_all('a')
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # Check parent text to identify type
                    parent_text = link.parent.get_text() if link.parent else ""
                    
                    if 'Web:' in parent_text:
                        colla_data["basic_info"]["website"] = href
                    elif 'Instagram:' in parent_text:
                        colla_data["basic_info"]["instagram"] = href
                    elif 'Twitter:' in parent_text:
                        colla_data["basic_info"]["twitter"] = href
                    elif 'Youtube:' in parent_text:
                        colla_data["basic_info"]["youtube"] = href
                    elif 'Viquipèdia:' in parent_text or 'wikipedia' in href.lower():
                        colla_data["wikipedia"]["url"] = href
                        # Scrape Wikipedia info
                        if href:
                            logger.info(f"Scraping Wikipedia for {colla_name}: {href}")
                            wiki_info = self.scrape_wikipedia_info(href)
                            # Merge Wikipedia info into the wikipedia section
                            if wiki_info and "error" not in wiki_info:
                                colla_data["wikipedia"].update({
                                    "title": wiki_info.get("title", ""),
                                    "description": wiki_info.get("description", ""),
                                    "history": wiki_info.get("history", ""),
                                    "achievements": wiki_info.get("achievements", ""),
                                    "info_wikipedia": wiki_info.get("info_wikipedia", []),
                                    "sections": wiki_info.get("sections", {}),
                                    "best_castells_wiki": wiki_info.get("best_castells", []),
                                    "wiki_stats": wiki_info.get("wiki_stats", {}),
                                    "external_links": wiki_info.get("external_links", [])
                                })
                                # Also update basic info from Wikipedia
                                if wiki_info.get("founded"):
                                    colla_data["basic_info"]["founded"] = wiki_info["founded"]
                                if wiki_info.get("location"):
                                    colla_data["basic_info"]["location"] = wiki_info["location"]
                                if wiki_info.get("facebook"):
                                    colla_data["basic_info"]["facebook"] = wiki_info["facebook"]
            
            # Also check if we have Wikipedia URL from the main page
            if not colla_data["wikipedia"]["url"] and "wikipedia" in colla_basic:
                wikipedia_url = colla_basic["wikipedia"]
                colla_data["wikipedia"]["url"] = wikipedia_url
                logger.info(f"Using Wikipedia URL from social links for {colla_name}: {wikipedia_url}")
                wiki_info = self.scrape_wikipedia_info(wikipedia_url)
                # Merge Wikipedia info into the wikipedia section
                if wiki_info and "error" not in wiki_info:
                    colla_data["wikipedia"].update({
                        "title": wiki_info.get("title", ""),
                        "description": wiki_info.get("description", ""),
                        "history": wiki_info.get("history", ""),
                        "achievements": wiki_info.get("achievements", ""),
                        "info_wikipedia": wiki_info.get("info_wikipedia", []),
                        "sections": wiki_info.get("sections", {}),
                        "best_castells_wiki": wiki_info.get("best_castells", []),
                        "wiki_stats": wiki_info.get("wiki_stats", {}),
                        "external_links": wiki_info.get("external_links", [])
                    })
                    # Also update basic info from Wikipedia
                    if wiki_info.get("founded"):
                        colla_data["basic_info"]["founded"] = wiki_info["founded"]
                    if wiki_info.get("location"):
                        colla_data["basic_info"]["location"] = wiki_info["location"]
                    if wiki_info.get("facebook"):
                        colla_data["basic_info"]["facebook"] = wiki_info["facebook"]
            
            # Extract first and last actuació dates
            text_content = soup.get_text()
            first_match = re.search(r'Primera actuació registrada:\s*(\d{2}/\d{2}/\d{4})', text_content)
            if first_match:
                colla_data["performance"]["first_actuacio"] = first_match.group(1)
            
            last_match = re.search(r'Última actuació registrada:\s*(\d{2}/\d{2}/\d{4})', text_content)
            if last_match:
                colla_data["performance"]["last_actuacio"] = last_match.group(1)
            
            # Extract best actuacions table
            actuacions_table = soup.find('table', class_='dades')
            if actuacions_table:
                rows = actuacions_table.find_all('tr')
                for row in rows[2:]:  # Skip header rows
                    cells = row.find_all('td')
                    if len(cells) >= 5:
                        try:
                            rank = cells[0].get_text(strip=True)
                            date = cells[1].get_text(strip=True)
                            location_info = cells[2].get_text(strip=True)
                            actuacio = cells[3].get_text(strip=True)
                            points = cells[4].get_text(strip=True)
                            
                            if rank.isdigit():  # Only process data rows
                                # Parse location to separate city from diada
                                location, diada = self.parse_location_and_diada(location_info)
                                
                                colla_data["performance"]["best_actuacions"].append({
                                    "rank": int(rank),
                                    "date": date,
                                    "location": location,
                                    "diada": diada,
                                    "actuacio": actuacio,
                                    "points": int(points) if points.isdigit() else 0
                                })
                        except (ValueError, IndexError):
                            continue
            
            # Extract best castells table
            castells_tables = soup.find_all('table', class_='dades')
            if len(castells_tables) > 1:
                castells_table = castells_tables[1]  # Second table is usually castells
                rows = castells_table.find_all('tr')
                for row in rows[2:]:  # Skip header rows
                    cells = row.find_all('td')
                    if len(cells) >= 5:
                        try:
                            castell_name = cells[0].get_text(strip=True)
                            descarregats = cells[1].get_text(strip=True)
                            carregats = cells[2].get_text(strip=True)
                            intents = cells[3].get_text(strip=True)
                            intents_descarregats = cells[4].get_text(strip=True)
                            
                            if castell_name and castell_name != 'Castell':  # Skip header
                                colla_data["performance"]["best_castells"].append({
                                    "castell_name": castell_name,
                                    "descarregats": int(descarregats) if descarregats.isdigit() else 0,
                                    "carregats": int(carregats) if carregats.isdigit() else 0,
                                    "intents": int(intents) if intents.isdigit() else 0,
                                    "intents_descarregats": int(intents_descarregats) if intents_descarregats.isdigit() else 0
                                })
                        except (ValueError, IndexError):
                            continue
            
            # Clean up empty fields
            def clean_empty_fields(data):
                if isinstance(data, dict):
                    return {k: clean_empty_fields(v) for k, v in data.items() if v != "" and v != [] and v != {}}
                elif isinstance(data, list):
                    return [clean_empty_fields(item) for item in data if item != "" and item != [] and item != {}]
                else:
                    return data
            
            colla_data = clean_empty_fields(colla_data)
            
            return colla_data
            
        except Exception as e:
            logger.error(f"Error scraping colla detail {colla_name} (ID: {colla_id}): {str(e)}")
            return {
                "colla_id": colla_id,
                "colla_name": colla_name,
                "error": str(e),
                "scraped_at": datetime.now().isoformat()
            }
    
    def scrape_main_page(self):
        """Scrape the main colles page to get list of all colles"""
        try:
            logger.info("Scraping main colles page...")
            response = self.make_request(self.colles_url, timeout=30)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all colla rows in the table
            colla_rows = soup.find_all('tr')
            colles_found = 0
            
            for row in colla_rows:
                # Look for colla name in h3 tag
                name_elem = row.find('h3')
                if not name_elem:
                    continue
                
                colla_name = name_elem.get_text(strip=True)
                if not colla_name:
                    continue
                
                # Extract colla ID from the +Info button
                info_button = row.find('input', {'value': '+Info'})
                if not info_button:
                    continue
                
                onclick = info_button.get('onclick', '')
                colla_id_match = re.search(r'GoToInfoColla\((\d+)\)', onclick)
                if not colla_id_match:
                    continue
                
                colla_id = colla_id_match.group(1)
                
                # Extract logo URL
                logo_img = row.find('img', {'src': re.compile(r'images/colles/')})
                logo_url = ""
                if logo_img:
                    logo_url = urljoin(self.base_url, logo_img.get('src', ''))
                
                # Extract social media links
                social_links = {}
                links = row.find_all('a')
                for link in links:
                    href = link.get('href', '')
                    title = link.get('title', '').lower()
                    
                    if 'instagram' in href or 'instagram' in title:
                        social_links['instagram'] = href
                    elif 'twitter' in href or 'twitter' in title:
                        social_links['twitter'] = href
                    elif 'youtube' in href or 'youtube' in title:
                        social_links['youtube'] = href
                    elif 'wikipedia' in href or 'wikipedia' in title:
                        social_links['wikipedia'] = href
                    elif 'http' in href and 'portalcasteller' not in href:
                        social_links['website'] = href
                
                # Store basic colla info
                colla_basic = {
                    "colla_id": colla_id,
                    "colla_name": colla_name,
                    "logo_url": logo_url,
                    "scraped_at": datetime.now().isoformat()
                }
                
                # Add social links directly to colla_basic to avoid duplication
                for key, value in social_links.items():
                    if value:  # Only add non-empty values
                        colla_basic[key] = value
                
                self.colles_data.append(colla_basic)
                colles_found += 1
                
                logger.info(f"Found colla: {colla_name} (ID: {colla_id})")
            
            logger.info(f"Found {colles_found} colles on main page")
            return colles_found
            
        except Exception as e:
            logger.error(f"Error scraping main page: {str(e)}")
            return 0
    
    def scrape_all_colles(self):
        """Main method to scrape all colles"""
        logger.info("Starting colles scraping...")
        
        # First, scrape the main page to get all colles
        print("Scraping main page...")
        colles_count = self.scrape_main_page()
        print(f"Found {colles_count} colles on main page")
        if colles_count == 0:
            logger.error("No colles found on main page")
            return
        
        # Now scrape detailed information for each colla
        logger.info(f"Scraping detailed information for {len(self.colles_data)} colles...")
    
        for i, colla_basic in enumerate(self.colles_data):
            logger.info(f"Processing {i+1}/{len(self.colles_data)}: {colla_basic['colla_name']}")
            
            # Scrape detailed information
            detailed_info = self.scrape_colla_detail(
                colla_basic['colla_id'], 
                colla_basic['colla_name'],
                colla_basic
            )
            
            # Merge basic and detailed info
            self.colles_data[i].update(detailed_info)
            
            # Add delay to be respectful to the server
            time.sleep(1)
        
        logger.info("Scraping completed!")
    
    def save_to_json(self, filename="../data_basic/colles_castelleres.json"):
        """Save scraped data to JSON file"""
        try:
            # Create comprehensive dataset
            dataset = {
                "metadata": {
                    "scraped_at": datetime.now().isoformat(),
                    "total_colles": len(self.colles_data),
                    "source_url": self.colles_url,
                    "scraper_version": "1.0"
                },
                "colles": self.colles_data
            }
            
            # Ensure data_basic directory exists
            os.makedirs('data_basic', exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(dataset, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Data saved to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving data: {str(e)}")

def main():
    print("Starting colles scraping...")
    scraper = CollesScraper()
    scraper.scrape_all_colles()
    scraper.save_to_json()

if __name__ == "__main__":
    main()
