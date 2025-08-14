-- Stop all running and queued jobs
UPDATE processing_runs
SET 
    job_status = 'cancelled',
    completed_at = NOW(),
    error_message = 'Manually stopped - worker killed'
WHERE job_status IN ('running', 'queued');

-- Clear any worker status
DELETE FROM worker_status;

-- Show what was cancelled
SELECT 
    id,
    run_name,
    job_status,
    created_at
FROM processing_runs
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;