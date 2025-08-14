-- Check for actively running processes in the last 24 hours
-- Look for clips being processed or recently updated

-- Option 1: Check recently modified clips (if you have updated_at timestamp)
SELECT 
    work_order,
    media,
    make_model,
    status,
    created_at,
    updated_at
FROM clips
WHERE updated_at > NOW() - INTERVAL '24 hours'
ORDER BY updated_at DESC
LIMIT 20;

-- Option 2: Check for specific statuses that indicate processing
SELECT 
    work_order,
    media,
    make_model,
    status,
    COUNT(*) as clip_count
FROM clips
WHERE created_at > NOW() - INTERVAL '24 hours'
    AND status IN ('Processing', 'Pending', 'In Progress')  -- adjust based on your statuses
GROUP BY work_order, media, make_model, status
ORDER BY work_order DESC;

-- Option 3: Get summary of today's activity
SELECT 
    DATE(created_at) as process_date,
    COUNT(*) as total_clips,
    COUNT(CASE WHEN status = 'Found' THEN 1 END) as found_clips,
    COUNT(CASE WHEN status = 'Not Found' THEN 1 END) as not_found_clips,
    COUNT(DISTINCT work_order) as unique_work_orders
FROM clips
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY DATE(created_at)
ORDER BY process_date DESC;