-- Migration: Add enhanced sentiment analysis fields for Message Pull-Through Analysis
-- This migration adds JSONB columns to store the detailed sentiment analysis data
-- while keeping existing columns for backward compatibility

-- Add new JSONB columns for enhanced sentiment data
ALTER TABLE clips 
ADD COLUMN IF NOT EXISTS sentiment_data_enhanced JSONB,
ADD COLUMN IF NOT EXISTS sentiment_version TEXT DEFAULT 'v1';

-- Add indexes for the new JSONB fields for better query performance
CREATE INDEX IF NOT EXISTS idx_clips_sentiment_enhanced ON clips USING GIN (sentiment_data_enhanced);
CREATE INDEX IF NOT EXISTS idx_clips_sentiment_version ON clips(sentiment_version);

-- Add computed columns for frequently accessed data (optional, for performance)
-- These will extract commonly queried fields from the JSONB
ALTER TABLE clips
ADD COLUMN IF NOT EXISTS sentiment_classification TEXT GENERATED ALWAYS AS 
    (sentiment_data_enhanced->>'sentiment_classification'->>'overall') STORED,
ADD COLUMN IF NOT EXISTS features_count INTEGER GENERATED ALWAYS AS 
    (jsonb_array_length(COALESCE(sentiment_data_enhanced->'key_features_mentioned', '[]'::jsonb))) STORED,
ADD COLUMN IF NOT EXISTS attributes_count INTEGER GENERATED ALWAYS AS 
    (jsonb_array_length(COALESCE(sentiment_data_enhanced->'brand_attributes_captured', '[]'::jsonb))) STORED,
ADD COLUMN IF NOT EXISTS drivers_count INTEGER GENERATED ALWAYS AS 
    (jsonb_array_length(COALESCE(sentiment_data_enhanced->'purchase_drivers', '[]'::jsonb))) STORED;

-- Create a view for easy access to enhanced sentiment data
CREATE OR REPLACE VIEW clips_sentiment_enhanced AS
SELECT 
    c.*,
    -- Extract sentiment classification
    sentiment_data_enhanced->'sentiment_classification'->>'overall' as sentiment_detailed,
    (sentiment_data_enhanced->'sentiment_classification'->>'confidence')::float as sentiment_confidence,
    sentiment_data_enhanced->'sentiment_classification'->>'rationale' as sentiment_rationale,
    
    -- Extract arrays as JSONB for further processing
    sentiment_data_enhanced->'key_features_mentioned' as key_features,
    sentiment_data_enhanced->'brand_attributes_captured' as brand_attributes,
    sentiment_data_enhanced->'purchase_drivers' as purchase_drivers,
    sentiment_data_enhanced->'competitive_context' as competitive_context,
    
    -- Counts for quick filtering
    jsonb_array_length(COALESCE(sentiment_data_enhanced->'key_features_mentioned', '[]'::jsonb)) as feature_mentions_count,
    jsonb_array_length(COALESCE(sentiment_data_enhanced->'brand_attributes_captured', '[]'::jsonb)) as brand_attributes_count,
    jsonb_array_length(COALESCE(sentiment_data_enhanced->'purchase_drivers', '[]'::jsonb)) as purchase_drivers_count
FROM clips c
WHERE c.sentiment_data_enhanced IS NOT NULL;

-- Create aggregation functions for Message Pull-Through Analysis

-- Function to aggregate features across multiple clips
CREATE OR REPLACE FUNCTION aggregate_features_mentioned(make_filter TEXT, model_filter TEXT, date_from DATE DEFAULT NULL, date_to DATE DEFAULT NULL)
RETURNS TABLE (
    feature TEXT,
    positive_count BIGINT,
    neutral_count BIGINT,
    negative_count BIGINT,
    total_mentions BIGINT,
    sample_quotes TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    WITH feature_data AS (
        SELECT 
            jsonb_array_elements(sentiment_data_enhanced->'key_features_mentioned') as feature_obj
        FROM clips
        WHERE make = make_filter 
        AND model = model_filter
        AND sentiment_data_enhanced IS NOT NULL
        AND (date_from IS NULL OR published_date >= date_from)
        AND (date_to IS NULL OR published_date <= date_to)
    )
    SELECT 
        feature_obj->>'feature' as feature,
        COUNT(*) FILTER (WHERE feature_obj->>'sentiment' = 'positive') as positive_count,
        COUNT(*) FILTER (WHERE feature_obj->>'sentiment' = 'neutral') as neutral_count,
        COUNT(*) FILTER (WHERE feature_obj->>'sentiment' = 'negative') as negative_count,
        COUNT(*) as total_mentions,
        ARRAY_AGG(DISTINCT feature_obj->>'quote' ORDER BY feature_obj->>'quote' LIMIT 5) as sample_quotes
    FROM feature_data
    GROUP BY feature_obj->>'feature'
    ORDER BY total_mentions DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to aggregate brand attributes
CREATE OR REPLACE FUNCTION aggregate_brand_attributes(make_filter TEXT, model_filter TEXT, date_from DATE DEFAULT NULL, date_to DATE DEFAULT NULL)
RETURNS TABLE (
    attribute TEXT,
    reinforced_count BIGINT,
    neutral_count BIGINT,
    challenged_count BIGINT,
    total_mentions BIGINT,
    sample_evidence TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    WITH attribute_data AS (
        SELECT 
            jsonb_array_elements(sentiment_data_enhanced->'brand_attributes_captured') as attr_obj
        FROM clips
        WHERE make = make_filter 
        AND model = model_filter
        AND sentiment_data_enhanced IS NOT NULL
        AND (date_from IS NULL OR published_date >= date_from)
        AND (date_to IS NULL OR published_date <= date_to)
    )
    SELECT 
        attr_obj->>'attribute' as attribute,
        COUNT(*) FILTER (WHERE attr_obj->>'sentiment' = 'reinforced') as reinforced_count,
        COUNT(*) FILTER (WHERE attr_obj->>'sentiment' = 'neutral') as neutral_count,
        COUNT(*) FILTER (WHERE attr_obj->>'sentiment' = 'challenged') as challenged_count,
        COUNT(*) as total_mentions,
        ARRAY_AGG(DISTINCT attr_obj->>'evidence' ORDER BY attr_obj->>'evidence' LIMIT 5) as sample_evidence
    FROM attribute_data
    GROUP BY attr_obj->>'attribute'
    ORDER BY total_mentions DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to aggregate purchase drivers
CREATE OR REPLACE FUNCTION aggregate_purchase_drivers(make_filter TEXT, model_filter TEXT, date_from DATE DEFAULT NULL, date_to DATE DEFAULT NULL)
RETURNS TABLE (
    reason TEXT,
    positive_count BIGINT,
    negative_count BIGINT,
    primary_count BIGINT,
    secondary_count BIGINT,
    mentioned_count BIGINT,
    total_mentions BIGINT,
    sample_quotes TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    WITH driver_data AS (
        SELECT 
            jsonb_array_elements(sentiment_data_enhanced->'purchase_drivers') as driver_obj
        FROM clips
        WHERE make = make_filter 
        AND model = model_filter
        AND sentiment_data_enhanced IS NOT NULL
        AND (date_from IS NULL OR published_date >= date_from)
        AND (date_to IS NULL OR published_date <= date_to)
    )
    SELECT 
        driver_obj->>'reason' as reason,
        COUNT(*) FILTER (WHERE driver_obj->>'sentiment' = 'positive') as positive_count,
        COUNT(*) FILTER (WHERE driver_obj->>'sentiment' = 'negative') as negative_count,
        COUNT(*) FILTER (WHERE driver_obj->>'strength' = 'primary') as primary_count,
        COUNT(*) FILTER (WHERE driver_obj->>'strength' = 'secondary') as secondary_count,
        COUNT(*) FILTER (WHERE driver_obj->>'strength' = 'mentioned') as mentioned_count,
        COUNT(*) as total_mentions,
        ARRAY_AGG(DISTINCT driver_obj->>'quote' ORDER BY driver_obj->>'quote' LIMIT 5) as sample_quotes
    FROM driver_data
    GROUP BY driver_obj->>'reason'
    ORDER BY primary_count DESC, total_mentions DESC;
END;
$$ LANGUAGE plpgsql;

-- Add comment explaining the schema
COMMENT ON COLUMN clips.sentiment_data_enhanced IS 'Enhanced sentiment analysis data in JSON format containing key_features_mentioned, brand_attributes_captured, purchase_drivers, and competitive_context';
COMMENT ON COLUMN clips.sentiment_version IS 'Version of sentiment analysis used: v1 (original), v2 (enhanced Message Pull-Through)';

-- Create helper view for backwards compatibility
CREATE OR REPLACE VIEW clips_dashboard_enhanced AS
SELECT 
    c.*,
    -- Include new enhanced fields
    sentiment_data_enhanced,
    sentiment_classification,
    features_count,
    attributes_count,
    drivers_count
FROM clips_dashboard c;