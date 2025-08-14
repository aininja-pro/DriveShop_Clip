-- Check the most recent jobs and their job_params
SELECT 
    id,
    run_name,
    job_type,
    job_status,
    job_params,
    created_by,
    created_at
FROM processing_runs
WHERE run_name LIKE 'CSV Process%2025-08-11%'
ORDER BY created_at DESC
LIMIT 5;