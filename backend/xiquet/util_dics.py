
# ---- Guardrails: paraules NO relacionades amb castells ----

# ---- Gamma de Castells (ranges/tiers) ----
# Uses castell_code from puntuacions table
GAMMA_CASTELLS = {
    "castells de 6": {
        "specific": ["3d6", "4d6", "5d6", "2d6", "3d6a", "4d6a", "5d6a", 
                     "7d6", "9d6", "3d6s"],
        "description": "Castells de 6 pisos"
    },
    "castells de 7": {
        "specific": ["3d7", "4d7", "5d7", "2d7", "3d7a", "4d7a", "5d7a",
                     "7d7", "9d7", "3d7s"],
        "description": "Castells de 7 pisos"
    },
    "castells de 8": {
        "specific": ["3d8", "4d8", "5d8", "2d8f", "3d8s", "4d8a", "5d8a",
                     "7d8", "9d8", "3d8a"],
        "description": "Castells de 8 pisos"
    },
    "castells de 9": {
        "specific": ["4d9f", "3d9f", "5d9f", "2d9fm", "4d9af", "3d9af", "7d9f", "3d9", "4d9", "5d9"],
        "description": "Castells de 9 pisos principals"
    },
    "gamma extra": {
        "specific": ["2d9fm", "4d9af", "3d9af", "5d9f", "9d8", "9d9f", "3d10fm", "4d10fm", 
                     "pd8fm","pde8fm", "Pde8fm","Pd8fm", "pd9fmp", "pde9fmp", "Pde9fmp", "Pd9fmp", "4d9", "7d9f", "2d9f", "3d9"],
        "description": "Castells de gamma extra (màxima dificultat)"
    }
}

# Keywords to detect gamma questions
GAMMA_KEYWORDS = {
    "castells de 6": ["castells de 6", "sis pisos", "gamma de 6", "castell de 6" ],
    "castells de 7": ["castells de 7", "set pisos", "gamma de 7", "castell de 7"],
    "castells de 8": ["castells de 8", "vuit pisos", "gamma de 8", "castell de 8" ],
    "castells de 9": ["castells de 9", "nou pisos", "gamma de 9", "castell de 9" ],
    "gamma extra": ["castells de gamma extra", "gamma extra", "màxima dificultat", "maxima dificultat"]
}

# # Define query types with their characteristic keywords
# SQL_QUERY_PATTERNS = {
#     "millor_diada": ["millor diada", "millor actuació", "millor actuacio", "millor actuacion", "millor actuacions", "quina diada", "quina actuació", "millor actuacions", "millors actuacions", "millors actuacions"],
#     "millor_castell": ["millor castell", "millor torre", "millor construcció", "millor construccio", "millor torre", "millor construcció"],
#     "castell_historia": ["quants", "quant", "vegades", "cops", "història", "historia", "ha fet", "han fet", "quantes vegades"],
#     "location_actuations": ["quin any", "quin lloc", "millor any", "millor lloc", "quina ciutat", "quina població", "millor ciutat"],
#     "first_castell": ["primer", "primera", "primer cop", "primera vegada", "primer castell", "primera vegada"],
#     "castell_statistics": ["estadístiques", "estadisticas", "estadística", "estadistica", "estadístiques castell"],
#     "year_summary": ["resum", "resum temporada", "activitat", "com va ser la temporada", "com va ser l'any", "resum any", "com va anar la temporada", "com va anar l'any", 'que van fer a la temporada', 'que van fer a l\'any'],
#     "concurs_ranking": ["concurs", "concursos", "classificació concurs", "classificacio concurs", "guanyador concurs", "guanyadora concurs", "quina classificació", "quin concurs", "concurs de castells"],
#     "concurs_history": ["història concurs", "historia concurs", "concursos celebrats", "història dels concursos"]
# }

IS_SQL_QUERY_PATTERNS = {
    # Millor diada/actuació - retorna: data, lloc, colla, castells fets, punts totals
    # Exemples: "Quina va ser la millor diada dels Castellers de Vilafranca l'any 2023?"
    "millor_diada": [
        "millor diada", "millor actuació", "millors diades", "millors actuacions",
        "quina diada", "quina actuació", "quina va ser la millor",
        "millor jornada", "actuació més destacada",
    ],
    
    # Millor castell - retorna: castell més difícil/puntuació, data, lloc, colla, estat
    # Exemples: "Quin és el millor castell que han descarregat els Minyons de Terrassa?"
    "millor_castell": [
        "millor castell", "millor torre", "millor construcció",
        "castell més difícil", "castell més gran",
        "màxim castell", "millor estructura", 'Millor castell'
    ],
    
    # Quines colles han fet X - retorna: colla, diada, lloc, any, castells fets
    "colles": [
        "quines colles han descarregat", "quines colles han carregat", "quines colles han intentat",
        "quines colles han fet", "quines colles van participar", "quines colles han participat",
        "quines colles van actuar", "quines colles han actuat","primera colla", "primeres colles",
    ],
    
    # Castell història - retorna: comptatge de vegades, dates (primera/última), llocs, estat
    # Exemples: "Quants 3d10fm han descarregat els Capgrossos de Mataró?"
    "castell_historia": [
        "quantes vegades han", "quants cops han", "han aconseguit mai", 
        "quants 3d", "quants 2d", "quants 4d", "quants 5d", "quants pilars de", "quantes torres de",
        "quants castells de 7", "quants castells de 8", "quants castells de 9", "quants castells de gamma extra",
        "quants castells de 6", "quants castells", 
    ],
    
    # Castells list - retorna: llista de castells fets (filtrable per colla, diada, any, lloc, status, gamma)
    # Exemples: "Quins castells van fer els Castellers de Vilafranca a la Mercè l'any 2023?"
    "castells_list": [
        "quins castells van fer", "quins castells han fet",
        "quins castells s'han descarregat", "quins castells s'han carregat",
        "quins castells van descarregar", "quins castells van carregar", "quins castells van intentar",
        "llista de castells", "castells que van fer", "castells que han fet",
    ],
    
    # Location actuations - retorna: any/lloc de millor actuació, castells fets
    # Exemples: "A quin any van fer la millor actuació a la Mercè?"
    "location_actuations": [
        "quin any s'ha fet", "quin lloc s'ha fet", "a quina plaça s'ha fet",
        "quina ciutat s'ha fet", "quina població s'ha fet", "a quin lloc han fet",
        "quin any van fer", "a quin lloc van fer"
    ],
    
    # First castell - retorna: data, lloc, colla del primer cop que es va fer un castell
    # Exemples: "Quan va ser el primer 2d9fm de la Colla Vella dels Xiquets de Valls?"
    "first_castell": [
        "quin va ser el primer", "quin va ser la primera vegada", "quin és el primer",
        "quan van fer el primer", "quan es va fer per primer cop", "primer castell de",
        "quan van descarregar per primer cop", "quan van aconseguir per primera vegada", 
        "quan van intentar per primera vegada", "quan van carregar per primer cop",
        "quin any s'ha fet el primer", "quin any s'ha descarregat el primer",
        "on es va fer el primer", "a quin lloc van fer el primer",
        "quan van fer per primera vegada", "quan van fer el primer castell", "primer 3d", 
        "primer 4d", "primer 5d",  "primer 7d",  "primer castell", "primer torre", "primer pd", "primer pilar"
    ],
    
    # Castell statistics - retorna: estadístiques completes (descarregats, carregats, colles, dates)
    # Exemples: "Dóna'm les estadístiques del 4d9fa"
    "castell_statistics": [
        "estadístiques de", "estadístiques del castell",
        "ranking de colles", "qui ha fet més",
        "colles que han aconseguit",
    ],
    
    # Year summary - retorna: resum d'actuacions, castells, resultats d'un any/temporada
    # Exemples: "Com va anar la temporada 2023 dels Castellers de Barcelona?"
    "year_summary": [
        "resum de la temporada", "resum temporada", "resum any",
        "balanç de temporada", "balanç de la temporada",
        "com va ser la temporada", "com va ser l'any",
        "com va anar la temporada", "com va anar l'any",
        "què van fer a la temporada", "què van fer l'any",
        "resultats de la temporada",
    ],
    
    # Concurs ranking - retorna: classificació, posicions, punts, rondes d'un concurs
    # Exemples: "Quina classificació va tenir la Colla Vella al concurs de Tarragona 2024?"
    "concurs_ranking": [
        "classificació concurs", "classificació al concurs",
        "quina posició", "en quina posició",
        "guanyador concurs", "guanyadora concurs",
        "resultats del concurs", "puntuació al concurs", "rondes del concurs"
    ],
    
    # Concurs history - retorna: història de concursos (guanyadors, edicions, estadístiques)
    # Exemples: "Quants cops han guanyat el concurs els Castellers de Vilafranca?"
    "concurs_history": [
        "història del concurs", "història del concurs de castells",
        "concursos celebrats", "història dels concursos",
        "explica el concurs de l'any", "explica el concurs de la temporada",
        "concurs de l'edició", "com va anar el concurs de",
    ]
}

SQL_QUERY_PATTERNS = IS_SQL_QUERY_PATTERNS

META_LLM_KEYWORDS = [
    # Plataformes i productes
    "chatgpt", "gpt", "gpt-3", "gpt-4", "gpt-4o", "openai",
    "claude", "anthropic", "gemini", "google ai",
    " llama ", "meta ai", "mistral",
    "deepseek", "qwen", "cerebras",
    
    # Conceptes IA
    "intel·ligència artificial", "inteligencia artificial", " ia ",
    "llm", "large language model", "model de llenguatge",
    "model generatiu", "generative ai", "genai",
    "xarxes neuronals", "neural network",
    "deep learning", "machine learning",
    
    # Meta preguntes
    "qui ets", "què ets", "com funcionas", "com funciono",
    "com has estat entrenat", "entrenament del model",
    "saps ", "tens consciència",
    "ets real", "ets una persona",
    
    # Infraestructura / tecnologia
    "token", "tokens", "prompt", "prompts",
    "embedding", "vector", "fine-tuning", "finetuning",
    "latència", "latency", "inference",
    
    # Altres xats
    "bing chat", "copilot", "perplexity", "notion ai"
]


TECH_PROGRAMMING_KEYWORDS = [
    # Programació general
    "python", "javascript", "typescript", "java", "c++", "c#",
    "react", "react native", "node", "nodejs",
    "html", "css",
    
    # Bases de dades
    "sql", "postgres", "postgresql", "mysql", "sqlite",
    "mongodb", "supabase", "firebase",
    
    # Dev / infra
    "docker", "kubernetes", "aws", "gcp", "azure",
    "linux", "bash", "terminal",
    
    # Conceptes tècnics
    "backend", "frontend", "fullstack",
    "endpoint", "request", "response",
    " bug ", "error", "stack trace", "exception"
]


NON_CASTELLER_DOMAINS = [
    # Altres esports
    "futbol", "bàsquet", "tennis", " nba ", "fifa",
    "formula 1", "motogp",
    
    # Política
    "eleccions", "govern", "president",
    "parlament",
    
    # Economia
    "borsa", "bitcoin", "criptomoneda",
    "inflació", "interessos",

]


# Available providers and their models
# Column name mappings for nicer display (db_column -> display_name)
COLUMN_MAPPINGS = {
    'ranking': '#',
    'gamma_filtrada': 'Gamma',
    'event_name': 'Diada',
    'event_date': 'Data',
    'event_place': 'Lloc',
    'event_city': 'Ciutat',
    'colla_name': 'Colla',
    'castells_fets': 'Castells',
    'num_castells': 'Núm. Castells',
    'total_punts': 'Punts',
    'castell_name': 'Castell',
    'status': 'Estat',
    'date': 'Data',
    'place': 'Lloc',
    'city': 'Ciutat',
    'position': 'Posició',
    'total_points': 'Punts Totals',
    'edition': 'Edició',
    'any': 'Any',
    'count': 'Vegades',
    'first_date': 'Primera Data',
    'last_date': 'Última Data',
    'cities': 'Ciutats',
    'places': 'Llocs',
    'colles': 'Colles',
    'diades': 'Diades',
    'count_occurrences': 'Vegades',
    'num_actuacions': 'Núm. Actuacions',
    'castells_descarregats': 'Castells Descarregats',
    'castells_carregats': 'Castells Carregats',
    'castells_intent_desmuntat': 'Castells Intent Desmuntat',
    'castells_intent': 'Castells Intent',
    'punts': 'Punts',
    'punts_descarregat': 'Punts Descarregat',
    'punts_carregat': 'Punts Carregat',
    'cops_descarregat': 'Cops Descarregat',
    'primera_ronda': 'Ronda 1',
    'segona_ronda': 'Ronda 2',
    'tercera_ronda': 'Ronda 3',
    'quarta_ronda': 'Ronda 4',
    'cinquena_ronda': 'Ronda 5',
    'jornada': 'Jornada',
    'colles_participants': 'Colles Participants',
    'colla_guanyadora': 'Colla Guanyadora',
    'punts_guanyador': 'Punts Guanyador',
    'castells_r1_descarregats': 'Castells R1',
    'castells_r2_descarregats': 'Castells R2',
    'castells_r3_descarregats': 'Castells R3',
    'castells_r4_descarregats': 'Castells R4',
    'castells_r5_descarregats': 'Castells R5',
    'diada': 'Diada',
    'lloc': 'Lloc',
    'any': 'Any',
    'cops_carregat': 'Cops Carregat',
    'cops_intent': 'Cops Intent',
    'cops_intent_desmuntat': 'Cops Intent Desmuntat',
    'primera_data_descarregat': 'Primera Data Descarregat',
    'primera_data_carregat': 'Primera Data Carregat',
    'primera_data': 'Primera Data',
}

# Title mappings based on query type
TITLE_MAPPINGS = {
    'millor_diada': 'Millors Diades',
    'millor_castell': 'Millors Castells',
    'castell_historia': 'Historial del Castell',
    'castells_list': 'Llista de Castells',
    'location_actuations': 'Actuacions',
    'first_castell': 'Primer Castell',
    'castell_statistics': 'Estadístiques',
    'concurs_ranking': 'Classificació Concurs',
    'concurs_history': 'Historial Concurs',
    'year_summary': 'Resum Anual',
    'colles': 'Colles',
    'custom': 'Resultats',
}


MAP_QUERY_CHANGE = {
"3d9fp":"3d9af", 
"3d9 amb folre i pilar":"3d9af",
"3d9 amb folre i agulla":"3d9af",
"4d9fp":"4d9af",
"4d9 amb folre i pilar":"4d9af",
"4d9 amb folre i agulla":"4d9af",
"3d9pf":"3d9af", 
"4d9pf":"4d9af",  
"3d9fa":"3d9af", 
"4d9fa":"4d9af", 
"3d9sf":"3d9",
"4d9sf":"4d9",
"2d8sf":"2d8",
"2d8 net":"2d8",
"2d8 sense folre":"2d8",
"4d9 net":"4d9",
"4d9 sense folre":"4d9",
"Pd7sf":"Pd7",
"Pilar de 7 sense folre":"Pd7",
"2d9sm":"2d9f",
"2d9 sense manilles":"2d9f",
"3de9fp":"3d9af", 
"4de9fp":"4d9af", 
"3de9pf":"3d9af", 
"4de9pf":"4d9af",  
"3de9fa":"3d9af", 
"4de9fa":"4d9af", 
"3de9df":"3d9",
"4de9df":"4d9",
"2de8f":"2d8",
"2de8 net":"2d8",
"4de9 net":"4d9",
"3de10":"3d10fm",
"Pde7sf":"Pd7",
"2de9sm":"2d9f",
"4d8p":"4d8a",
"3d8p":"3d8a",
"5d8p":"5d8a",
"7d8p":"7d8a",
"4de8p":"4d8a",
"4d8 amb agulla":"4d8a",
"4d8 amb pilar":"4d8a",
"3de8p":"3d8a",
"3d8 amb agulla":"3d8a",
"3d8 amb pilar":"3d8a",
"5de8p":"5d8a",
"7de8p":"7d8a",
"4d7p":"4d7a",
"3d7p":"3d7a",
"5d7p":"5d7a",
"7d7p":"7d7a",
"4de7p":"4d7a",
"4d7 amb agulla":"4d7a",
"4d7 amb pilar":"4d7a",
"3de7p":"3d7a",
"3d7 amb agulla":"3d7a",
"3d7 amb pilar":"3d7a",
"5de7p":"5d7a",
"7de7p":"7d7a",
"4d6p":"4d6a",
"3d6p":"3d6a",
"5d6p":"5d6a",
"7d6p":"7d6a",
"4de6p":"4d6a",
"4d6 amb agulla":"4d6a",
"4d6 amb pilar":"4d6a",
"3de6p":"3d6a",
"3d6 amb agulla":"3d6a",
"3d6 amb pilar":"3d6a",
"5de6p":"5d6a",
"7de6p":"7d6a",
"5d8p":"5d8a",
"5d8 amb agulla":"5d8a",
"5d8 amb pilar":"5d8a",
"7d8p":"7d8a",
"3d6ps":"3d6s",
"3d7ps":"3d7s",
"3d8ps":"3d8s",
"3de6ps":"3d6s",
"3de7ps":"3d7s",
"3de8ps":"3d8s",
"pd4ps":"Pd4s",
"Pd5ps":"Pde5s",
"Pd6ps":"Pde6s",
"carro gros": "4d8", 
"super caterdal": "5d9f", 
# "colla vella": "Colla Vella dels Xiquets de Valls",
# "colla joves": "Colla Joves Xiquets de Valls",
# "els verds": "castellers de Vilafranca", 
}


AVAILABLE_PROVIDERS = {
    "groq": {
        "description": "Very fast and cheap inference",
        "models": [
            "llama-3.1-8b-instant", 
            "llama-3.1-70b-versatile",
            "mixtral-8x7b-32768",
            "gemma-7b-it"
        ]
    },
    "openai": {
        "description": "High quality, reliable",
        "models": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-3.5-turbo"
        ]
    },
    "anthropic": {
        "description": "High quality responses",
        "models": [
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229"
        ]
    },
    "ollama": {
        "description": "Free local models",
        "models": [
            "llama3.1:8b",
            "llama3.1:70b",
            "mistral:7b",
            "codellama:7b"
        ]
    },
    "gemini": {
        "description": "Google's advanced AI models",
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",  # best choice for production (30 RPM 1M TPM)
            "gemini-2.5-pro",
            "gemini-2.0-pro-exp",
            "gemini-flash-latest",
            "gemini-pro-latest"
        ]
    },
    "deepseek": {
        "description": "Fast and cost-effective models",
        "models": [
            "deepseek-chat",
            "deepseek-coder",
            "deepseek-reasoner",
            "deepseek-vl"
        ]
    },
    "cerebras": {
        "description": "High-performance large models",
        "models": [
            "gpt-oss-120b",
            "llama-4-maverick-17b-128e-instruct",
            "qwen-3-235b-a22b-instruct-2507",
            "qwen-3-32b"
        ]
    },
    "sambanova": {
        "description": "SambaNova AI models",
        "models": [
            "gpt-oss-120b",
            "Meta-Llama-3.3-70B-Instruct",
            "Meta-Llama-3.1-8B-Instruct",
            "Meta-Llama-3.1-70B-Instruct",
            "Meta-Llama-3.1-405B-Instruct",
            "Qwen3-235B"
        ]
    }
}

