-- Add strategic sentiment analysis fields to clips table
-- Run this migration in your Supabase SQL Editor

-- Add new strategic fields
ALTER TABLE clips ADD COLUMN IF NOT EXISTS marketing_impact_score INTEGER CHECK (marketing_impact_score >= 0 AND marketing_impact_score <= 10);
ALTER TABLE clips ADD COLUMN IF NOT EXISTS executive_summary TEXT;
ALTER TABLE clips ADD COLUMN IF NOT EXISTS brand_narrative TEXT;
ALTER TABLE clips ADD COLUMN IF NOT EXISTS strategic_signal TEXT;

-- Add creator/publication analysis fields (JSONB for flexibility)
ALTER TABLE clips ADD COLUMN IF NOT EXISTS creator_analysis JSONB;
ALTER TABLE clips ADD COLUMN IF NOT EXISTS publication_analysis JSONB;

-- Add competitive intelligence fields (JSONB)
ALTER TABLE clips ADD COLUMN IF NOT EXISTS competitive_intelligence JSONB;

-- Add enhanced aspect insights (replacing simple aspects)
ALTER TABLE clips ADD COLUMN IF NOT EXISTS aspect_insights JSONB;

-- Add action items fields (JSONB)
ALTER TABLE clips ADD COLUMN IF NOT EXISTS action_items JSONB;

-- Add additional strategic fields
ALTER TABLE clips ADD COLUMN IF NOT EXISTS influential_statements TEXT[];
ALTER TABLE clips ADD COLUMN IF NOT EXISTS purchase_intent_signals TEXT;
ALTER TABLE clips ADD COLUMN IF NOT EXISTS messaging_opportunities TEXT[];
ALTER TABLE clips ADD COLUMN IF NOT EXISTS risks_to_address TEXT[];

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_clips_marketing_impact ON clips(marketing_impact_score);
CREATE INDEX IF NOT EXISTS idx_clips_purchase_intent ON clips(purchase_intent_signals);

-- Add comments for documentation
COMMENT ON COLUMN clips.marketing_impact_score IS 'Strategic impact score (1-10) indicating marketing/brand importance';
COMMENT ON COLUMN clips.executive_summary IS 'CMO-level summary of strategic implications';
COMMENT ON COLUMN clips.brand_narrative IS 'How this content frames the brand story';
COMMENT ON COLUMN clips.strategic_signal IS 'Key trend, risk, or opportunity revealed';
COMMENT ON COLUMN clips.creator_analysis IS 'JSON: influence_tier, audience_archetype, credibility_score, viral_potential';
COMMENT ON COLUMN clips.publication_analysis IS 'JSON: credibility, audience_reach, editorial_stance, influence_factor';
COMMENT ON COLUMN clips.competitive_intelligence IS 'JSON: positioning_vs_competitors, advantages_highlighted, vulnerabilities_exposed';
COMMENT ON COLUMN clips.aspect_insights IS 'JSON: Enhanced aspect analysis with sentiment, impact, and evidence';
COMMENT ON COLUMN clips.action_items IS 'JSON: recommendation, media_strategy, creator_relationship';
COMMENT ON COLUMN clips.influential_statements IS 'Array of quotes likely to be repeated/shared';
COMMENT ON COLUMN clips.purchase_intent_signals IS 'strong positive / moderate positive / neutral / negative';