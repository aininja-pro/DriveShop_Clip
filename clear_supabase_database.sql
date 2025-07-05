-- ========================================
-- CLEAR SUPABASE DATABASE FOR CLEAN TESTING
-- ========================================
-- This script completely clears all data from the DriveShop Clip Tracking database
-- while preserving the table structure and relationships.
-- 
-- USE WITH CAUTION: This will permanently delete ALL data!
-- 
-- To run this in Supabase:
-- 1. Go to your Supabase project
-- 2. Navigate to SQL Editor
-- 3. Copy and paste this entire script
-- 4. Click "Run" to execute
-- ========================================

-- Start transaction for safety
BEGIN;

-- Disable foreign key checks temporarily for faster deletion
SET session_replication_role = replica;

-- ========== CLEAR ALL DATA ==========
-- Delete in order to respect foreign key constraints

-- 1. Clear clips table first (has foreign key to processing_runs)
DELETE FROM clips;

-- 2. Clear wo_tracking table (independent)
DELETE FROM wo_tracking;

-- 3. Clear processing_runs table last (referenced by clips)
DELETE FROM processing_runs;

-- Re-enable foreign key checks
SET session_replication_role = DEFAULT;

-- ========== RESET SEQUENCES (if any) ==========
-- Note: UUID primary keys don't use sequences, so no reset needed

-- ========== VERIFICATION ==========
-- Check that all tables are empty
DO $$
DECLARE
    clips_count INTEGER;
    wo_tracking_count INTEGER;
    processing_runs_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO clips_count FROM clips;
    SELECT COUNT(*) INTO wo_tracking_count FROM wo_tracking;
    SELECT COUNT(*) INTO processing_runs_count FROM processing_runs;
    
    RAISE NOTICE '🗑️ Database clearing completed';
    RAISE NOTICE '📊 VERIFICATION RESULTS:';
    RAISE NOTICE '   clips table: % records', clips_count;
    RAISE NOTICE '   wo_tracking table: % records', wo_tracking_count;
    RAISE NOTICE '   processing_runs table: % records', processing_runs_count;
    
    IF clips_count = 0 AND wo_tracking_count = 0 AND processing_runs_count = 0 THEN
        RAISE NOTICE '✅ SUCCESS: All tables are now empty and ready for clean testing!';
        RAISE NOTICE '🧪 Ready for clean testing of WO #1202058 (Lexus RX 350h)';
        RAISE NOTICE '📝 Next steps:';
        RAISE NOTICE '   1. Run your DriveShop clip processing';
        RAISE NOTICE '   2. Check that WO #1202058 is found and processed correctly';
        RAISE NOTICE '   3. Verify the Lexus article appears in Bulk Review tab';
    ELSE
        RAISE NOTICE '❌ WARNING: Some tables still contain data. Check for errors.';
    END IF;
END $$;

-- ========== OPTIONAL: RESET AUTO-INCREMENT COUNTERS ==========
-- (Not needed for UUID primary keys, but included for completeness)
-- If you had SERIAL columns, you would reset them like this:
-- ALTER SEQUENCE your_sequence_name RESTART WITH 1;

-- Commit the transaction
COMMIT;

-- Final completion message
DO $$
BEGIN
    RAISE NOTICE '🎯 Database cleared successfully!';
END $$; 