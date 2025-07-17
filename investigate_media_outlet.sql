-- Check all pending clips to see what's in media_outlet field
SELECT 
    wo_number,
    contact,
    person_id,
    media_outlet,
    clip_url,
    byline_author,
    processed_date
FROM clips
WHERE status = 'pending_review'
ORDER BY processed_date DESC
LIMIT 20;

-- Check specifically for the clip you're seeing
-- Replace 'YOUR_WO_NUMBER' with the actual WO# you're looking at
-- SELECT * FROM clips WHERE wo_number = 'YOUR_WO_NUMBER';

-- Check if media_outlet has any non-null values
SELECT 
    media_outlet,
    COUNT(*) as count
FROM clips
WHERE status = 'pending_review'
GROUP BY media_outlet
ORDER BY count DESC;