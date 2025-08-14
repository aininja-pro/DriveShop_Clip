-- Enhanced schema for background job processing
-- This migration adds fields and tables needed for non-blocking background jobs

-- ========== ENHANCE PROCESSING_RUNS TABLE ==========
-- Add fields for background job tracking
ALTER TABLE processing_runs 
ADD COLUMN IF NOT EXISTS job_type TEXT DEFAULT 'csv_upload' CHECK (job_type IN ('csv_upload', 'historical_reprocessing', 'sentiment_analysis', 'fms_export')),
ADD COLUMN IF NOT EXISTS job_status TEXT DEFAULT 'queued' CHECK (job_status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
ADD COLUMN IF NOT EXISTS job_params JSONB,
ADD COLUMN IF NOT EXISTS created_by TEXT,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS error_message TEXT,
ADD COLUMN IF NOT EXISTS progress_current INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS progress_total INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS worker_id TEXT,
ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP WITH TIME ZONE;

-- Add indexes for job queries
CREATE INDEX IF NOT EXISTS idx_processing_runs_job_status ON processing_runs(job_status);
CREATE INDEX IF NOT EXISTS idx_processing_runs_created_by ON processing_runs(created_by);
CREATE INDEX IF NOT EXISTS idx_processing_runs_job_type ON processing_runs(job_type);
CREATE INDEX IF NOT EXISTS idx_processing_runs_created_at ON processing_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_processing_runs_worker_id ON processing_runs(worker_id);

-- ========== JOB LOGS TABLE ==========
-- Store detailed logs for each job
CREATE TABLE IF NOT EXISTS job_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES processing_runs(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    level TEXT CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    message TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_job_logs_job_id ON job_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_job_logs_timestamp ON job_logs(timestamp DESC);

-- ========== WORKER STATUS TABLE ==========
-- Track worker health and availability
CREATE TABLE IF NOT EXISTS worker_status (
    worker_id TEXT PRIMARY KEY,
    hostname TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'idle' CHECK (status IN ('idle', 'busy', 'offline')),
    current_job_id UUID REFERENCES processing_runs(id),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_worker_status_last_heartbeat ON worker_status(last_heartbeat DESC);

-- ========== JOB QUEUE TABLE ==========
-- Queue for pending jobs (optional, can use processing_runs with job_status='queued')
CREATE TABLE IF NOT EXISTS job_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type TEXT NOT NULL,
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    payload JSONB NOT NULL,
    created_by TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    scheduled_for TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    picked_up_at TIMESTAMP WITH TIME ZONE,
    processing_run_id UUID REFERENCES processing_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_job_queue_priority_scheduled ON job_queue(priority DESC, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_job_queue_picked_up ON job_queue(picked_up_at) WHERE picked_up_at IS NULL;

-- ========== HELPER FUNCTIONS ==========

-- Function to get active jobs for a user
CREATE OR REPLACE FUNCTION get_user_active_jobs(user_email TEXT)
RETURNS TABLE (
    id UUID,
    run_name TEXT,
    job_type TEXT,
    job_status TEXT,
    progress_current INTEGER,
    progress_total INTEGER,
    created_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pr.id,
        pr.run_name,
        pr.job_type,
        pr.job_status,
        pr.progress_current,
        pr.progress_total,
        pr.created_at,
        pr.started_at,
        pr.error_message
    FROM processing_runs pr
    WHERE pr.created_by = user_email
    AND pr.job_status IN ('queued', 'running')
    ORDER BY pr.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to update job progress
CREATE OR REPLACE FUNCTION update_job_progress(
    job_id UUID,
    current_progress INTEGER,
    total_progress INTEGER
) RETURNS VOID AS $$
BEGIN
    UPDATE processing_runs
    SET 
        progress_current = current_progress,
        progress_total = total_progress,
        last_heartbeat = NOW()
    WHERE id = job_id;
END;
$$ LANGUAGE plpgsql;

-- Function to claim next job from queue
CREATE OR REPLACE FUNCTION claim_next_job(worker_id_param TEXT)
RETURNS UUID AS $$
DECLARE
    next_job_id UUID;
BEGIN
    -- Find next queued job
    SELECT id INTO next_job_id
    FROM processing_runs
    WHERE job_status = 'queued'
    ORDER BY created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED;
    
    IF next_job_id IS NOT NULL THEN
        -- Mark job as running and assign to worker
        UPDATE processing_runs
        SET 
            job_status = 'running',
            started_at = NOW(),
            worker_id = worker_id_param,
            last_heartbeat = NOW()
        WHERE id = next_job_id;
        
        -- Update worker status
        INSERT INTO worker_status (worker_id, status, current_job_id, last_heartbeat)
        VALUES (worker_id_param, 'busy', next_job_id, NOW())
        ON CONFLICT (worker_id) DO UPDATE
        SET 
            status = 'busy',
            current_job_id = next_job_id,
            last_heartbeat = NOW();
    END IF;
    
    RETURN next_job_id;
END;
$$ LANGUAGE plpgsql;

-- Function to mark stale jobs as failed (no heartbeat for 5 minutes)
CREATE OR REPLACE FUNCTION cleanup_stale_jobs()
RETURNS INTEGER AS $$
DECLARE
    stale_count INTEGER;
BEGIN
    WITH updated AS (
        UPDATE processing_runs
        SET 
            job_status = 'failed',
            completed_at = NOW(),
            error_message = 'Job timed out - no heartbeat for 5 minutes'
        WHERE job_status = 'running'
        AND last_heartbeat < NOW() - INTERVAL '5 minutes'
        RETURNING 1
    )
    SELECT COUNT(*) INTO stale_count FROM updated;
    
    -- Also mark workers as offline
    UPDATE worker_status
    SET status = 'offline'
    WHERE last_heartbeat < NOW() - INTERVAL '5 minutes';
    
    RETURN stale_count;
END;
$$ LANGUAGE plpgsql;

-- Add RLS policies for job tables
ALTER TABLE job_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_queue ENABLE ROW LEVEL SECURITY;

-- Create policies (adjust based on your auth requirements)
CREATE POLICY "Users can view their own job logs" ON job_logs
    FOR SELECT
    USING (job_id IN (SELECT id FROM processing_runs WHERE created_by = current_user));

CREATE POLICY "Workers can update their status" ON worker_status
    FOR ALL
    USING (worker_id = current_user);

CREATE POLICY "Users can view all worker status" ON worker_status
    FOR SELECT
    USING (true);

CREATE POLICY "Users can create and view their own jobs" ON job_queue
    FOR ALL
    USING (created_by = current_user);

-- Migration completed message
DO $$
BEGIN
    RAISE NOTICE 'Background job tracking schema migration completed successfully';
    RAISE NOTICE 'Tables created/modified: processing_runs (enhanced), job_logs, worker_status, job_queue';
    RAISE NOTICE 'Helper functions added for job management';
END $$;