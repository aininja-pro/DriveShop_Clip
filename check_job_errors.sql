-- Check error messages in processing_runs
SELECT 
    id,
    run_name,
    job_type,
    job_status,
    error_message,
    created_at
FROM processing_runs
WHERE created_at > NOW() - INTERVAL '1 hour'
AND error_message IS NOT NULL
ORDER BY created_at DESC;

-- Check job logs for errors
SELECT 
    jl.timestamp,
    jl.level,
    jl.message,
    pr.run_name
FROM job_logs jl
JOIN processing_runs pr ON jl.job_id = pr.id
WHERE jl.level IN ('ERROR', 'CRITICAL')
AND jl.timestamp > NOW() - INTERVAL '1 hour'
ORDER BY jl.timestamp DESC
LIMIT 20;