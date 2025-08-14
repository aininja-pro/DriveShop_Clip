-- Fix RLS policies for worker_status table to allow service role access

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Workers can update their status" ON worker_status;
DROP POLICY IF EXISTS "Users can view all worker status" ON worker_status;

-- Create new policies that allow service role (backend) access
CREATE POLICY "Service role full access to worker_status" ON worker_status
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Also fix job_logs table
DROP POLICY IF EXISTS "Users can view their own job logs" ON job_logs;

CREATE POLICY "Service role full access to job_logs" ON job_logs
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Fix job_queue table
DROP POLICY IF EXISTS "Users can create and view their own jobs" ON job_queue;

CREATE POLICY "Service role full access to job_queue" ON job_queue
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Verify the policies are created
SELECT tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies
WHERE tablename IN ('worker_status', 'job_logs', 'job_queue')
ORDER BY tablename, policyname;