-- Create a process tracking table to monitor long-running jobs
CREATE TABLE IF NOT EXISTS process_tracking (
    id SERIAL PRIMARY KEY,
    process_id UUID DEFAULT gen_random_uuid(),
    process_type VARCHAR(50) NOT NULL, -- 'bulk_search', 'channel_scan', etc.
    started_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'running', -- 'running', 'completed', 'failed'
    total_items INTEGER,
    processed_items INTEGER DEFAULT 0,
    found_items INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    metadata JSONB, -- Store work orders, search params, etc.
    last_heartbeat TIMESTAMP DEFAULT NOW()
);

-- Create indexes for quick lookups
CREATE INDEX idx_process_tracking_status ON process_tracking(status);
CREATE INDEX idx_process_tracking_started ON process_tracking(started_at DESC);

-- Function to update heartbeat
CREATE OR REPLACE FUNCTION update_process_heartbeat(p_process_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE process_tracking 
    SET last_heartbeat = NOW(),
        updated_at = NOW()
    WHERE process_id = p_process_id;
END;
$$ LANGUAGE plpgsql;

-- View to see active processes (heartbeat within last 5 minutes)
CREATE VIEW active_processes AS
SELECT 
    process_id,
    process_type,
    started_at,
    EXTRACT(EPOCH FROM (NOW() - started_at))/60 as minutes_running,
    processed_items || '/' || total_items as progress,
    ROUND((processed_items::numeric / NULLIF(total_items, 0) * 100), 1) as percent_complete,
    last_heartbeat,
    metadata
FROM process_tracking
WHERE status = 'running' 
    AND last_heartbeat > NOW() - INTERVAL '5 minutes'
ORDER BY started_at DESC;