-- Add workflow_stage column to clips table for enhanced workflow tracking
-- Values: 'found' | 'sentiment_analyzed' | 'exported' | 'rejected'

ALTER TABLE clips ADD COLUMN IF NOT EXISTS workflow_stage TEXT DEFAULT 'found';

-- Update existing records to have proper workflow_stage values
UPDATE clips 
SET workflow_stage = CASE 
    WHEN status = 'approved' THEN 'found'
    WHEN status = 'rejected' THEN 'rejected'
    WHEN status = 'pending_review' THEN 'found'
    WHEN status = 'no_content_found' THEN 'rejected'
    ELSE 'found'
END
WHERE workflow_stage IS NULL OR workflow_stage = 'found';

-- Add index for performance on workflow_stage queries
CREATE INDEX IF NOT EXISTS idx_clips_workflow_stage ON clips(workflow_stage);
CREATE INDEX IF NOT EXISTS idx_clips_status_workflow ON clips(status, workflow_stage);

-- Verify the changes
SELECT 
    workflow_stage,
    status,
    COUNT(*) as count
FROM clips 
GROUP BY workflow_stage, status
ORDER BY workflow_stage, status; 