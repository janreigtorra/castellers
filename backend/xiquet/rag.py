"""
RAG (Retrieval-Augmented Generation) utilities for reranking and processing search results.
"""

import re
from typing import List
from difflib import SequenceMatcher


def expand_decade_to_years(question: str) -> List[int]:

    decade_patterns = {
        r'\bany[s]?\s*80\b|\bdècada.*80\b|anys\s*vuitanta': range(1980, 1990),
        r'\bany[s]?\s*70\b|\bdècada.*70\b|anys\s*setanta': range(1970, 1980),
        r'\bany[s]?\s*90\b|\bdècada.*90\b|anys\s*noranta': range(1990, 2000),
        r'\bany[s]?\s*60\b|\bdècada.*60\b|anys\s*seixanta': range(1960, 1970),
        r'\bany[s]?\s*50\b|\bdècada.*50\b|anys\s*cinquanta': range(1950, 1960),
        r'\bsegle\s*XVIII\b|segle\s*18': range(1700, 1800),
        r'\bsegle\s*XIX\b|segle\s*19': range(1800, 1900),
        r'\bsegle\s*XX\b|segle\s*20': range(1900, 2000),
    }
    
    years = []
    for pattern, year_range in decade_patterns.items():
        if re.search(pattern, question, re.IGNORECASE):
            years.extend(list(year_range))
    
    return years


def rerank_rag_results(results: list, entities: dict, question: str) -> list:

    if not results:
        return results
    
    question_lower = question.lower()
    detected_colles = entities.get("colla", []) or []
    detected_anys = entities.get("anys", []) or []
    
    # Expand decade references to years
    expanded_years = expand_decade_to_years(question)
    all_years = set(detected_anys + expanded_years)
    
    # Extract query words for keyword matching (remove common words)
    stop_words = {'el', 'la', 'els', 'les', 'un', 'una', 'de', 'del', 'a', 'amb', 'per', 'que', 'és', 'i', 'o'}
    query_words = [w.lower() for w in re.findall(r'\b\w+\b', question) if w.lower() not in stop_words and len(w) > 2]
    
    reranked = []
    colla_matches = []  # Separate list for colla-matched chunks
    

    for doc_info, base_score in results:
        meta = doc_info.get("meta", {})
        boost = 0.0
        boost_reasons = []
        is_colla_match = False
        
        # Debug: Check if title contains any detected colla name (to find potential matches)
        title = meta.get("title", "")
        for colla in detected_colles:
            if colla.lower() in title.lower():
                chunk_colles_debug = meta.get("colles") or []

        
        # 1. Colla boost (highest priority)
        chunk_colles = [c.lower() for c in (meta.get("colles") or [])]
        for colla in detected_colles:
            colla_lower = colla.lower()
            # Check if colla name (or significant part) appears in chunk colles
            for chunk_colla in chunk_colles:
                if colla_lower in chunk_colla or chunk_colla in colla_lower:
                    boost += 0.35
                    boost_reasons.append(f"colla:{colla}")
                    is_colla_match = True
                    break
        
        # 2. Year boost
        chunk_years = set(meta.get("years") or [])
        chunk_year_ranges = [yr.lower() for yr in (meta.get("year_ranges") or [])]
        
        # Check direct year matches
        year_matches = chunk_years & all_years
        if year_matches:
            boost += 0.2 * min(len(year_matches), 3)  # Cap at 0.6
            boost_reasons.append(f"years:{list(year_matches)[:3]}")
        
        # Check year range matches (e.g., "1980-1990", "segle XIX")
        for yr in chunk_year_ranges:
            if any(str(y) in yr for y in all_years):
                boost += 0.1
                boost_reasons.append(f"year_range:{yr}")
                break
        
        # 3. Keyword fuzzy matching
        chunk_keywords = [kw.lower() for kw in (meta.get("keywords") or [])]
        keyword_matches = 0
        for query_word in query_words:
            for chunk_kw in chunk_keywords:
                # Fuzzy match: check if query word is similar to chunk keyword
                similarity = SequenceMatcher(None, query_word, chunk_kw).ratio()
                if similarity > 0.7 or query_word in chunk_kw or chunk_kw in query_word:
                    keyword_matches += 1
                    break
        
        if keyword_matches > 0:
            # Progressive boost: 1kw=0.1, 2kw=0.25, 3kw=0.4, 4+=0.5
            kw_boost = 0.15 + (min(keyword_matches, 4) - 1) * 0.15 if keyword_matches > 1 else 0.1
            boost += kw_boost
            boost_reasons.append(f"keywords:{keyword_matches}")
        
        # 4. Category relevance boost
        category = meta.get("category", "")
        if "història" in question_lower or "origen" in question_lower:
            if category == "history":
                boost += 0.15
                boost_reasons.append("cat:history")
        elif "tècnic" in question_lower or "estructura" in question_lower:
            if category == "technique":
                boost += 0.15
                boost_reasons.append("cat:technique")
        elif "concurs" in question_lower:
            if category == "concurs":
                boost += 0.15
                boost_reasons.append("cat:concurs")
        
        # 5. Place matching
        chunk_places = [p.lower() for p in (meta.get("places") or [])]
        detected_llocs = entities.get("llocs", []) or []
        for lloc in detected_llocs:
            if lloc.lower() in chunk_places:
                boost += 0.15
                boost_reasons.append(f"place:{lloc}")
                break
        
        # 6. Penalize colla-category chunks when no colla is detected
        if not detected_colles and category == "colles":
            boost -= 0.2
            boost_reasons.append("no_colla_penalty")
        
        # Calculate final score
        final_score = min(base_score + boost, 1.0)
        

        if is_colla_match:
            colla_matches.append((doc_info, final_score))
        else:
            reranked.append((doc_info, final_score))
    
    # Sort both lists by score
    colla_matches.sort(key=lambda x: x[1], reverse=True)
    reranked.sort(key=lambda x: x[1], reverse=True)
    
    # Prioritize colla matches at the top
    return colla_matches + reranked

