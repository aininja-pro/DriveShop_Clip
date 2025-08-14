# Quick Process Check Guide

Since the UI logs you out but processes continue running, here are two ways to check if your process is still active:

## Option 1: Supabase SQL Editor (Easiest)

Go to your Supabase dashboard → SQL Editor and run this query:

```sql
-- Quick status check - shows if clips were added in last 5 minutes
SELECT 
    CASE 
        WHEN COUNT(*) > 0 THEN '🟢 ACTIVE - Process is running!'
        ELSE '🔴 INACTIVE - No recent activity'
    END as status,
    COUNT(*) as clips_last_5_mins,
    MAX(processed_date) as last_clip_time
FROM clips
WHERE processed_date > NOW() - INTERVAL '5 minutes';
```

## Option 2: Detailed Activity Check

For more details, run this query:

```sql
-- Shows clips added by minute for last 30 minutes
SELECT 
    DATE_TRUNC('minute', processed_date) as minute,
    COUNT(*) as clips_added,
    STRING_AGG(DISTINCT wo_number::text, ', ') as work_orders
FROM clips
WHERE processed_date > NOW() - INTERVAL '30 minutes'
GROUP BY DATE_TRUNC('minute', processed_date)
ORDER BY minute DESC
LIMIT 10;
```

## Option 3: Current Work Orders

To see which work orders are being processed:

```sql
-- Shows work orders processed in last hour
SELECT 
    wo_number,
    COUNT(*) as total_clips,
    SUM(CASE WHEN status = 'Found' THEN 1 ELSE 0 END) as found,
    SUM(CASE WHEN status = 'Not Found' THEN 1 ELSE 0 END) as not_found,
    MAX(processed_date) as last_update,
    EXTRACT(EPOCH FROM (NOW() - MAX(processed_date)))/60 as mins_ago
FROM clips
WHERE processed_date > NOW() - INTERVAL '2 hours'
GROUP BY wo_number
ORDER BY MAX(processed_date) DESC
LIMIT 10;
```

## Interpreting Results

- **🟢 ACTIVE**: Clips added in last 5 minutes = process is running
- **🟡 MAYBE**: Clips added 5-15 minutes ago = check Render logs
- **🔴 INACTIVE**: No clips for 15+ minutes = process likely finished

## Pro Tip

The Render logs are your best source of truth. The database queries just confirm if new clips are being added, which indicates the process is still running even if your UI session expired.