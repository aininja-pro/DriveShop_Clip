-- Debug job queue issues

-- Check jobs in queue
SELECT id, run_name, job_type, job_status, created_by, created_at, worker_id
FROM processing_runs
WHERE job_status IN ('queued', 'running')
ORDER BY created_at DESC;

-- Check worker status
SELECT * FROM worker_status;

-- Manually try to claim a job (for testing)
UPDATE processing_runs
SET job_status = 'running',
    started_at = NOW(),
    worker_id = 'manual-test'
WHERE id IN (
    SELECT id 
    FROM processing_runs 
    WHERE job_status = 'queued' 
    ORDER BY created_at 
    LIMIT 1
)
RETURNING *;