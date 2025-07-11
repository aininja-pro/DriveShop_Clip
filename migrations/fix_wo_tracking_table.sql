-- Add missing last_attempt_result column to wo_tracking table
ALTER TABLE wo_tracking 
ADD COLUMN IF NOT EXISTS last_attempt_result text;

-- Add index for better performance
CREATE INDEX IF NOT EXISTS idx_wo_tracking_retry_after ON wo_tracking(retry_after_date);
CREATE INDEX IF NOT EXISTS idx_wo_tracking_status ON wo_tracking(status);