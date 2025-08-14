-- Check all jobs from the last hour
SELECT 
    id,
    run_name,
    job_status,
    job_type,
    progress_current,
    progress_total,
    created_at,
    last_heartbeat,
    worker_id,
    created_by
FROM processing_runs
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 10;

-- Check if any workers are active
SELECT 
    worker_id,
    status,
    current_job_id,
    last_heartbeat
FROM worker_status
WHERE last_heartbeat > NOW() - INTERVAL '5 minutes';
