"""
Background worker service for processing long-running jobs.
Designed to run as a separate process on Render, pulling jobs from the queue.
"""

import os
import sys
import time
import signal
import asyncio
import json
import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.logger import setup_logger
from src.utils.database import get_database
from src.ingest.ingest_database import run_ingest_database_with_filters, load_loans_data_from_url
from src.utils.sentiment_analysis import run_sentiment_analysis
from src.utils.fms_api import FMSAPIClient

# Setup logging
logger = setup_logger(__name__)

class BackgroundWorker:
    """Background worker that processes jobs from the queue"""
    
    def __init__(self, worker_id: Optional[str] = None):
        """Initialize the worker"""
        self.worker_id = worker_id or f"worker_{os.getpid()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.db = get_database()
        self.running = False
        self.current_job_id = None
        self.heartbeat_interval = 5  # seconds - reduced for faster cancellation response
        self.last_heartbeat = time.time()
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        logger.info(f"Worker {self.worker_id} initialized")
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Worker {self.worker_id} received shutdown signal")
        self.running = False
        
        # Check if this is a cancellation vs actual shutdown
        if self.current_job_id:
            try:
                # Check if job was cancelled
                result = self.db.supabase.table('processing_runs').select('job_status').eq(
                    'id', self.current_job_id
                ).single().execute()
                
                if result.data and result.data.get('job_status') == 'cancelled':
                    # Job was cancelled, just clean up
                    logger.info(f"Job {self.current_job_id} was cancelled, cleaning up")
                    self.current_job_id = None
                    # Don't exit, continue to next job
                    return
                else:
                    # Real shutdown, requeue the job
                    self.db.supabase.table('processing_runs').update({
                        'job_status': 'queued',
                        'worker_id': None,
                        'error_message': 'Worker shutdown - job will be retried'
                    }).eq('id', self.current_job_id).execute()
            except Exception as e:
                logger.error(f"Failed to handle job {self.current_job_id}: {e}")
        
        # Mark worker as offline
        try:
            self.db.supabase.table('worker_status').update({
                'status': 'offline',
                'current_job_id': None
            }).eq('worker_id', self.worker_id).execute()
        except:
            pass
        
        sys.exit(0)
    
    def register_worker(self):
        """Register this worker in the database"""
        try:
            import socket
            hostname = socket.gethostname()
            
            self.db.supabase.table('worker_status').upsert({
                'worker_id': self.worker_id,
                'hostname': hostname,
                'started_at': datetime.now(timezone.utc).isoformat(),
                'last_heartbeat': datetime.now(timezone.utc).isoformat(),
                'status': 'idle',
                'metadata': {
                    'pid': os.getpid(),
                    'python_version': sys.version,
                    'render_service': os.environ.get('RENDER_SERVICE_NAME', 'unknown')
                }
            }).execute()
            
            logger.info(f"Worker {self.worker_id} registered successfully")
        except Exception as e:
            logger.error(f"Failed to register worker: {e}")
            raise
    
    def send_heartbeat(self):
        """Send heartbeat to indicate worker is alive"""
        try:
            now = time.time()
            if now - self.last_heartbeat >= self.heartbeat_interval:
                # Check for cancellation on every heartbeat
                if self.current_job_id and self.check_if_cancelled():
                    raise Exception("Job cancelled by user")
                
                # Update worker heartbeat
                self.db.supabase.table('worker_status').update({
                    'last_heartbeat': datetime.now(timezone.utc).isoformat()
                }).eq('worker_id', self.worker_id).execute()
                
                # Update job heartbeat if processing
                if self.current_job_id:
                    self.db.supabase.table('processing_runs').update({
                        'last_heartbeat': datetime.now(timezone.utc).isoformat()
                    }).eq('id', self.current_job_id).execute()
                
                self.last_heartbeat = now
                logger.debug(f"Heartbeat sent for worker {self.worker_id}")
        except Exception as e:
            if "cancelled by user" in str(e).lower():
                raise  # Re-raise cancellation
            logger.error(f"Failed to send heartbeat: {e}")
    
    def check_if_cancelled(self) -> bool:
        """Check if the current job has been cancelled"""
        if not self.current_job_id:
            return False
        
        try:
            result = self.db.supabase.table('processing_runs').select('job_status').eq(
                'id', self.current_job_id
            ).single().execute()
            
            if result.data and result.data.get('job_status') == 'cancelled':
                logger.info(f"Job {self.current_job_id} has been cancelled")
                return True
        except Exception as e:
            logger.error(f"Failed to check job status: {e}")
        
        return False
    
    def claim_job(self) -> Optional[Dict[str, Any]]:
        """Claim the next available job from the queue"""
        try:
            # Try the RPC function first
            result = self.db.supabase.rpc('claim_next_job', {
                'worker_id_param': self.worker_id
            }).execute()
            
            if result.data:
                job_id = result.data
                self.current_job_id = job_id
                
                # Force update to ensure it shows as running
                self.db.supabase.table('processing_runs').update({
                    'job_status': 'running',
                    'worker_id': self.worker_id,
                    'started_at': datetime.now(timezone.utc).isoformat(),
                    'last_heartbeat': datetime.now(timezone.utc).isoformat()
                }).eq('id', job_id).execute()
                
                # Now fetch the full job details
                job_result = self.db.supabase.table('processing_runs').select('*').eq('id', job_id).single().execute()
                if job_result.data:
                    logger.info(f"Worker {self.worker_id} claimed job {job_id}: {job_result.data.get('run_name')}")
                    
                    # Update worker status
                    self.db.supabase.table('worker_status').upsert({
                        'worker_id': self.worker_id,
                        'status': 'busy',
                        'current_job_id': job_id,
                        'last_heartbeat': datetime.now(timezone.utc).isoformat()
                    }).execute()
                    
                    return job_result.data
            
            # Fallback: Try direct query if RPC doesn't work
            jobs = self.db.supabase.table('processing_runs').select('*').eq(
                'job_status', 'queued'
            ).order('created_at').limit(1).execute()
            
            if jobs.data and len(jobs.data) > 0:
                job = jobs.data[0]
                # Try to claim it
                update_result = self.db.supabase.table('processing_runs').update({
                    'job_status': 'running',
                    'started_at': datetime.now(timezone.utc).isoformat(),
                    'worker_id': self.worker_id,
                    'last_heartbeat': datetime.now(timezone.utc).isoformat()
                }).eq('id', job['id']).eq('job_status', 'queued').execute()
                
                if update_result.data:
                    self.current_job_id = job['id']
                    logger.info(f"Worker {self.worker_id} claimed job {job['id']} via fallback: {job.get('run_name')}")
                    
                    # Update worker status
                    self.db.supabase.table('worker_status').upsert({
                        'worker_id': self.worker_id,
                        'status': 'busy',
                        'current_job_id': job['id'],
                        'last_heartbeat': datetime.now(timezone.utc).isoformat()
                    }).execute()
                    
                    return job
            
            return None
        except Exception as e:
            logger.error(f"Failed to claim job: {e}")
            return None
    
    def log_job_message(self, level: str, message: str, metadata: Optional[Dict] = None):
        """Log a message for the current job"""
        if not self.current_job_id:
            return
        
        try:
            self.db.supabase.table('job_logs').insert({
                'job_id': self.current_job_id,
                'level': level,
                'message': message,
                'metadata': metadata or {}
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log job message: {e}")
    
    def update_job_progress(self, current: int, total: int):
        """Update job progress"""
        if not self.current_job_id:
            return
        
        # ALWAYS check if cancelled when updating progress
        if self.check_if_cancelled():
            logger.info(f"Job {self.current_job_id} was cancelled - stopping immediately")
            raise Exception("Job cancelled by user")
        
        try:
            self.db.supabase.rpc('update_job_progress', {
                'job_id': self.current_job_id,
                'current_progress': current,
                'total_progress': total
            }).execute()
            
            logger.debug(f"Job {self.current_job_id} progress: {current}/{total}")
        except Exception as e:
            if "cancelled by user" in str(e).lower():
                raise  # Re-raise cancellation
            logger.error(f"Failed to update job progress: {e}")
    
    def complete_job(self, success: bool = True, error_message: Optional[str] = None):
        """Mark the current job as completed"""
        if not self.current_job_id:
            return
        
        try:
            status = 'completed' if success else 'failed'
            self.db.supabase.table('processing_runs').update({
                'job_status': status,
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'error_message': error_message,
                'run_status': status  # Also update legacy run_status field
            }).eq('id', self.current_job_id).execute()
            
            self.log_job_message(
                'INFO' if success else 'ERROR',
                f"Job {status}: {error_message or 'Successfully completed'}",
                {'duration': time.time() - self.job_start_time if hasattr(self, 'job_start_time') else 0}
            )
            
            logger.info(f"Job {self.current_job_id} marked as {status}")
        except Exception as e:
            logger.error(f"Failed to complete job: {e}")
        finally:
            self.current_job_id = None
            # Mark worker as idle
            try:
                self.db.supabase.table('worker_status').update({
                    'status': 'idle',
                    'current_job_id': None
                }).eq('worker_id', self.worker_id).execute()
            except:
                pass
    
    def process_csv_upload_job(self, job: Dict[str, Any]):
        """Process a CSV upload job"""
        self.log_job_message('INFO', 'Starting CSV upload processing')
        
        try:
            params = job.get('job_params')
            if params is None:
                # Handle old jobs without job_params
                self.log_job_message('ERROR', 'Job has no job_params - this is an old job format')
                raise ValueError("Job missing job_params - cannot process")
            
            # If params is a string (JSON), parse it
            if isinstance(params, str):
                import json
                params = json.loads(params)
            
            url = params.get('url')
            filters = params.get('filters', {})
            limit = params.get('limit', 0)
            
            if not url:
                raise ValueError("No URL provided in job parameters")
            
            # Load loans data
            self.log_job_message('INFO', f'Loading loans from URL: {url}')
            loans = load_loans_data_from_url(url, limit=limit)
            
            if not loans:
                raise ValueError("No loans found to process")
            
            self.log_job_message('INFO', f'Loaded {len(loans)} loans')
            
            # Apply filters if provided
            filtered_loans = loans
            if filters:
                # Apply office filter
                office_filter = filters.get('office')
                if office_filter and office_filter not in ['All', 'All Offices']:
                    filtered_loans = [l for l in filtered_loans if l.get('office') == office_filter]
                
                # Apply make filter
                make_filter = filters.get('make')
                if make_filter and make_filter not in ['All', 'All Makes']:
                    filtered_loans = [l for l in filtered_loans if l.get('make') == make_filter]
                
                # Apply model filter
                model_filter = filters.get('model')
                if model_filter and model_filter not in ['All', 'All Models']:
                    filtered_loans = [l for l in filtered_loans if l.get('model') == model_filter]

                # Apply reporter filter (maps to contact name 'to')
                reporter_filter = filters.get('reporter')
                if reporter_filter and reporter_filter not in ['All', 'All Reporters']:
                    filtered_loans = [l for l in filtered_loans if str(l.get('to', '')).strip() == str(reporter_filter).strip()]

                # Apply WO # filter (comma-separated list)
                wo_numbers_raw = filters.get('wo_numbers')
                if wo_numbers_raw:
                    try:
                        wo_numbers = [str(x).strip() for x in str(wo_numbers_raw).split(',') if str(x).strip()]
                        if wo_numbers:
                            filtered_loans = [l for l in filtered_loans if str(l.get('work_order', '')).strip() in wo_numbers]
                    except Exception:
                        pass

                # Apply Activity ID filter (comma-separated list)
                activity_ids_raw = filters.get('activity_ids')
                if activity_ids_raw:
                    try:
                        activity_ids = [str(x).strip() for x in str(activity_ids_raw).split(',') if str(x).strip()]
                        if activity_ids:
                            filtered_loans = [l for l in filtered_loans if str(l.get('activity_id', '')).strip() in activity_ids]
                    except Exception:
                        pass

                # Apply positional skip filter
                skip_records = filters.get('skip_records')
                if isinstance(skip_records, int) and skip_records > 0 and skip_records < len(filtered_loans):
                    filtered_loans = filtered_loans[skip_records:]

                # Apply date range filter on Start Date if provided
                date_from = filters.get('date_from')
                date_to = filters.get('date_to')
                if date_from or date_to:
                    from datetime import datetime
                    def in_range(loan):
                        sd = loan.get('start_date')
                        # Parse strings to datetime when necessary
                        if isinstance(sd, str) and sd:
                            try:
                                sd = datetime.fromisoformat(sd)
                            except Exception:
                                return True  # if unparseable, don't exclude
                        if date_from:
                            try:
                                df = datetime.fromisoformat(str(date_from))
                                if sd and sd < df:
                                    return False
                            except Exception:
                                pass
                        if date_to:
                            try:
                                dt = datetime.fromisoformat(str(date_to))
                                if sd and sd > dt:
                                    return False
                            except Exception:
                                pass
                        return True
                    filtered_loans = [l for l in filtered_loans if in_range(l)]
                
                self.log_job_message('INFO', f'Filtered to {len(filtered_loans)} loans')
            
            # Apply overall limit AFTER filtering
            if isinstance(limit, int) and limit > 0:
                filtered_loans = filtered_loans[:limit]
                self.log_job_message('INFO', f'Applied limit: processing {len(filtered_loans)} loans')
            
            # Update job with correct total for progress tracking
            self.db.supabase.table('processing_runs').update({
                'progress_total': len(filtered_loans),  # Set the actual filtered count
                'total_records': len(filtered_loans)
            }).eq('id', self.current_job_id).execute()
            
            # Start a background thread to check for cancellation every second
            import threading
            import os
            import signal
            self.job_cancelled = False
            
            def check_cancellation_thread():
                while not self.job_cancelled and self.current_job_id:
                    if self.check_if_cancelled():
                        self.job_cancelled = True
                        logger.info(f"Cancellation detected for job {self.current_job_id} - flagged for stop")
                        break
                    time.sleep(1)  # Check every second
            
            cancel_thread = threading.Thread(target=check_cancellation_thread, daemon=True)
            cancel_thread.start()
            
            # Create progress callback that checks for cancellation
            def progress_callback(current, total):
                # Check if job was cancelled
                if self.job_cancelled or self.check_if_cancelled():
                    raise Exception("Job cancelled by user")
                
                # Use the filtered count for progress
                self.update_job_progress(current, len(filtered_loans))
                self.send_heartbeat()  # Send heartbeat on progress updates
            
            # Process the loans
            self.log_job_message('INFO', f'Starting loan processing for {len(filtered_loans)} filtered records')
            
            # We need to process without creating a new run since we already have one
            from src.ingest.ingest_database import process_loans_database_concurrent, load_person_outlets_mapping
            import asyncio
            
            # Load outlets mapping for media validation
            outlets_mapping = load_person_outlets_mapping()
            
            # Process loans and get stats with cancellation support
            try:
                stats = asyncio.run(process_loans_database_concurrent(
                    filtered_loans, self.db, self.current_job_id, outlets_mapping, progress_callback
                ))
            except Exception as e:
                if "cancelled by user" in str(e).lower():
                    # Job was cancelled during processing
                    raise
                else:
                    # Real error, re-raise
                    raise
            
            # Update job with final statistics - use actual skipped count
            self.db.supabase.table('processing_runs').update({
                'total_records': stats.get('processed', len(filtered_loans)),  # Use actual processed count
                'successful_finds': stats.get('successful', 0),
                'failed_attempts': stats.get('failed', 0),
                'skipped_count': stats.get('skipped', 0),  # Store actual skipped count
                'error_count': stats.get('errors', 0),  # Store error count separately
                'progress_current': stats.get('processed', len(filtered_loans))
            }).eq('id', self.current_job_id).execute()
            
            self.log_job_message('INFO', f'CSV upload processing completed: {stats}')
            self.complete_job(success=True)
                
        except Exception as e:
            error_msg = str(e)
            if "cancelled by user" in error_msg.lower():
                self.log_job_message('INFO', 'Job cancelled by user')
                # Job already marked as cancelled in DB by UI
                self.current_job_id = None
            else:
                error_msg = f"CSV upload job failed: {error_msg}"
                self.log_job_message('ERROR', error_msg, {'traceback': traceback.format_exc()})
                self.complete_job(success=False, error_message=error_msg)
    
    def process_sentiment_analysis_job(self, job: Dict[str, Any]):
        """Process a sentiment analysis job"""
        self.log_job_message('INFO', 'Starting sentiment analysis')
        
        try:
            params = job.get('job_params', {})
            run_id = params.get('run_id')
            
            if run_id:
                # Process specific run
                self.log_job_message('INFO', f'Processing sentiment for run {run_id}')
            else:
                # Process all pending
                self.log_job_message('INFO', 'Processing all pending sentiment analysis')
            
            # Create progress callback that checks for cancellation
            def progress_callback(current, total):
                if self.check_if_cancelled():
                    raise Exception("Job cancelled by user")
                self.update_job_progress(current, total)
                self.send_heartbeat()
            
            # Run sentiment analysis
            stats = run_sentiment_analysis(
                run_id=run_id,
                progress_callback=progress_callback
            )
            
            self.log_job_message('INFO', f'Sentiment analysis completed: {stats}')
            self.complete_job(success=True)
            
        except Exception as e:
            error_msg = str(e)
            if "cancelled by user" in error_msg.lower():
                self.log_job_message('INFO', 'Job cancelled by user')
                self.current_job_id = None
            else:
                error_msg = f"Sentiment analysis job failed: {error_msg}"
                self.log_job_message('ERROR', error_msg, {'traceback': traceback.format_exc()})
                self.complete_job(success=False, error_message=error_msg)
    
    def process_historical_reprocessing_job(self, job: Dict[str, Any]):
        """Process a historical reprocessing job"""
        self.log_job_message('INFO', 'Starting historical reprocessing')
        
        try:
            params = job.get('job_params', {})
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            
            # Import the reprocessing function
            from src.dashboard.historical_reprocessing import reprocess_historical_clips
            
            # Create progress callback that checks for cancellation
            def progress_callback(current, total):
                if self.check_if_cancelled():
                    raise Exception("Job cancelled by user")
                self.update_job_progress(current, total)
                self.send_heartbeat()
            
            # Run reprocessing
            self.log_job_message('INFO', f'Reprocessing clips from {start_date} to {end_date}')
            stats = reprocess_historical_clips(
                start_date=start_date,
                end_date=end_date,
                progress_callback=progress_callback
            )
            
            self.log_job_message('INFO', f'Historical reprocessing completed: {stats}')
            self.complete_job(success=True)
            
        except Exception as e:
            error_msg = str(e)
            if "cancelled by user" in error_msg.lower():
                self.log_job_message('INFO', 'Job cancelled by user')
                self.current_job_id = None
            else:
                error_msg = f"Historical reprocessing job failed: {error_msg}"
                self.log_job_message('ERROR', error_msg, {'traceback': traceback.format_exc()})
                self.complete_job(success=False, error_message=error_msg)
    
    def process_job(self, job: Dict[str, Any]):
        """Process a single job based on its type"""
        self.job_start_time = time.time()
        job_type = job.get('job_type')
        
        logger.info(f"Processing job type: {job_type}")
        
        # Check if job was already cancelled before starting
        if self.check_if_cancelled():
            logger.info(f"Job {self.current_job_id} was cancelled before processing started")
            self.current_job_id = None
            return
        
        try:
            if job_type == 'csv_upload':
                self.process_csv_upload_job(job)
            elif job_type == 'sentiment_analysis':
                self.process_sentiment_analysis_job(job)
            elif job_type == 'historical_reprocessing':
                self.process_historical_reprocessing_job(job)
            elif job_type == 'fms_export':
                # TODO: Implement FMS export job processing
                self.log_job_message('ERROR', 'FMS export job type not yet implemented')
                self.complete_job(success=False, error_message='Job type not implemented')
            else:
                error_msg = f"Unknown job type: {job_type}"
                self.log_job_message('ERROR', error_msg)
                self.complete_job(success=False, error_message=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error processing job: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log_job_message('ERROR', error_msg, {'traceback': traceback.format_exc()})
            self.complete_job(success=False, error_message=error_msg)
    
    def cleanup_stale_jobs(self):
        """Clean up stale jobs that have no heartbeat"""
        try:
            result = self.db.supabase.rpc('cleanup_stale_jobs').execute()
            if result.data and result.data > 0:
                logger.info(f"Cleaned up {result.data} stale jobs")
        except Exception as e:
            logger.error(f"Failed to cleanup stale jobs: {e}")
    
    def run(self):
        """Main worker loop"""
        logger.info(f"Worker {self.worker_id} starting...")
        
        # Register worker
        self.register_worker()
        
        self.running = True
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.running:
            try:
                # Send heartbeat
                self.send_heartbeat()
                
                # Clean up stale jobs periodically
                if time.time() % 300 < 1:  # Every 5 minutes
                    self.cleanup_stale_jobs()
                
                # Try to claim a job
                job = self.claim_job()
                
                if job:
                    consecutive_errors = 0  # Reset error counter on successful claim
                    logger.info(f"Processing job: {job.get('run_name')}")
                    self.process_job(job)
                else:
                    # No jobs available, wait before checking again
                    logger.debug("No jobs available, waiting...")
                    time.sleep(5)
                
            except KeyboardInterrupt:
                logger.info("Worker interrupted by user")
                self.running = False
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Worker error (attempt {consecutive_errors}/{max_consecutive_errors}): {e}", exc_info=True)
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"Too many consecutive errors, shutting down worker")
                    self.running = False
                else:
                    # Wait before retrying with exponential backoff
                    wait_time = min(60, 5 * (2 ** consecutive_errors))
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
        
        logger.info(f"Worker {self.worker_id} stopped")

def main():
    """Main entry point for the worker"""
    # Configure logging based on environment
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get worker ID from environment or generate one
    worker_id = os.environ.get('WORKER_ID')
    
    # Create and run worker
    worker = BackgroundWorker(worker_id=worker_id)
    
    try:
        worker.run()
    except Exception as e:
        logger.critical(f"Worker crashed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()