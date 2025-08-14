-- Update completed jobs with proper statistics
UPDATE processing_runs 
SET 
    total_records = COALESCE(total_records, 0),
    successful_finds = COALESCE(successful_finds, 0),
    failed_attempts = COALESCE(failed_attempts, 0)
WHERE job_status = 'completed'
  AND (total_records IS NULL OR successful_finds IS NULL OR failed_attempts IS NULL);

-- Check recent jobs to verify statistics
SELECT 
    id,
    run_name,
    job_status,
    total_records,
    successful_finds,
    failed_attempts,
    created_at
FROM processing_runs
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 10;
EOF < /dev/null