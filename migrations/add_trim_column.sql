-- Migration to add trim column to clips table
-- This stores the vehicle trim level separately from the model

-- Add trim column to clips table
ALTER TABLE clips 
ADD COLUMN IF NOT EXISTS trim TEXT;

-- Add index on trim for better query performance
CREATE INDEX IF NOT EXISTS idx_clips_trim ON clips(trim);

-- Add composite index for make/model/trim queries
CREATE INDEX IF NOT EXISTS idx_clips_make_model_trim ON clips(make, model, trim);

-- Update any existing records if we have model data that includes trim
-- This would need to be run separately with proper trim extraction logic
-- UPDATE clips SET trim = extract_trim_from_model(model) WHERE trim IS NULL;