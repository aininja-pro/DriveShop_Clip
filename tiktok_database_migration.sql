-- TikTok Integration Database Migration
-- Safe to run now - adds columns without affecting existing functionality

-- Add platform column to distinguish between web/youtube/tiktok sources
ALTER TABLE clips 
ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT 'web';

-- Add TikTok-specific fields
ALTER TABLE clips 
ADD COLUMN IF NOT EXISTS creator_handle TEXT;

ALTER TABLE clips 
ADD COLUMN IF NOT EXISTS video_id TEXT;

ALTER TABLE clips 
ADD COLUMN IF NOT EXISTS hashtags TEXT[];

ALTER TABLE clips 
ADD COLUMN IF NOT EXISTS engagement_metrics JSONB;

-- Create index on platform for faster filtering
CREATE INDEX IF NOT EXISTS idx_clips_platform ON clips(platform);

-- Create index on creator_handle for channel-based queries
CREATE INDEX IF NOT EXISTS idx_clips_creator_handle ON clips(creator_handle);

-- Optional: Add a comment to document the engagement_metrics structure
COMMENT ON COLUMN clips.engagement_metrics IS 'JSON object containing platform-specific metrics like views, likes, comments, shares, engagement_rate';

-- Example of what engagement_metrics will contain:
-- {
--   "views": 2100000,
--   "likes": 213500,
--   "comments": 1500,
--   "shares": 850,
--   "engagement_rate": 0.111
-- }