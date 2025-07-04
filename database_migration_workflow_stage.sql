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