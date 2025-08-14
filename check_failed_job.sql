SELECT 
    id,
    run_name,
    job_status,
    error_message,
    created_at,
    completed_at
FROM processing_runs
WHERE id = 'b95aa12c-8356-4002-b5c6-1444e22a5277'
   OR created_at > NOW() - INTERVAL '10 minutes'
ORDER BY created_at DESC
LIMIT 5;