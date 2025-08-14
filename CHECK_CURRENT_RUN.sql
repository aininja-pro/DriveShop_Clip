-- ============================================
-- CHECK ALL CLIPS FROM CURRENT RUN
-- ============================================

-- 1. See ALL clips from today's run (adjust the time window as needed)
SELECT 
    wo_number,
    make,
    model,
    status,
    processed_date,
    tier_used,
    clip_url
FROM clips
WHERE processed_date > NOW() - INTERVAL '4 hours'  -- Adjust this based on when you started
ORDER BY processed_date DESC;

-- 2. Summary of the current run
SELECT 
    COUNT(*) as total_clips,
    SUM(CASE WHEN status = 'Found' THEN 1 ELSE 0 END) as found_clips,
    SUM(CASE WHEN status = 'Not Found' THEN 1 ELSE 0 END) as not_found_clips,
    MIN(processed_date) as run_started,
    MAX(processed_date) as last_clip,
    EXTRACT(EPOCH FROM (NOW() - MAX(processed_date)))/60 as mins_since_last_clip
FROM clips
WHERE processed_date > NOW() - INTERVAL '4 hours';

-- 3. See clips grouped by status (to spot patterns)
SELECT 
    status,
    COUNT(*) as count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 1) as percentage
FROM clips
WHERE processed_date > NOW() - INTERVAL '4 hours'
GROUP BY status
ORDER BY count DESC;

-- 4. Work orders processed in this run
SELECT 
    wo_number,
    make || ' ' || model as vehicle,
    status,
    processed_date,
    CASE 
        WHEN clip_url IS NOT NULL THEN '✓ Has URL'
        ELSE '✗ No URL'
    END as has_clip
FROM clips
WHERE processed_date > NOW() - INTERVAL '4 hours'
ORDER BY processed_date DESC;

-- 5. Find the last few successful clips before it stopped
SELECT 
    wo_number,
    make || ' ' || model as vehicle,
    status,
    processed_date,
    tier_used
FROM clips
WHERE processed_date > NOW() - INTERVAL '4 hours'
    AND status = 'Found'
ORDER BY processed_date DESC
LIMIT 10;