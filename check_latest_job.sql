-- Check the latest job you just submitted
SELECT 
    id,
    run_name,
    job_type,
    job_status,
    created_by,
    created_at,
    worker_id,
    CASE 
        WHEN job_params IS NULL THEN 'NULL'
        ELSE 'Has params'
    END as params_status
FROM processing_runs
WHERE id = '4fdadf00-a8f9-462d-92c8-7e6c6a349da4'
   OR created_at > NOW() - INTERVAL '5 minutes'
ORDER BY created_at DESC;