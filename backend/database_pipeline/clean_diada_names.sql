UPDATE public.events
SET name = 'Diada de Tots Sants a Vilafranca del Penedès'
WHERE name = 'Tots Sants a Vilafranca del PenedèsDiada de Tots Sants a Vilafranca del Penedès';


UPDATE public.events
SET name = 'Diada de Sant Ramon a Vilafranca del Penedès'
WHERE name = 'Sant Ramon a Vilafranca del PenedèsDiada de Sant Ramon a Vilafranca del Penedès';


UPDATE public.events
SET name = 'Diada de Santa Tecla a Tarragona'
WHERE name = 'Santa Tecla a Tarragona (dia 23)Diada de Santa Tecla a Tarragona';



UPDATE public.events
SET name = 'Festa Major de l''Arboç'
WHERE name = 'Festa Major de l''ArboçFesta Major de l''Arboç';


UPDATE public.events
SET name = 'Diada de Sant Magí a Tarragona'
WHERE name = 'Sant Magí a TarragonaDiada de Sant Magí a Tarragona';


UPDATE public.events
SET name = 'Festa Major de Sant Pere a Terrassa'
WHERE name = 'Festa Major de TerrassaFesta Major de Sant Pere a Terrassa';


UPDATE public.events
SET name = 'Diada de Sant Magí a Tarragona'
WHERE name = 'Sant Magí a TarragonaDiada de Sant Magí a Tarragona';




UPDATE public.events
SET name = 'Festa Major del Catlla'
WHERE name = 'Festa Major del CatllarFesta Major del Catllar';


UPDATE public.events
SET name = 'Diada de la Mercè (colles convidades) a Barcelona'
WHERE name = 'La Mercè de Barcelona (colles convidades)Diada de la Mercè (colles convidades) a Barcelona';


UPDATE public.events
SET name = 'Diada de Sant Ramon a Vilafranca del Penedès'
WHERE name = 'Sant Ramon a Vilafranca del PenedèsDiada de Sant Ramon a Vilafranca del Penedès';


UPDATE public.events
SET name = 'Diada de la Mercè a Barcelona'
WHERE name = 'La Mercè de Barcelona (colles locals)Diada de la Mercè a Barcelona';


UPDATE public.events
SET name = 'Diada de Sant Fèlix'
WHERE name = 'Sant Fèlix a Vilafranca del PenedèsDiada de Sant Fèlix a Vilafranca del Penedès';


UPDATE public.events
SET name = 'Diada de Sant Narcís a Girona'
WHERE name = 'Sant Narcís a GironaDiada de Sant Narcís a Girona';


UPDATE public.events
SET name = 'Diada de Les Santes a Mataró'
WHERE name = 'Les Santes a MataróFesta Major de Les Santes a Mataró';


UPDATE public.events
SET name = 'Diada del Quadre de Santa Rosalia a Torredembarra'
WHERE name = 'Diada del Quadre de Santa Rosalia a TorredembarraDiada del Quadre de Santa Rosalia a Torredembarra';


UPDATE public.events
SET name = 'Diada de Sant Joan a Valls'
WHERE name = 'Sant Joan a VallsFesta Major de Sant Joan a Valls';


UPDATE public.events
SET name = 'Diada de les Neus de Vilanova i la Geltrú'
WHERE name = 'Festa Major de Vilanova i la GeltrúDiada de les Neus de Vilanova i la Geltrú';


UPDATE public.events
SET name = 'Diada de Santa Úrsula a Valls'
WHERE name = 'Santa Úrsula a VallsDiada de Santa Úrsula a Valls';


UPDATE public.events
SET name = 'Diada del Mercadal a Reus'
WHERE name = 'Diada del Mercadal a ReusDiada del Mercadal a Reus';



UPDATE public.events
SET name = 'Diada de Santa Teresa al Vendrell'
WHERE name = 'Santa Teresa al VendrellDiada de Santa Teresa al Vendrell';

UPDATE public.events
SET name = 'Festa Major de La Bisbal del Penedès'
WHERE name = 'Festa Major de la Bisbal del PenedèsFesta Major de La Bisbal del Penedès';



UPDATE public.events
SET name = 'Festa Major de la Bisbal del Penedès'
WHERE name = 'Festa Major de la Bisbal del PenedèsFesta Major de la Bisbal del Penedès'


SET name = TRIM(
    REPLACE(name, 'Concurs de Castells de Tarragona', '')
)
WHERE name LIKE 'Concurs de Castells de Tarragona%';

UPDATE public.events
SET name = TRIM(
    REPLACE(name, 'Concurs de Castells de Torredembarra', '')
)
WHERE name LIKE 'Concurs de Castells de Torredembarra%';


-- Fix castell_code_external for pilar names
UPDATE public.puntuacions
SET castell_code_external = LEFT(castell_code_external, LENGTH(castell_code_external) - 1) || 'p'
WHERE castell_code_external LIKE '%a';