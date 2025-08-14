# Background Jobs Deployment Guide

## Overview

This guide explains how to deploy the new background job processing system for DriveShop Clip. The system allows long-running processes (2-3 hours) to run in the background without blocking the UI, and jobs persist even if users log out.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Browser   │────▶│   Dashboard  │────▶│   Database   │
│             │     │  (Streamlit) │     │  (Supabase)  │
└─────────────┘     └──────────────┘     └──────────────┘
                                                 ▲
                                                 │
                                          ┌──────────────┐
                                          │   Workers    │
                                          │  (1-3 pods)  │
                                          └──────────────┘
```

## Components

### 1. Database Schema Changes
- Enhanced `processing_runs` table with job tracking fields
- New tables: `job_logs`, `worker_status`, `job_queue`
- Helper functions for job management

### 2. Background Worker Service
- `src/worker/background_worker.py` - Main worker process
- `src/worker/health_check.py` - Health monitoring endpoint
- Processes jobs from queue asynchronously

### 3. Dashboard Updates
- **Active Jobs Tab** - Monitor running/queued jobs
- **Non-blocking submission** - Jobs queued instead of blocking UI
- **Progress tracking** - Real-time progress updates

## Deployment Steps

### Step 1: Apply Database Migration

1. Connect to your Supabase database
2. Run the migration script:

```sql
-- Run this in Supabase SQL Editor
-- File: migrations/add_background_job_tracking.sql
```

### Step 2: Deploy Worker Service to Render

1. **Create a new Background Worker service on Render:**
   - Go to Render Dashboard
   - Click "New +" → "Background Worker"
   - Connect your GitHub repository
   - Name: `driveshop-clip-worker`

2. **Configure the worker:**
   - Runtime: Python 3.11
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python -m src.worker.background_worker`
   
3. **Set Environment Variables:**
   ```
   SUPABASE_URL=<your-supabase-url>
   SUPABASE_KEY=<your-supabase-key>
   OPENAI_API_KEY=<your-openai-key>
   LOG_LEVEL=INFO
   WORKER_ID=worker-1  # or auto-generate
   ```

4. **Configure Scaling (optional for paid plans):**
   - Min Instances: 1
   - Max Instances: 3
   - Target CPU: 70%

### Step 3: Update Dashboard Application

1. **Update app.py to include Active Jobs tab:**

```python
# Add import at the top
from src.dashboard.active_jobs_tab import display_active_jobs_tab

# Update tabs list (around line 2449)
active_jobs_tab, bulk_review_tab, approved_queue_tab, ... = st.tabs([
    "🚀 Active Jobs",  # NEW TAB
    "Bulk Review",
    ...
])

# Add Active Jobs tab content
with active_jobs_tab:
    display_active_jobs_tab()
```

2. **Update Process Filtered button to use job queue:**

Replace the existing handler (around line 2285-2404) with the non-blocking version from `app_job_submission.py`.

### Step 4: Deploy Dashboard Changes

1. Commit all changes to your repository
2. Render will auto-deploy if configured, or manually trigger deployment
3. Verify the new Active Jobs tab appears in the dashboard

## Testing the System

### 1. Submit a Test Job

1. Log into the dashboard
2. Load data from URL as usual
3. Apply filters if needed
4. Click "Process Filtered"
5. You should see a success message with Job ID

### 2. Monitor Job Progress

1. Navigate to "Active Jobs" tab
2. You should see your job in the queue or running
3. Progress bar shows real-time updates
4. Logs show detailed processing information

### 3. Test Persistence

1. Submit a job
2. Log out of the dashboard
3. Log back in
4. Go to Active Jobs - your job should still be there
5. Once complete, check Bulk Review for results

## Monitoring & Maintenance

### Check Worker Health

```bash
# Via Render Dashboard
# Look for worker service status

# Via Database
SELECT * FROM worker_status 
ORDER BY last_heartbeat DESC;

# Check stale jobs
SELECT * FROM processing_runs 
WHERE job_status = 'running' 
AND last_heartbeat < NOW() - INTERVAL '5 minutes';
```

### View Job Logs

```sql
-- Recent logs for a specific job
SELECT * FROM job_logs 
WHERE job_id = '<job-id>'
ORDER BY timestamp DESC 
LIMIT 50;
```

### Clean Up Stale Jobs

```sql
-- Run periodically or set up as scheduled job
SELECT cleanup_stale_jobs();
```

## Troubleshooting

### Worker Not Processing Jobs

1. Check worker is running in Render dashboard
2. Verify environment variables are set correctly
3. Check database connectivity
4. Review worker logs in Render

### Jobs Stuck in Queue

1. Ensure at least one worker is running
2. Check for stale jobs blocking the queue
3. Run cleanup function: `SELECT cleanup_stale_jobs();`

### Progress Not Updating

1. Check worker heartbeat in database
2. Verify progress callback is working
3. Check for errors in job_logs table

## Configuration Options

### Worker Settings (Environment Variables)

- `MAX_CONCURRENT_JOBS`: Number of jobs per worker (default: 1)
- `HEARTBEAT_INTERVAL`: Seconds between heartbeats (default: 30)
- `JOB_TIMEOUT`: Maximum seconds per job (default: 10800 = 3 hours)
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)

### Scaling Options

For high load, you can:
1. Increase worker instances (Render scaling)
2. Increase MAX_CONCURRENT_JOBS per worker
3. Optimize job processing logic

## Security Considerations

1. **Authentication**: Jobs are tied to user emails
2. **RLS Policies**: Users can only see their own jobs
3. **API Keys**: Store securely in Render environment
4. **Job Isolation**: Each job runs independently

## Rollback Plan

If issues arise:

1. **Quick Disable**: Set all workers to 0 instances in Render
2. **Revert Code**: Git revert the dashboard changes
3. **Database Cleanup**: 
   ```sql
   UPDATE processing_runs 
   SET job_status = 'failed' 
   WHERE job_status IN ('queued', 'running');
   ```

## Future Enhancements

- [ ] Job prioritization based on user tier
- [ ] Email notifications on job completion
- [ ] Scheduled jobs (daily/weekly processing)
- [ ] Job retry logic with exponential backoff
- [ ] Cost tracking per job
- [ ] Export job results to S3/cloud storage

## Support

For issues or questions:
1. Check worker logs in Render dashboard
2. Review job_logs table in database
3. Contact the development team with Job ID and error details