-- DriveShop Clip Tracking Database Schema
-- Run this SQL in your Supabase SQL Editor to create all required tables

-- Enable UUID extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========== PROCESSING RUNS TABLE ==========
-- Tracks each batch processing session
CREATE TABLE processing_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_name TEXT NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_time TIMESTAMP WITH TIME ZONE,
    total_records INTEGER DEFAULT 0,
    successful_finds INTEGER DEFAULT 0,
    failed_attempts INTEGER DEFAULT 0,
    run_status TEXT DEFAULT 'running' CHECK (run_status IN ('running', 'completed', 'failed'))
);

-- ========== CLIPS TABLE ==========  
-- Stores all found clips with their metadata and analysis
CREATE TABLE clips (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wo_number TEXT NOT NULL,
    processing_run_id UUID REFERENCES processing_runs(id) ON DELETE CASCADE,
    
    -- Loan metadata
    office TEXT,
    make TEXT,
    model TEXT,
    contact TEXT,
    person_id TEXT,
    activity_id TEXT,
    
    -- Clip data (only for successful finds)
    clip_url TEXT,
    extracted_content TEXT,
    published_date DATE,
    attribution_strength TEXT CHECK (attribution_strength IN ('strong', 'delegated', 'unknown')),
    byline_author TEXT,
    
    -- Processing metadata
    processed_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tier_used TEXT,
    status TEXT DEFAULT 'pending_review' CHECK (status IN ('pending_review', 'approved', 'rejected', 'no_content_found', 'processing_failed')),
    workflow_stage TEXT DEFAULT 'found' CHECK (workflow_stage IN ('found', 'sentiment_analyzed', 'exported')),
    
    -- Smart retry logic
    last_attempt_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    attempt_count INTEGER DEFAULT 1,
    last_attempt_result TEXT,
    retry_after_date TIMESTAMP WITH TIME ZONE,
    
    -- Sentiment data (added later via batch processing)
    relevance_score INTEGER CHECK (relevance_score >= 0 AND relevance_score <= 10),
    overall_sentiment TEXT CHECK (overall_sentiment IN ('positive', 'neutral', 'negative')),
    brand_alignment BOOLEAN,
    summary TEXT,
    sentiment_analysis_date TIMESTAMP WITH TIME ZONE
);

-- ========== WO TRACKING TABLE ==========
-- Smart retry logic to avoid repeated failures
CREATE TABLE wo_tracking (
    wo_number TEXT PRIMARY KEY,
    status TEXT DEFAULT 'searching' CHECK (status IN ('searching', 'found', 'exhausted')),
    last_attempt_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    attempt_count INTEGER DEFAULT 0,
    found_clip_url TEXT,
    retry_after_date TIMESTAMP WITH TIME ZONE
);

-- ========== INDEXES FOR PERFORMANCE ==========

-- Processing runs indexes
CREATE INDEX idx_processing_runs_start_time ON processing_runs(start_time DESC);
CREATE INDEX idx_processing_runs_status ON processing_runs(run_status);

-- Clips indexes  
CREATE INDEX idx_clips_wo_number ON clips(wo_number);
CREATE INDEX idx_clips_processing_run_id ON clips(processing_run_id);
CREATE INDEX idx_clips_status ON clips(status);
CREATE INDEX idx_clips_workflow_stage ON clips(workflow_stage);
CREATE INDEX idx_clips_status_workflow ON clips(status, workflow_stage);
CREATE INDEX idx_clips_processed_date ON clips(processed_date DESC);
CREATE INDEX idx_clips_sentiment_analysis ON clips(status, sentiment_analysis_date) WHERE status = 'approved';

-- WO tracking indexes
CREATE INDEX idx_wo_tracking_status ON wo_tracking(status);
CREATE INDEX idx_wo_tracking_retry_date ON wo_tracking(retry_after_date) WHERE retry_after_date IS NOT NULL;

-- ========== ROW LEVEL SECURITY (RLS) ==========
-- Enable RLS for all tables (you can customize these policies)

-- Enable RLS
ALTER TABLE processing_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE clips ENABLE ROW LEVEL SECURITY;
ALTER TABLE wo_tracking ENABLE ROW LEVEL SECURITY;

-- Create policies (adjust these based on your security needs)
-- For now, allow all operations with authenticated users

-- Processing runs policies
CREATE POLICY "Enable all for authenticated users" ON processing_runs
    FOR ALL USING (auth.role() = 'authenticated');

-- Clips policies  
CREATE POLICY "Enable all for authenticated users" ON clips
    FOR ALL USING (auth.role() = 'authenticated');

-- WO tracking policies
CREATE POLICY "Enable all for authenticated users" ON wo_tracking
    FOR ALL USING (auth.role() = 'authenticated');

-- ========== HELPFUL VIEWS ==========

-- View for dashboard display
CREATE VIEW clips_dashboard AS
SELECT 
    c.id,
    c.wo_number,
    c.office,
    c.make,
    c.model,
    c.contact,
    c.person_id,
    c.clip_url,
    c.published_date,
    c.attribution_strength,
    c.byline_author,
    c.status,
    c.workflow_stage,
    c.relevance_score,
    c.overall_sentiment,
    c.brand_alignment,
    c.summary,
    c.processed_date,
    c.tier_used,
    pr.run_name,
    pr.start_time as run_start_time
FROM clips c
LEFT JOIN processing_runs pr ON c.processing_run_id = pr.id
ORDER BY c.processed_date DESC;

-- View for run statistics
CREATE VIEW run_stats AS
SELECT 
    pr.id as run_id,
    pr.run_name,
    pr.start_time,
    pr.end_time,
    pr.total_records,
    pr.successful_finds,
    pr.failed_attempts,
    pr.run_status,
    COUNT(c.id) as total_clips,
    COUNT(CASE WHEN c.status = 'approved' THEN 1 END) as approved_clips,
    COUNT(CASE WHEN c.status = 'rejected' THEN 1 END) as rejected_clips,
    COUNT(CASE WHEN c.status = 'pending_review' THEN 1 END) as pending_clips,
    COUNT(CASE WHEN c.sentiment_analysis_date IS NOT NULL THEN 1 END) as clips_with_sentiment,
    ROUND(AVG(c.relevance_score), 1) as avg_relevance_score,
    CASE 
        WHEN pr.total_records > 0 THEN ROUND((pr.successful_finds::DECIMAL / pr.total_records * 100), 1)
        ELSE 0 
    END as success_rate_pct
FROM processing_runs pr
LEFT JOIN clips c ON pr.id = c.processing_run_id
GROUP BY pr.id, pr.run_name, pr.start_time, pr.end_time, pr.total_records, pr.successful_finds, pr.failed_attempts, pr.run_status
ORDER BY pr.start_time DESC;

-- ========== FUNCTIONS ==========

-- Function to get clips needing sentiment analysis
CREATE OR REPLACE FUNCTION get_clips_needing_sentiment(run_ids UUID[] DEFAULT NULL)
RETURNS TABLE (
    id UUID,
    wo_number TEXT,
    extracted_content TEXT,
    make TEXT,
    model TEXT
) 
LANGUAGE sql
AS $$
    SELECT c.id, c.wo_number, c.extracted_content, c.make, c.model
    FROM clips c
    WHERE c.status = 'approved' 
    AND c.sentiment_analysis_date IS NULL
    AND (run_ids IS NULL OR c.processing_run_id = ANY(run_ids))
    ORDER BY c.processed_date DESC;
$$;

-- Function to check if WO should be retried
CREATE OR REPLACE FUNCTION should_retry_wo(wo_num TEXT)
RETURNS BOOLEAN
LANGUAGE sql
AS $$
    SELECT CASE 
        WHEN NOT EXISTS (SELECT 1 FROM wo_tracking WHERE wo_number = wo_num) THEN TRUE  -- Never tried
        WHEN wt.status = 'found' THEN FALSE  -- Already found
        WHEN wt.retry_after_date IS NOT NULL AND wt.retry_after_date > NOW() THEN FALSE  -- In cooldown
        ELSE TRUE  -- Ready to retry
    END
    FROM wo_tracking wt 
    WHERE wt.wo_number = wo_num;
$$;

-- ========== SAMPLE DATA (OPTIONAL) ==========
-- Uncomment to insert sample data for testing

/*
-- Sample processing run
INSERT INTO processing_runs (run_name, total_records, successful_finds, failed_attempts, run_status, end_time)
VALUES ('Sample_Run_20250101_120000', 10, 7, 3, 'completed', NOW());

-- Sample clips (get the run_id from the inserted row)
WITH sample_run AS (
    SELECT id FROM processing_runs WHERE run_name = 'Sample_Run_20250101_120000'
)
INSERT INTO clips (wo_number, processing_run_id, office, make, model, contact, clip_url, status, tier_used, extracted_content)
VALUES 
    ('12345', (SELECT id FROM sample_run), 'West Coast', 'Toyota', 'Camry', 'John Doe', 'https://example.com/camry-review', 'pending_review', 'Tier 1: Basic HTTP', 'Great review of the 2024 Toyota Camry...'),
    ('12346', (SELECT id FROM sample_run), 'East Coast', 'Honda', 'Civic', 'Jane Smith', 'https://example.com/civic-test', 'approved', 'Tier 2: Enhanced HTTP', 'Honda Civic continues to impress...');

-- Sample WO tracking
INSERT INTO wo_tracking (wo_number, status, attempt_count, found_clip_url)
VALUES 
    ('12345', 'found', 1, 'https://example.com/camry-review'),
    ('12347', 'searching', 2, NULL);
*/

-- ========== COMPLETION MESSAGE ==========
DO $$
BEGIN
    RAISE NOTICE '✅ DriveShop Clip Tracking database schema created successfully!';
    RAISE NOTICE '📊 Tables created: processing_runs, clips, wo_tracking';
    RAISE NOTICE '🔍 Views created: clips_dashboard, run_stats';
    RAISE NOTICE '⚡ Functions created: get_clips_needing_sentiment, should_retry_wo';
    RAISE NOTICE '🛡️ Row Level Security enabled on all tables';
END $$; 