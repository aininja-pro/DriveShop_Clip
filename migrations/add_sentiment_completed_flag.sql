-- Add sentiment_completed flag to track when sentiment analysis has been completed
ALTER TABLE clips
ADD COLUMN IF NOT EXISTS sentiment_completed BOOLEAN DEFAULT FALSE;

-- Add additional sentiment analysis fields if they don't exist
ALTER TABLE clips
ADD COLUMN IF NOT EXISTS overall_score INTEGER,
ADD COLUMN IF NOT EXISTS aspects JSONB,
ADD COLUMN IF NOT EXISTS pros TEXT[],
ADD COLUMN IF NOT EXISTS cons TEXT[],
ADD COLUMN IF NOT EXISTS recommendation TEXT,
ADD COLUMN IF NOT EXISTS key_mentions TEXT[];

-- Update existing clips with sentiment data to have sentiment_completed = true
UPDATE clips
SET sentiment_completed = TRUE
WHERE overall_sentiment IS NOT NULL
AND workflow_stage = 'complete';

-- Create index for faster queries on sentiment_completed
CREATE INDEX IF NOT EXISTS idx_clips_sentiment_completed 
ON clips(sentiment_completed, status, workflow_stage);