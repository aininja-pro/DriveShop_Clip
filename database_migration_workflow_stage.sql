-- Migration to add workflow_stage column and expand status options
-- Run this on your existing Supabase database

-- Add workflow_stage column
ALTER TABLE clips ADD COLUMN IF NOT EXISTS workflow_stage TEXT DEFAULT 'found';

-- Update status constraint to include new values
ALTER TABLE clips DROP CONSTRAINT IF EXISTS clips_status_check;
ALTER TABLE clips ADD CONSTRAINT clips_status_check 
    CHECK (status IN ('pending_review', 'approved', 'rejected', 'no_content_found', 'processing_failed'));

-- Add workflow_stage constraint
ALTER TABLE clips ADD CONSTRAINT clips_workflow_stage_check 
    CHECK (workflow_stage IN ('found', 'sentiment_analyzed', 'exported'));

-- Add new indexes
CREATE INDEX IF NOT EXISTS idx_clips_workflow_stage ON clips(workflow_stage);
CREATE INDEX IF NOT EXISTS idx_clips_status_workflow ON clips(status, workflow_stage);

-- Update clips_dashboard view
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

-- Set workflow_stage for existing records
UPDATE clips SET workflow_stage = 'found' WHERE workflow_stage IS NULL;

-- Add original_urls column if it doesn't exist (for View link in Rejected/Issues tab)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'clips' AND column_name = 'original_urls') THEN
        ALTER TABLE clips ADD COLUMN original_urls TEXT;
        
        RAISE NOTICE 'Added original_urls column to clips table';
    ELSE
        RAISE NOTICE 'original_urls column already exists in clips table';
    END IF;
END
$$;

-- Add urls_attempted column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'clips' AND column_name = 'urls_attempted') THEN
        ALTER TABLE clips ADD COLUMN urls_attempted INTEGER DEFAULT 0;
        
        RAISE NOTICE 'Added urls_attempted column to clips table';
    ELSE
        RAISE NOTICE 'urls_attempted column already exists in clips table';
    END IF;
END
$$;

-- Add failure_reason column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'clips' AND column_name = 'failure_reason') THEN
        ALTER TABLE clips ADD COLUMN failure_reason TEXT;
        
        RAISE NOTICE 'Added failure_reason column to clips table';
    ELSE
        RAISE NOTICE 'failure_reason column already exists in clips table';
    END IF;
END
$$;

-- Verify the changes
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'clips'
AND column_name IN ('workflow_stage', 'original_urls', 'urls_attempted', 'failure_reason')
ORDER BY column_name; 