-- Check what's actually in the database for the running job
SELECT 
    id,
    run_name,
    job_status,
    total_records,
    progress_current,
    progress_total,
    job_params,
    worker_id,
    last_heartbeat
FROM processing_runs
WHERE job_status IN ('running', 'cancelled')
   OR created_at > NOW() - INTERVAL '20 minutes'
ORDER BY created_at DESC
LIMIT 3;
