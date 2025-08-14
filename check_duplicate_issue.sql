-- Check for duplicate jobs with same timestamp
SELECT 
    id,
    run_name,
    job_status,
    created_by,
    worker_id,
    total_records,
    successful_finds,
    failed_attempts,
    created_at
FROM processing_runs
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC, job_status;
