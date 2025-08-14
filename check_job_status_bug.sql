-- Check the job that's currently being processed
SELECT 
    id,
    run_name,
    job_status,
    worker_id,
    progress_current,
    progress_total,
    last_heartbeat,
    created_at
FROM processing_runs
WHERE created_at > NOW() - INTERVAL '30 minutes'
ORDER BY created_at DESC
LIMIT 5;
