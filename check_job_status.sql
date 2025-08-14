-- Check what's in the processing_runs table
SELECT 
    id,
    run_name,
    job_type,
    job_status,
    run_status,
    created_by,
    created_at,
    worker_id
FROM processing_runs
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 10;