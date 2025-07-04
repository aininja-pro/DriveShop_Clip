-- Clean Database Script
-- Run this in Supabase SQL Editor to delete all existing records

-- Delete in order to respect foreign key constraints

-- 1. Delete all clips first (they reference processing_runs)
DELETE FROM clips;

-- 2. Delete all wo_tracking records
DELETE FROM wo_tracking;

-- 3. Delete all processing_runs
DELETE FROM processing_runs;

-- Reset any sequences if needed (optional)
-- This ensures new IDs start from 1 again
-- ALTER SEQUENCE clips_id_seq RESTART WITH 1;
-- ALTER SEQUENCE processing_runs_id_seq RESTART WITH 1;

-- Verify everything is clean
SELECT 'clips' as table_name, COUNT(*) as record_count FROM clips
UNION ALL
SELECT 'wo_tracking' as table_name, COUNT(*) as record_count FROM wo_tracking  
UNION ALL
SELECT 'processing_runs' as table_name, COUNT(*) as record_count FROM processing_runs;

-- Should show 0 records for all tables 