-- ============================================
-- CHECK IF PROCESSES ARE STILL RUNNING
-- Run these queries in Supabase SQL Editor
-- ============================================

-- 1. CHECK LAST 5 MINUTES (Active = clips being added now)
SELECT 
    COUNT(*) as clips_last_5_mins,
    MAX(created_at) as most_recent_clip
FROM clips
WHERE created_at > NOW() - INTERVAL '5 minutes';

-- 2. ACTIVITY BY MINUTE (See processing pattern)
SELECT 
    DATE_TRUNC('minute', created_at) as minute,
    COUNT(*) as clips_added,
    STRING_AGG(DISTINCT work_order::text, ', ') as work_orders
FROM clips
WHERE created_at > NOW() - INTERVAL '30 minutes'
GROUP BY DATE_TRUNC('minute', created_at)
ORDER BY minute DESC;

-- 3. CURRENT WORK ORDERS BEING PROCESSED
SELECT 
    work_order,
    media,
    COUNT(*) as total_clips,
    SUM(CASE WHEN status = 'Found' THEN 1 ELSE 0 END) as found,
    SUM(CASE WHEN status = 'Not Found' THEN 1 ELSE 0 END) as not_found,
    MAX(created_at) as last_clip_time,
    EXTRACT(EPOCH FROM (NOW() - MAX(created_at)))/60 as mins_since_last
FROM clips
WHERE created_at > NOW() - INTERVAL '2 hours'
GROUP BY work_order, media
ORDER BY MAX(created_at) DESC
LIMIT 10;

-- 4. PROCESSING RATE (clips per minute)
WITH minute_counts AS (
    SELECT 
        DATE_TRUNC('minute', created_at) as minute,
        COUNT(*) as clip_count
    FROM clips
    WHERE created_at > NOW() - INTERVAL '1 hour'
    GROUP BY DATE_TRUNC('minute', created_at)
)
SELECT 
    AVG(clip_count) as avg_clips_per_minute,
    MAX(clip_count) as max_clips_per_minute,
    COUNT(*) as active_minutes
FROM minute_counts
WHERE clip_count > 0;

-- 5. QUICK STATUS CHECK
SELECT 
    CASE 
        WHEN COUNT(*) > 0 THEN '🟢 ACTIVE - Processing running'
        ELSE '🔴 INACTIVE - No recent activity'
    END as process_status,
    COUNT(*) as clips_last_5_mins,
    NOW() as checked_at
FROM clips
WHERE created_at > NOW() - INTERVAL '5 minutes';