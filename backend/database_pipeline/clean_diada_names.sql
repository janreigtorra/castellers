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

UPDATE public.puntuacions
SET castell_code_external = LEFT(castell_code_external, LENGTH(castell_code_external) - 2) || 'fp'
WHERE castell_code_external LIKE '%af';



UPDATE puntuacions p
SET 
  punts_descarregat = v.descarregat,
  punts_carregat = v.carregat
FROM (
  VALUES
    ('Pd4',35,30),
    ('4d6',145,120),
    ('3d6',150,125),
    ('3d6a',185,165),
    ('4d6a',190,170),
    ('7d6',195,160),
    ('5d6',205,175),
    ('7d6a',235,210),
    ('5d6a',240,215),
    ('3d6s',245,220),
    ('2d6',300,250),
    ('Pd5',315,260),
    ('9d6',355,295),
    ('4d7',395,325),
    ('3d7',415,345),
    ('4d7a',515,465),
    ('3d7a',545,485),
    ('7d7',555,460),
    ('5d7',565,470),
    ('7d7a',640,570),
    ('5d7a',670,605),
    ('3d7s',705,635),
    ('9d7',740,615),
    ('2d7',805,670),
    ('4d8',845,700),
    ('Pd6',920,765),
    ('3d8',970,805),
    ('7d8',1090,905),
    ('2d8f',1210,1005),
    ('Pd7f',1270,1055),
    ('5d8',1385,1150),
    ('4d8a',1455,1310),
    ('3d8a',1530,1375),
    ('7d8a',1635,1475),
    ('5d8a',1730,1555),
    ('4d9f',1820,1510),
    ('3d9f',1910,1585),
    ('9d8',2385,1980),
    ('3d8s',2600,2340),
    ('2d9fm',2730,2265),
    ('Pd8fm',2870,2380),
    ('7d9f',3010,2500),
    ('5d9f',3125,2595),
    ('4d9af',3285,2955),
    ('3d9af',3445,3100),
    ('4d9',4105,3405),
    ('2d8',4310,3575),
    ('3d10fm',4525,3755),
    ('4d10fm',4930,4095),
    ('9d9f',5180,4295),
    ('2d9f',5645,4685),
    ('Pd9fmp',5925,4920),
    ('3d9',6220,5165),
    ('Pd7',6360,5280),
    ('2d10fmp',6780,5630),
    ('4d10f',7120,5910),
    ('3d10f',7475,6205)
) AS v(castell_code, descarregat, carregat)
WHERE p.castell_code = v.castell_code;

