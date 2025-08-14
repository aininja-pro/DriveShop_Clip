-- Add columns for actual skipped and error counts
ALTER TABLE processing_runs 
ADD COLUMN IF NOT EXISTS skipped_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS error_count INTEGER DEFAULT 0;

-- Update any existing completed jobs to calculate skipped
UPDATE processing_runs
SET skipped_count = GREATEST(0, total_records - successful_finds - failed_attempts)
WHERE job_status = 'completed' 
  AND skipped_count IS NULL
  AND total_records IS NOT NULL;