-- Fix Row Level Security policies to allow operations
-- Run this in Supabase SQL Editor to fix the RLS issue

-- Drop existing restrictive policies
DROP POLICY IF EXISTS "Enable all for authenticated users" ON processing_runs;
DROP POLICY IF EXISTS "Enable all for authenticated users" ON clips;
DROP POLICY IF EXISTS "Enable all for authenticated users" ON wo_tracking;

-- Create permissive policies that allow all operations
-- (In production, you'd want more restrictive policies)

-- Processing runs policies - allow all operations
CREATE POLICY "Allow all operations" ON processing_runs
    FOR ALL USING (true);

-- Clips policies - allow all operations
CREATE POLICY "Allow all operations" ON clips
    FOR ALL USING (true);

-- WO tracking policies - allow all operations  
CREATE POLICY "Allow all operations" ON wo_tracking
    FOR ALL USING (true);

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ RLS policies updated successfully!';
    RAISE NOTICE '🔓 All operations now allowed on all tables';
    RAISE NOTICE '⚠️ In production, consider more restrictive policies';
END $$; 