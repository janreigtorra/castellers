#!/usr/bin/env python3
"""
Script per simular i entendre com funciona el matching de SQL query types
"""
from difflib import SequenceMatcher

# Pregunta original
question = "Quines colles van actuar a la Diada de Tots Sants a Vilafranca del Penedès 2025?"
question_lower = question.lower()
print(f"Pregunta: {question}\n")
print(f"Pregunta (lowercase): {question_lower}\n")
print("=" * 80)

# Patrons de COLLES (abans de la correcció)
colles_patterns = [
    "quines colles han",
    "quines colles han descarregat",
    "quines colles han carregat",
    "quines colles han intentat",
    "quines colles han fet",
    "quines colles van participar",
    "quines colles han participat",
    "quines colles han participat en",
    "quina colla"
]

# Patrons de CASTELLS_LIST
castells_list_patterns = [
    "quins castells van fer",
    "quins castells va fer",
    "quins castells han fet",
    "quins castells s'han fet",
    "quins castells s'han descarregat",
    "quins castells s'han carregat",
    "quins castells van descarregar",
    "quins castells van carregar",
    "quins castells van intentar",
    "quins castells van fer a la diada",  # AQUEST ÉS CLAU!
    "quins castells van fer a l'any",
    "quins castells van fer l'any",
    "quins castells van fer a la temporada",
    "quins castells van fer la temporada",
    "quins castells van fer a",
    "quins castells van fer en",
    "quins castells van fer el",
    "llista de castells",
    "castells que van fer",
    "castells que han fet",
    "castells fets a",
    "castells fets en",
    "castells fets el"
]

def calculate_scores(patterns, query_type_name):
    """Calcula els scores per a un conjunt de patrons"""
    print(f"\n{'='*80}")
    print(f"ANÀLISI DE: {query_type_name.upper()}")
    print(f"{'='*80}\n")
    
    max_similarity = 0
    best_pattern = None
    partial_matches = []
    
    for pattern in patterns:
        # 1. SequenceMatcher ratio (compara strings senceres)
        similarity = SequenceMatcher(None, question_lower, pattern).ratio()
        
        # 2. Check partial match (substring)
        is_partial = pattern in question_lower
        
        print(f"Patró: '{pattern}'")
        print(f"  → SequenceMatcher ratio: {similarity:.4f}")
        print(f"  → És substring de la pregunta? {is_partial}")
        
        if similarity > max_similarity:
            max_similarity = similarity
            best_pattern = pattern
        
        if is_partial:
            partial_matches.append(pattern)
            print(f"  → ⚠️  PARTIAL MATCH TROBAT!")
        
        print()
    
    # Boost per partial matches
    final_score = max_similarity
    if partial_matches:
        final_score = max(final_score, 0.75)
        print(f"📊 PARTIAL MATCHES TROBATS: {len(partial_matches)}")
        for pm in partial_matches:
            print(f"   - '{pm}'")
        print(f"📈 Score boost aplicat: max({max_similarity:.4f}, 0.75) = {final_score:.4f}")
    else:
        print(f"📊 No s'han trobat partial matches")
        print(f"📈 Score final: {final_score:.4f}")
    
    print(f"\n🏆 MILLOR PATRÓ: '{best_pattern}'")
    print(f"🏆 SCORE FINAL: {final_score:.4f}\n")
    
    return final_score, best_pattern, partial_matches

# Calcular scores
colles_score, colles_best, colles_partials = calculate_scores(colles_patterns, "COLLES")
castells_score, castells_best, castells_partials = calculate_scores(castells_list_patterns, "CASTELLS_LIST")

# Comparació final
print("\n" + "=" * 80)
print("COMPARACIÓ FINAL")
print("=" * 80)
print(f"\nCOLLES score: {colles_score:.4f}")
print(f"CASTELLS_LIST score: {castells_score:.4f}")
print(f"\n{'→ CASTELLS_LIST guanya!' if castells_score > colles_score else '→ COLLES guanya!'}")
print(f"\nDiferència: {abs(castells_score - colles_score):.4f}")

if castells_partials:
    print(f"\n⚠️  RAÓ: CASTELLS_LIST té {len(castells_partials)} partial match(es):")
    for pm in castells_partials:
        print(f"   - '{pm}' està dins de la pregunta!")
        print(f"     Pregunta conté: '{pm}' ✓")

