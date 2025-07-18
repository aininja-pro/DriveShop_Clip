-- Add unique constraint on wo_number to ensure one clip per WO#
-- Run this in your Supabase SQL Editor

-- Step 1: Clean up existing duplicates (keep the best clip per WO#)
DO $$
BEGIN
    -- Delete duplicate clips, keeping only the one with highest relevance_score per WO#
    DELETE FROM clips 
    WHERE id NOT IN (
        SELECT DISTINCT ON (wo_number) id
        FROM clips 
        ORDER BY wo_number, 
                 relevance_score DESC NULLS LAST,  -- Prefer higher relevance
                 processed_date DESC                -- If tied, prefer more recent
    );
    
    RAISE NOTICE '✅ Cleaned up duplicate clips - kept best clip per WO#';
END $$;

-- Step 2: Add unique constraint to prevent future duplicates
ALTER TABLE clips ADD CONSTRAINT unique_wo_number UNIQUE (wo_number);

-- Step 3: Verify the changes
SELECT 
    COUNT(*) as total_clips,
    COUNT(DISTINCT wo_number) as unique_wo_numbers,
    CASE 
        WHEN COUNT(*) = COUNT(DISTINCT wo_number) THEN '✅ No duplicates'
        ELSE '❌ Still has duplicates'
    END as status
FROM clips;

-- Step 4: Show any remaining duplicates (should be none)
SELECT wo_number, COUNT(*) as clip_count
FROM clips
GROUP BY wo_number
HAVING COUNT(*) > 1
ORDER BY clip_count DESC;

-- Final message
DO $$
BEGIN
    RAISE NOTICE '✅ Unique constraint added - one clip per WO# enforced';
END $$; 