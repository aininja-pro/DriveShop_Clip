-- First, identify duplicates and which ones to keep
WITH duplicates AS (
    SELECT 
        id,
        run_name,
        job_status,
        created_at,
        total_records,
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
),
to_keep AS (
    SELECT id, run_name FROM duplicates WHERE rn = 1
),
to_delete AS (
    SELECT d.id as delete_id, tk.id as keep_id
    FROM duplicates d
    JOIN to_keep tk ON d.run_name = tk.run_name 
        AND DATE_TRUNC('minute', d.created_at) = DATE_TRUNC('minute', d.created_at)
    WHERE d.rn > 1
)
-- Update clips to point to the kept run instead of the duplicate
UPDATE clips 
SET last_skip_run_id = td.keep_id
FROM to_delete td
WHERE clips.last_skip_run_id = td.delete_id;

-- Now delete the duplicates
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