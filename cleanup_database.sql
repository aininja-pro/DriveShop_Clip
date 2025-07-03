-- Cleanup script to drop existing tables
-- Run this FIRST, then run the main supabase_schema.sql

-- Drop tables in reverse order (due to foreign key constraints)
DROP TABLE IF EXISTS clips CASCADE;
DROP TABLE IF EXISTS wo_tracking CASCADE;  
DROP TABLE IF EXISTS processing_runs CASCADE;

-- Drop views if they exist
DROP VIEW IF EXISTS clips_dashboard CASCADE;
DROP VIEW IF EXISTS run_stats CASCADE;

-- Drop functions if they exist
DROP FUNCTION IF EXISTS get_clips_needing_sentiment(UUID[]);
DROP FUNCTION IF EXISTS should_retry_wo(TEXT);

-- Success message
DO $$
BEGIN
    RAISE NOTICE '🧹 Cleanup completed! All tables, views, and functions dropped.';
    RAISE NOTICE '✅ Ready to run supabase_schema.sql for a fresh start.';
END $$; 