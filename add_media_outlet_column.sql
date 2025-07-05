-- Add media_outlet column to clips table
-- Run this in your Supabase SQL Editor

-- Add the media_outlet column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'clips' AND column_name = 'media_outlet'
    ) THEN
        ALTER TABLE clips ADD COLUMN media_outlet TEXT;
        RAISE NOTICE '✅ Added media_outlet column to clips table';
    ELSE
        RAISE NOTICE '⚠️ media_outlet column already exists';
    END IF;
END $$;

-- Update the clips_dashboard view to include the new column
DROP VIEW IF EXISTS clips_dashboard;
CREATE VIEW clips_dashboard AS
SELECT 
    c.id,
    c.wo_number,
    c.office,
    c.make,
    c.model,
    c.contact,
    c.person_id,
    c.activity_id,
    c.media_outlet,
    c.clip_url,
    c.published_date,
    c.attribution_strength,
    c.byline_author,
    c.status,
    c.workflow_stage,
    c.relevance_score,
    c.overall_sentiment,
    c.brand_alignment,
    c.summary,
    c.processed_date,
    c.tier_used,
    pr.run_name,
    pr.start_time as run_start_time
FROM clips c
LEFT JOIN processing_runs pr ON c.processing_run_id = pr.id
ORDER BY c.processed_date DESC;

-- Verify the changes
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'clips' 
ORDER BY ordinal_position; 