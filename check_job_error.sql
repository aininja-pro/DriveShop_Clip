-- Check error for this specific job
SELECT 
    error_message
FROM processing_runs
WHERE id = '4fdadf00-a8f9-462d-92c8-7e6c6a349da4';

-- Check logs for this job
SELECT 
    timestamp,
    level,
    message
FROM job_logs
WHERE job_id = '4fdadf00-a8f9-462d-92c8-7e6c6a349da4'
ORDER BY timestamp;