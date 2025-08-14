-- Check the running job details
SELECT 
    id,
    run_name,
    job_status,
    total_records,
    progress_current,
    progress_total,
    successful_finds,
    failed_attempts,
    job_params::json->>'filters' as filters,
    worker_id
FROM processing_runs
WHERE job_status IN ('running', 'queued')
   OR created_at > NOW() - INTERVAL '10 minutes'
ORDER BY created_at DESC
LIMIT 5;
