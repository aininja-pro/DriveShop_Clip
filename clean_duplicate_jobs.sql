-- Delete duplicate jobs keeping only the completed ones
WITH duplicates AS (
    SELECT 
        id,
        run_name,
        job_status,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY run_name, DATE_TRUNC('minute', created_at)
            ORDER BY 
                CASE job_status 
                    WHEN 'completed' THEN 1 
                    WHEN 'running' THEN 2
                    WHEN 'failed' THEN 3
                    WHEN 'queued' THEN 4
                    ELSE 5 
                END,
                total_records DESC NULLS LAST
        ) as rn
    FROM processing_runs
    WHERE created_at > NOW() - INTERVAL '2 hours'
)
DELETE FROM processing_runs
WHERE id IN (
    SELECT id FROM duplicates WHERE rn > 1
);

-- Verify no more duplicates
SELECT 
    run_name,
    COUNT(*) as count,
    STRING_AGG(job_status, ', ') as statuses,
    STRING_AGG(created_by, ', ') as users
FROM processing_runs
WHERE created_at > NOW() - INTERVAL '2 hours'
GROUP BY run_name
ORDER BY MAX(created_at) DESC;