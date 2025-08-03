-- OEM Messaging Schema - Mirrors Enhanced Sentiment Structure for Direct Comparison
-- This allows true Message Pull-Through Analysis comparing what OEMs want said vs what actually gets said
--
-- Run this in Supabase SQL Editor:
-- 1. Go to SQL Editor in Supabase Dashboard
-- 2. Create new query
-- 3. Paste this entire file
-- 4. Run the query

-- 1. OEM Messaging Sources (Documents, Web Pages, etc)
CREATE TABLE oem_messaging_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    make VARCHAR(100) NOT NULL,
    document_title VARCHAR(500),
    document_type VARCHAR(50), -- 'media_guide', 'press_release', 'dealer_bulletin', 'web_page'
    source_url TEXT,
    source_file_path TEXT,
    model_year INTEGER,
    extracted_date TIMESTAMP DEFAULT NOW(),
    raw_content TEXT, -- Store original content
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. OEM Model Messaging (One record per model/year/trim combination)
CREATE TABLE oem_model_messaging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES oem_messaging_sources(id),
    make VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    trim_level VARCHAR(100),
    
    -- Overall positioning (mirrors our sentiment summary)
    positioning_statement TEXT,
    target_audience TEXT,
    
    -- Store the complete extracted messaging as JSONB (mirrors sentiment_data_enhanced)
    messaging_data_enhanced JSONB,
    
    -- Metadata
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Unique constraint to prevent duplicates
    UNIQUE(make, model, year, trim_level, version)
);

-- 3. OEM Key Features (Mirrors key_features_mentioned from sentiment)
CREATE TABLE oem_key_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_messaging_id UUID REFERENCES oem_model_messaging(id),
    
    feature VARCHAR(500) NOT NULL,
    feature_category VARCHAR(100), -- 'performance', 'technology', 'design', 'safety', etc.
    priority VARCHAR(50), -- 'primary', 'secondary', 'tertiary'
    messaging_points TEXT, -- How OEM wants it described
    target_sentiment VARCHAR(50) DEFAULT 'positive', -- What sentiment they're aiming for
    supporting_stats TEXT, -- Any data points they provide
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- 4. OEM Brand Attributes (Mirrors brand_attributes_identified)
CREATE TABLE oem_brand_attributes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_messaging_id UUID REFERENCES oem_model_messaging(id),
    
    attribute VARCHAR(200) NOT NULL,
    attribute_category VARCHAR(100), -- 'heritage', 'innovation', 'value', 'performance'
    importance VARCHAR(50), -- 'core', 'supporting', 'aspirational'
    messaging_guidance TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- 5. OEM Purchase Drivers (Mirrors purchase_drivers from sentiment)
CREATE TABLE oem_purchase_drivers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_messaging_id UUID REFERENCES oem_model_messaging(id),
    
    reason VARCHAR(200) NOT NULL,
    target_audience VARCHAR(200), -- 'ST buyers', 'PHEV buyers', 'families', etc.
    priority INTEGER, -- 1-5 priority ranking
    supporting_features TEXT, -- Which features support this driver
    messaging_points TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- 6. OEM Competitive Positioning (Mirrors competitive_context)
CREATE TABLE oem_competitive_positioning (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_messaging_id UUID REFERENCES oem_model_messaging(id),
    
    competitor_make VARCHAR(100),
    competitor_model VARCHAR(100),
    comparison_type VARCHAR(50), -- 'direct', 'aspirational', 'value'
    
    -- Our advantages
    advantages JSONB, -- Array of advantage points
    -- Their advantages (acknowledged)
    competitor_advantages JSONB,
    
    positioning_strategy TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- 7. Message Pull-Through Tracking (Links OEM messages to actual sentiment results)
CREATE TABLE message_pull_through (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- OEM side
    model_messaging_id UUID REFERENCES oem_model_messaging(id),
    oem_feature_id UUID REFERENCES oem_key_features(id),
    oem_attribute_id UUID REFERENCES oem_brand_attributes(id),
    oem_driver_id UUID REFERENCES oem_purchase_drivers(id),
    
    -- Media/Review side
    clip_id UUID REFERENCES clips(id),
    
    -- Analysis results
    pull_through_status VARCHAR(50), -- 'exact_match', 'partial_match', 'sentiment_mismatch', 'not_mentioned'
    sentiment_alignment VARCHAR(50), -- 'aligned', 'neutral', 'opposite'
    
    notes TEXT,
    
    analyzed_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_oem_model_messaging_make_model ON oem_model_messaging(make, model, year);
CREATE INDEX idx_oem_key_features_model ON oem_key_features(model_messaging_id);
CREATE INDEX idx_oem_brand_attributes_model ON oem_brand_attributes(model_messaging_id);
CREATE INDEX idx_oem_purchase_drivers_model ON oem_purchase_drivers(model_messaging_id);
CREATE INDEX idx_message_pull_through_clip ON message_pull_through(clip_id);
CREATE INDEX idx_message_pull_through_model ON message_pull_through(model_messaging_id);

-- Function to get all OEM messaging for a model as JSON (similar to our enhanced sentiment)
CREATE OR REPLACE FUNCTION get_oem_messaging_json(model_id UUID)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'positioning_statement', m.positioning_statement,
        'target_audience', m.target_audience,
        'key_features_intended', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'feature', feature,
                    'category', feature_category,
                    'priority', priority,
                    'messaging', messaging_points,
                    'target_sentiment', target_sentiment
                ) ORDER BY priority
            )
            FROM oem_key_features
            WHERE model_messaging_id = model_id
        ),
        'brand_attributes_intended', (
            SELECT jsonb_agg(attribute ORDER BY importance)
            FROM oem_brand_attributes
            WHERE model_messaging_id = model_id
        ),
        'purchase_drivers_intended', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'reason', reason,
                    'priority', priority,
                    'target_audience', target_audience,
                    'messaging', messaging_points
                ) ORDER BY priority
            )
            FROM oem_purchase_drivers
            WHERE model_messaging_id = model_id
        ),
        'competitive_positioning', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'competitor', competitor_make || ' ' || competitor_model,
                    'advantages', advantages,
                    'strategy', positioning_strategy
                )
            )
            FROM oem_competitive_positioning
            WHERE model_messaging_id = model_id
        )
    ) INTO result
    FROM oem_model_messaging m
    WHERE m.id = model_id;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Sample view for easy comparison
CREATE VIEW oem_vs_media_comparison AS
SELECT 
    c.wo_number,
    c.make,
    c.model,
    c.published_date,
    c.media_outlet,
    omm.positioning_statement as oem_positioning,
    c.sentiment_data_enhanced->>'summary' as media_summary,
    c.sentiment_data_enhanced->'key_features_mentioned' as media_features,
    get_oem_messaging_json(omm.id)->'key_features_intended' as oem_features
FROM clips c
JOIN oem_model_messaging omm ON 
    c.make = omm.make AND 
    c.model = omm.model AND
    EXTRACT(YEAR FROM c.published_date) = omm.year
WHERE c.sentiment_completed = true;