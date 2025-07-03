"""
Database utilities for Supabase integration.
Handles all database operations for the DriveShop clip tracking system.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from supabase import create_client, Client
from dataclasses import dataclass

# Import existing logger
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class ProcessingRun:
    """Data class for processing run information"""
    id: str
    run_name: str
    start_time: datetime
    end_time: Optional[datetime]
    total_records: int
    successful_finds: int
    failed_attempts: int
    run_status: str

@dataclass
class ClipData:
    """Data class for clip information"""
    id: Optional[str]
    wo_number: str
    processing_run_id: str
    office: Optional[str]
    make: Optional[str]
    model: Optional[str]
    contact: Optional[str]
    person_id: Optional[str]
    activity_id: Optional[str]
    clip_url: Optional[str]
    extracted_content: Optional[str]
    published_date: Optional[str]
    attribution_strength: Optional[str]
    byline_author: Optional[str]
    processed_date: datetime
    tier_used: Optional[str]
    status: str
    last_attempt_date: datetime
    attempt_count: int
    last_attempt_result: Optional[str]
    retry_after_date: Optional[datetime]
    relevance_score: Optional[int]
    overall_sentiment: Optional[str]
    brand_alignment: Optional[bool]
    summary: Optional[str]
    sentiment_analysis_date: Optional[datetime]

class DatabaseManager:
    """Manages all database operations for the DriveShop clip tracking system"""
    
    def __init__(self):
        """Initialize the database connection"""
        try:
            self.supabase_url = os.environ.get("SUPABASE_URL")
            self.supabase_key = os.environ.get("SUPABASE_ANON_KEY")
            
            if not self.supabase_url or not self.supabase_key:
                raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")
            
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("✅ Successfully connected to Supabase database")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Supabase: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test the database connection"""
        try:
            # Try a simple query to test connection
            result = self.supabase.table('processing_runs').select('id').limit(1).execute()
            logger.info("✅ Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")
            return False
    
    # ========== PROCESSING RUNS ==========
    
    def create_processing_run(self, run_name: str = None) -> str:
        """
        Create a new processing run and return the run ID
        
        Args:
            run_name: Optional custom name for the run
            
        Returns:
            The UUID of the created processing run
        """
        try:
            if not run_name:
                run_name = f"Auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            run_data = {
                "run_name": run_name,
                "start_time": datetime.now().isoformat(),
                "run_status": "running"
            }
            
            result = self.supabase.table('processing_runs').insert(run_data).execute()
            
            if result.data:
                run_id = result.data[0]['id']
                logger.info(f"✅ Created processing run: {run_name} (ID: {run_id})")
                return run_id
            else:
                raise Exception("No data returned from insert")
                
        except Exception as e:
            logger.error(f"❌ Failed to create processing run: {e}")
            raise
    
    def update_processing_run(self, run_id: str, **updates) -> bool:
        """Update a processing run with new data"""
        try:
            result = self.supabase.table('processing_runs').update(updates).eq('id', run_id).execute()
            
            if result.data:
                logger.info(f"✅ Updated processing run {run_id}")
                return True
            else:
                logger.warning(f"⚠️ No processing run found with ID {run_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update processing run {run_id}: {e}")
            return False
    
    def finish_processing_run(self, run_id: str, successful_finds: int, failed_attempts: int) -> bool:
        """Mark a processing run as completed"""
        try:
            updates = {
                "end_time": datetime.now().isoformat(),
                "successful_finds": successful_finds,
                "failed_attempts": failed_attempts,
                "total_records": successful_finds + failed_attempts,
                "run_status": "completed"
            }
            
            return self.update_processing_run(run_id, **updates)
            
        except Exception as e:
            logger.error(f"❌ Failed to finish processing run {run_id}: {e}")
            return False
    
    def get_recent_runs(self, limit: int = 10) -> List[ProcessingRun]:
        """Get recent processing runs"""
        try:
            result = self.supabase.table('processing_runs')\
                .select('*')\
                .order('start_time', desc=True)\
                .limit(limit)\
                .execute()
            
            runs = []
            for row in result.data:
                runs.append(ProcessingRun(
                    id=row['id'],
                    run_name=row['run_name'],
                    start_time=datetime.fromisoformat(row['start_time']),
                    end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
                    total_records=row['total_records'] or 0,
                    successful_finds=row['successful_finds'] or 0,
                    failed_attempts=row['failed_attempts'] or 0,
                    run_status=row['run_status']
                ))
            
            logger.info(f"✅ Retrieved {len(runs)} recent processing runs")
            return runs
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent runs: {e}")
            return []
    
    # ========== CLIP MANAGEMENT ==========
    
    def store_clip(self, clip_data: Dict[str, Any]) -> bool:
        """
        Store a found clip to the database
        
        Args:
            clip_data: Dictionary containing clip information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure required fields are present
            required_fields = ['wo_number', 'processing_run_id']
            for field in required_fields:
                if field not in clip_data:
                    raise ValueError(f"Required field '{field}' missing from clip_data")
            
            # Prepare data for insertion
            db_data = {
                "wo_number": str(clip_data['wo_number']),
                "processing_run_id": clip_data['processing_run_id'],
                "office": clip_data.get('office'),
                "make": clip_data.get('make'),
                "model": clip_data.get('model'),
                "contact": clip_data.get('contact'),
                "person_id": clip_data.get('person_id'),
                "activity_id": clip_data.get('activity_id'),
                "clip_url": clip_data.get('clip_url'),
                "extracted_content": clip_data.get('extracted_content'),
                "published_date": clip_data.get('published_date'),
                "attribution_strength": clip_data.get('attribution_strength'),
                "byline_author": clip_data.get('byline_author'),
                "tier_used": clip_data.get('tier_used'),
                "status": clip_data.get('status', 'pending_review'),
                "last_attempt_result": 'success'
            }
            
            result = self.supabase.table('clips').insert(db_data).execute()
            
            if result.data:
                clip_id = result.data[0]['id']
                logger.info(f"✅ Stored clip for WO# {clip_data['wo_number']} (ID: {clip_id})")
                
                # Update WO tracking
                self.mark_wo_success(clip_data['wo_number'], clip_data.get('clip_url'))
                
                return True
            else:
                raise Exception("No data returned from insert")
                
        except Exception as e:
            logger.error(f"❌ Failed to store clip: {e}")
            return False
    
    def get_pending_clips(self, run_id: str = None) -> List[Dict[str, Any]]:
        """Get clips that are pending review"""
        try:
            query = self.supabase.table('clips').select('*').eq('status', 'pending_review')
            
            if run_id:
                query = query.eq('processing_run_id', run_id)
            
            result = query.order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} pending clips")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get pending clips: {e}")
            return []
    
    def get_clips_needing_sentiment(self, run_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Get approved clips that need sentiment analysis"""
        try:
            query = self.supabase.table('clips')\
                .select('*')\
                .eq('status', 'approved')\
                .is_('sentiment_analysis_date', None)
            
            if run_ids:
                query = query.in_('processing_run_id', run_ids)
            
            result = query.execute()
            
            logger.info(f"✅ Found {len(result.data)} clips needing sentiment analysis")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get clips needing sentiment: {e}")
            return []
    
    def update_clip_sentiment(self, clip_id: str, sentiment_data: Dict[str, Any]) -> bool:
        """Update a clip with sentiment analysis results"""
        try:
            updates = {
                "relevance_score": sentiment_data.get('relevance_score'),
                "overall_sentiment": sentiment_data.get('overall_sentiment'),
                "brand_alignment": sentiment_data.get('brand_alignment'),
                "summary": sentiment_data.get('summary'),
                "sentiment_analysis_date": datetime.now().isoformat()
            }
            
            result = self.supabase.table('clips').update(updates).eq('id', clip_id).execute()
            
            if result.data:
                logger.info(f"✅ Updated sentiment for clip {clip_id}")
                return True
            else:
                logger.warning(f"⚠️ No clip found with ID {clip_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update clip sentiment: {e}")
            return False
    
    def approve_clip(self, clip_id: str) -> bool:
        """Mark a clip as approved"""
        return self._update_clip_status(clip_id, 'approved')
    
    def reject_clip(self, clip_id: str) -> bool:
        """Mark a clip as rejected"""
        return self._update_clip_status(clip_id, 'rejected')
    
    def _update_clip_status(self, clip_id: str, status: str) -> bool:
        """Helper method to update clip status"""
        try:
            result = self.supabase.table('clips').update({"status": status}).eq('id', clip_id).execute()
            
            if result.data:
                logger.info(f"✅ Updated clip {clip_id} status to {status}")
                return True
            else:
                logger.warning(f"⚠️ No clip found with ID {clip_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update clip status: {e}")
            return False
    
    # ========== SMART RETRY LOGIC ==========
    
    def should_retry_wo(self, wo_number: str) -> bool:
        """
        Check if a WO# should be retried based on smart retry logic
        
        Args:
            wo_number: The work order number to check
            
        Returns:
            True if the WO should be processed, False if it should be skipped
        """
        try:
            # Check WO tracking table
            result = self.supabase.table('wo_tracking').select('*').eq('wo_number', wo_number).execute()
            
            if not result.data:
                # Never tried before, should retry
                logger.info(f"🆕 WO# {wo_number} never attempted - will process")
                return True
            
            wo_record = result.data[0]
            
            # If we already found a clip, don't retry
            if wo_record['status'] == 'found':
                logger.info(f"✅ WO# {wo_number} already has clip - skipping")
                return False
            
            # Check retry timing
            if wo_record['retry_after_date']:
                retry_after = datetime.fromisoformat(wo_record['retry_after_date'])
                if datetime.now() < retry_after:
                    logger.info(f"⏰ WO# {wo_number} in retry cooldown until {retry_after} - skipping")
                    return False
            
            logger.info(f"🔄 WO# {wo_number} ready for retry")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking retry status for WO# {wo_number}: {e}")
            # On error, allow retry to be safe
            return True
    
    def mark_wo_attempt(self, wo_number: str, result: str, details: str = None) -> bool:
        """
        Record an attempt for a WO# with smart retry logic
        
        Args:
            wo_number: The work order number
            result: 'success', 'no_content', 'crawl_failed', 'generic_content', etc.
            details: Optional additional details
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Define retry intervals (in days)
            RETRY_INTERVALS = {
                'no_content': 7,        # 7 days - content might be published weekly
                'generic_content': 3,   # 3 days - they might publish specific content soon  
                'crawl_failed': 1,      # 1 day - technical issues usually resolve quickly
                'blocked_403': 2,       # 2 days - anti-bot measures might reset
                'timeout': 1,           # 1 day - site performance issues
                'success': None         # Never retry - we found what we needed!
            }
            
            # Calculate retry date
            retry_after_date = None
            if result in RETRY_INTERVALS and RETRY_INTERVALS[result] is not None:
                retry_after_date = (datetime.now() + timedelta(days=RETRY_INTERVALS[result])).isoformat()
            
            # Prepare tracking data
            tracking_data = {
                "wo_number": str(wo_number),
                "status": "found" if result == "success" else "searching",
                "last_attempt_date": datetime.now().isoformat(),
                "retry_after_date": retry_after_date
            }
            
            # Use upsert (insert or update)
            result_db = self.supabase.table('wo_tracking').upsert(tracking_data).execute()
            
            if result_db.data:
                logger.info(f"✅ Recorded attempt for WO# {wo_number}: {result}")
                return True
            else:
                raise Exception("No data returned from upsert")
                
        except Exception as e:
            logger.error(f"❌ Failed to record attempt for WO# {wo_number}: {e}")
            return False
    
    def mark_wo_success(self, wo_number: str, clip_url: str) -> bool:
        """Mark a WO# as successfully found"""
        try:
            tracking_data = {
                "wo_number": str(wo_number),
                "status": "found",
                "last_attempt_date": datetime.now().isoformat(),
                "found_clip_url": clip_url,
                "retry_after_date": None  # Never retry successful finds
            }
            
            result = self.supabase.table('wo_tracking').upsert(tracking_data).execute()
            
            if result.data:
                logger.info(f"✅ Marked WO# {wo_number} as successfully found")
                return True
            else:
                raise Exception("No data returned from upsert")
                
        except Exception as e:
            logger.error(f"❌ Failed to mark WO# {wo_number} as success: {e}")
            return False
    
    # ========== ANALYTICS & REPORTING ==========
    
    def get_run_statistics(self, run_id: str) -> Dict[str, Any]:
        """Get statistics for a specific processing run"""
        try:
            # Get run info
            run_result = self.supabase.table('processing_runs').select('*').eq('id', run_id).execute()
            
            if not run_result.data:
                return {}
            
            run_info = run_result.data[0]
            
            # Get clips for this run
            clips_result = self.supabase.table('clips').select('*').eq('processing_run_id', run_id).execute()
            clips = clips_result.data
            
            # Calculate statistics
            total_clips = len(clips)
            approved_clips = len([c for c in clips if c['status'] == 'approved'])
            rejected_clips = len([c for c in clips if c['status'] == 'rejected'])
            pending_clips = len([c for c in clips if c['status'] == 'pending_review'])
            
            # Calculate average relevance (only for clips with sentiment analysis)
            clips_with_scores = [c for c in clips if c.get('relevance_score') is not None]
            avg_relevance = sum(c['relevance_score'] for c in clips_with_scores) / len(clips_with_scores) if clips_with_scores else 0
            
            statistics = {
                "run_name": run_info['run_name'],
                "start_time": run_info['start_time'],
                "end_time": run_info['end_time'],
                "total_records": run_info['total_records'] or 0,
                "successful_finds": run_info['successful_finds'] or 0,
                "failed_attempts": run_info['failed_attempts'] or 0,
                "success_rate": (run_info['successful_finds'] / run_info['total_records'] * 100) if run_info['total_records'] else 0,
                "total_clips": total_clips,
                "approved_clips": approved_clips,
                "rejected_clips": rejected_clips,
                "pending_clips": pending_clips,
                "avg_relevance": avg_relevance,
                "clips_with_sentiment": len(clips_with_scores)
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"❌ Failed to get run statistics: {e}")
            return {}

# Global database instance
_db_instance = None

def get_database() -> DatabaseManager:
    """Get global database instance (singleton pattern)"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance 