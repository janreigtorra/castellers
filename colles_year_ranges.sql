-- Query to get all colles and the range of years in which they have more than 10 events
-- Handles date formats: DD/MM/YYYY and YYYY-MM-DD

WITH events_with_years AS (
    -- Extract year from date field
    SELECT 
        e.id AS event_id,
        CASE 
            -- Handle DD/MM/YYYY format
            WHEN e.date ~ '^\d{2}/\d{2}/\d{4}$' THEN CAST(SPLIT_PART(e.date, '/', 3) AS INTEGER)
            -- Handle YYYY-MM-DD format
            WHEN e.date ~ '^\d{4}-\d{2}-\d{2}' THEN CAST(SPLIT_PART(e.date, '-', 1) AS INTEGER)
            -- Try to extract year from any format with 4-digit year
            WHEN e.date ~ '\d{4}' THEN CAST(SUBSTRING(e.date FROM '\d{4}') AS INTEGER)
            ELSE NULL
        END AS year
    FROM events e
    WHERE e.date IS NOT NULL 
      AND e.date != ''
),
colla_year_events AS (
    -- Count events per colla per year
    SELECT 
        c.id AS colla_id,
        c.name AS colla_name,
        ey.year,
        COUNT(DISTINCT ey.event_id) AS event_count
    FROM colles c
    INNER JOIN event_colles ec ON ec.colla_fk = c.id
    INNER JOIN events_with_years ey ON ey.event_id = ec.event_fk
    WHERE ey.year IS NOT NULL
    GROUP BY c.id, c.name, ey.year
    HAVING COUNT(DISTINCT ey.event_id) > 10  -- Only years with more than 10 events
),
colla_year_ranges AS (
    -- Get the min and max year for each colla
    SELECT 
        colla_id,
        colla_name,
        MIN(year) AS min_year,
        MAX(year) AS max_year,
        COUNT(DISTINCT year) AS years_with_10plus_events,
        SUM(event_count) AS total_events_in_range
    FROM colla_year_events
    GROUP BY colla_id, colla_name
)
SELECT 
    colla_name,
    min_year,
    max_year,
    CASE 
        WHEN min_year = max_year THEN min_year::TEXT
        ELSE min_year::TEXT || ' - ' || max_year::TEXT
    END AS year_range,
    years_with_10plus_events,
    total_events_in_range
FROM colla_year_ranges
ORDER BY colla_name;

