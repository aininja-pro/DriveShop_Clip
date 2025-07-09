-- Add FMS export date to track when clips are exported
ALTER TABLE clips
ADD COLUMN IF NOT EXISTS fms_export_date TIMESTAMP;

-- Create index for faster queries on FMS export date
CREATE INDEX IF NOT EXISTS idx_clips_fms_export_date 
ON clips(fms_export_date);