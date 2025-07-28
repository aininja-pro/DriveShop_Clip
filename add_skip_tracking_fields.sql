-- Add fields to track when clips are skipped during processing runs
-- This allows us to show skipped clips in the Current Run view

-- Add last_skip_run_id to track which run last skipped this clip
ALTER TABLE clips 
ADD COLUMN IF NOT EXISTS last_skip_run_id UUID REFERENCES processing_runs(id);

-- Add skip_reason to track why the clip was skipped
ALTER TABLE clips 
ADD COLUMN IF NOT EXISTS skip_reason TEXT;

-- Add index for efficient querying by skip run
CREATE INDEX IF NOT EXISTS idx_clips_last_skip_run_id ON clips(last_skip_run_id);

-- Verify the changes
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM 
    information_schema.columns
WHERE 
    table_name = 'clips' 
    AND column_name IN ('last_skip_run_id', 'skip_reason')
ORDER BY 
    ordinal_position;