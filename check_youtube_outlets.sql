-- Check YouTube clips with generic "YouTube" media outlet
SELECT 
    wo_number,
    contact,
    person_id,
    media_outlet,
    clip_url,
    byline_author
FROM clips
WHERE status = 'pending_review'
    AND clip_url LIKE '%youtube.com%'
    AND media_outlet = 'YouTube'
ORDER BY processed_date DESC;

-- Optional: Update these clips to have NULL media_outlet so dropdown appears
-- UPDATE clips
-- SET media_outlet = NULL
-- WHERE status = 'pending_review'
--     AND clip_url LIKE '%youtube.com%'
--     AND media_outlet = 'YouTube';