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
    sentiment_completed: Optional[bool]

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
                "trim": clip_data.get('trim'),  # ADD TRIM FIELD
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
                "workflow_stage": clip_data.get('workflow_stage', 'found'),
                "last_attempt_result": 'success',
                "relevance_score": clip_data.get('relevance_score'),
                "overall_sentiment": clip_data.get('overall_sentiment'),
                "brand_alignment": clip_data.get('brand_alignment'),
                "summary": clip_data.get('summary'),
                "sentiment_completed": clip_data.get('sentiment_completed', False)
            }
            
            # Check if clip already exists for this WO#
            existing = self.supabase.table('clips').select('id').eq('wo_number', clip_data['wo_number']).execute()
            
            if existing.data:
                # Update existing clip
                result = self.supabase.table('clips').update(db_data).eq('wo_number', clip_data['wo_number']).execute()
                if result.data:
                    clip_id = result.data[0]['id']
                    logger.info(f"✅ Updated existing clip for WO# {clip_data['wo_number']} (ID: {clip_id})")
                    # Update WO tracking
                    self.mark_wo_success(clip_data['wo_number'], clip_data.get('clip_url'))
                    return True
                else:
                    raise Exception("No data returned from update")
            else:
                # Insert new clip
                result = self.supabase.table('clips').insert(db_data).execute()
                if result.data:
                    clip_id = result.data[0]['id']
                    logger.info(f"✅ Stored new clip for WO# {clip_data['wo_number']} (ID: {clip_id})")
                    # Update WO tracking
                    self.mark_wo_success(clip_data['wo_number'], clip_data.get('clip_url'))
                    return True
                else:
                    raise Exception("No data returned from insert")
                
        except Exception as e:
            logger.error(f"❌ Failed to store clip: {e}")
            return False
    
    def store_failed_attempt(self, loan_data: Dict[str, Any], reason: str = "no_content_found") -> bool:
        """
        Store a failed processing attempt (no content found or processing failed)
        
        Args:
            loan_data: Dictionary containing loan information
            reason: Reason for failure ('no_content_found' or 'processing_failed')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure required fields are present
            required_fields = ['wo_number', 'processing_run_id']
            for field in required_fields:
                if field not in loan_data:
                    raise ValueError(f"Required field '{field}' missing from loan_data")
            
            # Prepare data for insertion
            db_data = {
                "wo_number": str(loan_data['wo_number']),
                "processing_run_id": loan_data['processing_run_id'],
                "office": loan_data.get('office'),
                "make": loan_data.get('make'),
                "model": loan_data.get('model'),
                "contact": loan_data.get('contact'),
                "person_id": loan_data.get('person_id'),
                "activity_id": loan_data.get('activity_id'),
                "clip_url": None,  # No clip found
                "extracted_content": None,  # No content found
                "published_date": None,
                "attribution_strength": None,
                "byline_author": None,
                "tier_used": loan_data.get('tier_used', 'Unknown'),
                "status": reason,  # 'no_content_found' or 'processing_failed'
                "workflow_stage": 'found',  # Default workflow stage
                # NEW: Store original source URLs for View link transparency
                "original_urls": loan_data.get('original_urls', ''),
                "urls_attempted": loan_data.get('urls_attempted', 0),
                "failure_reason": loan_data.get('failure_reason', reason)
            }
            
            # Check if clip already exists for this WO#
            existing = self.supabase.table('clips').select('id, attempt_count').eq('wo_number', loan_data['wo_number']).execute()
            
            if existing.data:
                # Update existing failed attempt and increment attempt count
                current_attempts = existing.data[0].get('attempt_count', 0) or 0
                db_data['attempt_count'] = current_attempts + 1
                
                result = self.supabase.table('clips').update(db_data).eq('wo_number', loan_data['wo_number']).execute()
                if result.data:
                    clip_id = result.data[0]['id']
                    logger.info(f"✅ Updated failed attempt for WO# {loan_data['wo_number']} (ID: {clip_id}, reason: {reason}, attempts: {db_data['attempt_count']})")
                    # Update WO tracking
                    self.mark_wo_attempt(loan_data['wo_number'], reason)
                    return True
                else:
                    raise Exception("No data returned from update")
            else:
                # Insert new failed attempt
                db_data['attempt_count'] = 1
                result = self.supabase.table('clips').insert(db_data).execute()
                if result.data:
                    clip_id = result.data[0]['id']
                    logger.info(f"✅ Stored failed attempt for WO# {loan_data['wo_number']} (ID: {clip_id}, reason: {reason})")
                    # Update WO tracking
                    self.mark_wo_attempt(loan_data['wo_number'], reason)
                    return True
                else:
                    raise Exception("No data returned from insert")
                
        except Exception as e:
            logger.error(f"❌ Failed to store failed attempt: {e}")
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
    
    def get_approved_clips(self, run_id: str = None) -> List[Dict[str, Any]]:
        """Get clips that have been approved"""
        try:
            query = self.supabase.table('clips').select('*').eq('status', 'approved')
            
            if run_id:
                query = query.eq('processing_run_id', run_id)
            
            result = query.order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} approved clips")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get approved clips: {e}")
            return []
    
    def get_approved_queue_clips(self, run_id: str = None) -> List[Dict[str, Any]]:
        """Get all approved clips in the queue (includes clips with sentiment analysis)"""
        try:
            # Include 'sentiment_analyzed' clips so they stay in the queue until exported
            query = self.supabase.table('clips')\
                .select('*')\
                .eq('status', 'approved')\
                .in_('workflow_stage', ['found', 'sentiment_analyzed'])
            
            if run_id:
                query = query.eq('processing_run_id', run_id)
            
            result = query.order('processed_date', desc=True).limit(1000).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} approved queue clips")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get approved queue clips: {e}")
            return []
    
    def get_ready_for_export_clips(self, run_id: str = None) -> List[Dict[str, Any]]:
        """Get clips that are ready for FMS export (approved + sentiment analyzed)"""
        try:
            query = self.supabase.table('clips')\
                .select('*')\
                .eq('status', 'approved')\
                .eq('workflow_stage', 'sentiment_analyzed')
            
            if run_id:
                query = query.eq('processing_run_id', run_id)
            
            result = query.order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} ready for export clips")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get ready for export clips: {e}")
            return []
    
    def get_exported_clips(self, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """Get clips that have been exported to FMS"""
        try:
            query = self.supabase.table('clips')\
                .select('*')\
                .eq('status', 'approved')\
                .eq('workflow_stage', 'exported')
            
            if start_date:
                query = query.gte('processed_date', start_date)
            if end_date:
                query = query.lte('processed_date', end_date)
            
            result = query.order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} exported clips")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get exported clips: {e}")
            return []
    
    def update_clip_workflow_stage(self, clip_id: str, workflow_stage: str) -> bool:
        """Update a clip's workflow stage"""
        try:
            result = self.supabase.table('clips').update({
                "workflow_stage": workflow_stage
            }).eq('id', clip_id).execute()
            
            if result.data:
                logger.info(f"✅ Updated clip {clip_id} workflow stage to {workflow_stage}")
                return True
            else:
                logger.warning(f"⚠️ No clip found with ID {clip_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update clip workflow stage: {e}")
            return False
    
    def bulk_update_workflow_stage(self, clip_ids: List[str], workflow_stage: str) -> int:
        """Update multiple clips' workflow stage"""
        try:
            result = self.supabase.table('clips').update({
                "workflow_stage": workflow_stage
            }).in_('id', clip_ids).execute()
            
            updated_count = len(result.data) if result.data else 0
            logger.info(f"✅ Updated {updated_count} clips to workflow stage {workflow_stage}")
            return updated_count
            
        except Exception as e:
            logger.error(f"❌ Failed to bulk update workflow stage: {e}")
            return 0
    
    def get_rejected_clips(self, run_id: str = None) -> List[Dict[str, Any]]:
        """Get clips that have been rejected"""
        try:
            # Select only required fields for performance
            fields = 'wo_number,office,make,model,contact,media_outlet,status,processed_date,clip_url,processing_run_id'
            query = self.supabase.table('clips').select(fields).eq('status', 'rejected')
            
            if run_id:
                query = query.eq('processing_run_id', run_id)
            
            result = query.order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} rejected clips")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get rejected clips: {e}")
            return []
    
    def get_failed_processing_attempts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get WO numbers that failed to find any content (for Rejected/Issues tab)"""
        try:
            query = self.supabase.table('wo_tracking')\
                .select('*')\
                .eq('status', 'searching')\
                .order('last_attempt_date', desc=True)\
                .limit(limit)
            
            result = query.execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} failed processing attempts")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get failed processing attempts: {e}")
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
            # Check if this is enhanced sentiment data (v2)
            is_enhanced = 'sentiment_classification' in sentiment_data
            
            # Handle PostgreSQL array fields - convert Python lists to PostgreSQL array format
            pros_list = sentiment_data.get('pros', [])
            cons_list = sentiment_data.get('cons', [])
            key_mentions_list = sentiment_data.get('key_mentions', [])
            influential_statements = sentiment_data.get('influential_statements', [])
            messaging_opportunities = sentiment_data.get('messaging_opportunities', [])
            risks_to_address = sentiment_data.get('risks_to_address', [])
            
            # Handle competitive intelligence arrays
            competitive_intel = sentiment_data.get('competitive_intelligence', {})
            if isinstance(competitive_intel, dict):
                advantages = competitive_intel.get('advantages_highlighted', [])
                vulnerabilities = competitive_intel.get('vulnerabilities_exposed', [])
            else:
                advantages = []
                vulnerabilities = []
            
            updates = {
                # Core sentiment fields
                "relevance_score": sentiment_data.get('relevance_score'),
                "overall_sentiment": sentiment_data.get('overall_sentiment'),
                "brand_alignment": sentiment_data.get('brand_alignment'),
                "summary": sentiment_data.get('summary'),
                "sentiment_analysis_date": datetime.now().isoformat(),
                "sentiment_completed": True,
                "workflow_stage": "sentiment_analyzed",
                "overall_score": sentiment_data.get('overall_score'),
                "recommendation": sentiment_data.get('recommendation'),
                
                # Strategic intelligence fields
                "marketing_impact_score": sentiment_data.get('marketing_impact_score'),
                "executive_summary": sentiment_data.get('executive_summary'),
                "brand_narrative": sentiment_data.get('brand_narrative'),
                "strategic_signal": sentiment_data.get('strategic_signal'),
                "purchase_intent_signals": sentiment_data.get('purchase_intent_signals'),
                
                # JSONB fields
                "creator_analysis": json.dumps(sentiment_data.get('creator_analysis', {})) if sentiment_data.get('creator_analysis') else None,
                "publication_analysis": json.dumps(sentiment_data.get('publication_analysis', {})) if sentiment_data.get('publication_analysis') else None,
                "competitive_intelligence": json.dumps(sentiment_data.get('competitive_intelligence', {})) if sentiment_data.get('competitive_intelligence') else None,
                "aspect_insights": json.dumps(sentiment_data.get('aspect_insights', {})) if sentiment_data.get('aspect_insights') else None,
                "action_items": json.dumps(sentiment_data.get('action_items', {})) if sentiment_data.get('action_items') else None,
                
                # Legacy aspects field for backward compatibility
                "aspects": json.dumps(sentiment_data.get('aspects', {})) if sentiment_data.get('aspects') else None,
                
                # Array fields
                "pros": pros_list if isinstance(pros_list, list) else [],
                "cons": cons_list if isinstance(cons_list, list) else [],
                "key_mentions": key_mentions_list if isinstance(key_mentions_list, list) else [],
                "influential_statements": influential_statements if isinstance(influential_statements, list) else [],
                "messaging_opportunities": messaging_opportunities if isinstance(messaging_opportunities, list) else [],
                "risks_to_address": risks_to_address if isinstance(risks_to_address, list) else []
            }
            
            # Add enhanced sentiment data if this is v2
            if is_enhanced:
                updates['sentiment_data_enhanced'] = json.dumps(sentiment_data)
                updates['sentiment_version'] = 'v2'
            else:
                updates['sentiment_version'] = 'v1'
            
            # Log the update for debugging
            logger.info(f"Updating clip {clip_id} with {'enhanced' if is_enhanced else 'original'} sentiment data: marketing_impact={updates.get('marketing_impact_score')}")
            
            result = self.supabase.table('clips').update(updates).eq('id', clip_id).execute()
            
            if result.data:
                logger.info(f"✅ Updated strategic sentiment for clip {clip_id} - workflow_stage is now 'sentiment_analyzed'")
                return True
            else:
                logger.warning(f"⚠️ No clip found with ID {clip_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update clip sentiment for {clip_id}: {e}")
            logger.error(f"Sentiment data that failed: {sentiment_data}")
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
    
    def update_clip_media_outlet(self, wo_number: str, media_outlet: str, media_outlet_id: str = None, impressions: int = None) -> bool:
        """Update the media outlet for a clip by WO number"""
        try:
            # Build update data
            update_data = {
                "media_outlet": media_outlet
            }
            
            # Add optional fields if provided
            if media_outlet_id is not None:
                update_data["media_outlet_id"] = media_outlet_id
            if impressions is not None:
                update_data["impressions"] = impressions
            
            # Update the clip
            result = self.supabase.table('clips').update(update_data).eq('wo_number', wo_number).execute()
            
            if result.data:
                logger.info(f"✅ Updated media outlet for WO# {wo_number} to: {media_outlet} (ID: {media_outlet_id}, Impressions: {impressions})")
                return True
            else:
                logger.warning(f"⚠️ No clip found with WO# {wo_number}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update media outlet for WO# {wo_number}: {e}")
            # If the media_outlet column doesn't exist, show helpful error
            if "column" in str(e).lower() and "media_outlet" in str(e).lower():
                logger.error("💡 SOLUTION: Run the add_media_outlet_column.sql script in your Supabase SQL Editor first!")
            return False
    
    def update_clip_byline_author(self, wo_number: str, byline_author: str) -> bool:
        """Update the byline author for a clip by WO number"""
        try:
            # Update the byline_author field
            result = self.supabase.table('clips').update({
                "byline_author": byline_author
            }).eq('wo_number', wo_number).execute()
            
            if result.data:
                logger.info(f"✅ Updated byline author for WO# {wo_number} to: {byline_author}")
                return True
            else:
                logger.warning(f"⚠️ No clip found with WO# {wo_number}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update byline author for WO# {wo_number}: {e}")
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
            # First check if we have a finalized clip (approved, pending_review, or rejected by user)
            clips_result = self.supabase.table('clips').select('id, status').eq('wo_number', wo_number).execute()
            if clips_result.data:
                clip_status = clips_result.data[0].get('status', '')
                if clip_status in ['approved', 'pending_review', 'rejected']:
                    logger.info(f"✅ WO# {wo_number} already has {clip_status} clip - skipping")
                    return False
                # If it's a failed attempt (no_content_found/processing_failed), continue to check retry logic
            
            # Check WO tracking table for retry logic
            result = self.supabase.table('wo_tracking').select('*').eq('wo_number', wo_number).execute()
            
            if not result.data:
                # Never tried before, should retry
                logger.info(f"🆕 WO# {wo_number} never attempted - will process")
                return True
            
            wo_record = result.data[0]
            
            # If we already found a clip (successful), don't retry
            if wo_record['status'] == 'found':
                logger.info(f"✅ WO# {wo_number} already found clip - skipping")
                return False
            
            # Check retry timing
            if wo_record['retry_after_date']:
                retry_after = datetime.fromisoformat(wo_record['retry_after_date'])
                # Ensure we're comparing timezone-aware datetimes
                current_time = datetime.now()
                if retry_after.tzinfo is not None:
                    # retry_after is timezone-aware, make current_time aware too
                    from datetime import timezone
                    current_time = datetime.now(timezone.utc)
                elif current_time.tzinfo is not None:
                    # current_time is timezone-aware, make retry_after naive
                    retry_after = retry_after.replace(tzinfo=None)
                
                if current_time < retry_after:
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
                'no_content': 4,        # 4 days - content might be published within a few days
                'no_content_found': 4,  # 4 days - same as no_content
                'generic_content': 3,   # 3 days - they might publish specific content soon  
                'crawl_failed': 1,      # 1 day - technical issues usually resolve quickly
                'blocked_403': 2,       # 2 days - anti-bot measures might reset
                'timeout': 1,           # 1 day - site performance issues
                'store_failed': 1,      # 1 day - database issues
                'success': None         # Never retry - we found what we needed!
            }
            
            # Calculate retry date
            retry_after_date = None
            if result in RETRY_INTERVALS and RETRY_INTERVALS[result] is not None:
                retry_after_date = (datetime.now() + timedelta(days=RETRY_INTERVALS[result])).isoformat()
            
            # Get current attempt count to increment it
            existing = self.supabase.table('wo_tracking').select('attempt_count').eq('wo_number', str(wo_number)).execute()
            current_count = existing.data[0]['attempt_count'] if existing.data and len(existing.data) > 0 else 0
            
            # Prepare tracking data
            tracking_data = {
                "wo_number": str(wo_number),
                "status": "found" if result == "success" else "searching",
                "last_attempt_date": datetime.now().isoformat(),
                "attempt_count": current_count + 1,
                # "last_attempt_result": result,  # COMMENTED OUT: Column doesn't exist yet
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
    
    def record_skip_event(self, wo_number: str, run_id: str, skip_reason: str) -> bool:
        """
        Record when a clip is skipped during processing
        
        Args:
            wo_number: The work order number that was skipped
            run_id: The current processing run ID
            skip_reason: Reason for skipping (e.g., 'retry_cooldown', 'already_approved')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update the existing clip record with skip information
            result = self.supabase.table('clips').update({
                'last_skip_run_id': run_id,
                'skip_reason': skip_reason
            }).eq('wo_number', wo_number).execute()
            
            if result.data:
                logger.info(f"📝 Recorded skip event for WO# {wo_number}: {skip_reason}")
                return True
            else:
                logger.warning(f"⚠️ No clip found to update skip status for WO# {wo_number}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to record skip event for WO# {wo_number}: {e}")
            return False
    
    def mark_wo_success(self, wo_number: str, clip_url: str) -> bool:
        """Mark a WO# as successfully found"""
        try:
            # Get current attempt count to increment it
            existing = self.supabase.table('wo_tracking').select('attempt_count').eq('wo_number', str(wo_number)).execute()
            current_count = existing.data[0]['attempt_count'] if existing.data and len(existing.data) > 0 else 0
            
            tracking_data = {
                "wo_number": str(wo_number),
                "status": "found",
                "last_attempt_date": datetime.now().isoformat(),
                "attempt_count": current_count + 1,
                # "last_attempt_result": "success",  # COMMENTED OUT: Column doesn't exist yet
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

    def get_clips_by_status_and_stage(self, status: str, workflow_stage: str = None, run_id: str = None) -> List[Dict[str, Any]]:
        """Get clips by status and optionally by workflow stage"""
        try:
            query = self.supabase.table('clips').select('*').eq('status', status)
            
            if workflow_stage:
                query = query.eq('workflow_stage', workflow_stage)
            
            if run_id:
                query = query.eq('processing_run_id', run_id)
            
            result = query.order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} clips with status='{status}', workflow_stage='{workflow_stage}'")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get clips by status and stage: {e}")
            return []

    def get_no_content_clips(self, run_id: str = None) -> List[Dict[str, Any]]:
        """Get clips where no content was found"""
        try:
            query = self.supabase.table('clips').select('*').eq('status', 'no_content_found')
            
            if run_id:
                query = query.eq('processing_run_id', run_id)
            
            result = query.order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} no content clips")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get no content clips: {e}")
            return []

    def get_processing_failed_clips(self, run_id: str = None) -> List[Dict[str, Any]]:
        """Get clips where processing failed"""
        try:
            query = self.supabase.table('clips').select('*').eq('status', 'processing_failed')
            
            if run_id:
                query = query.eq('processing_run_id', run_id)
            
            result = query.order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} processing failed clips")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get processing failed clips: {e}")
            return []

    def get_approved_clips_by_stage(self, workflow_stage: str = None, run_id: str = None) -> List[Dict[str, Any]]:
        """Get approved clips by workflow stage"""
        try:
            query = self.supabase.table('clips').select('*').eq('status', 'approved')
            
            if workflow_stage:
                query = query.eq('workflow_stage', workflow_stage)
            
            if run_id:
                query = query.eq('processing_run_id', run_id)
            
            result = query.order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} approved clips with workflow_stage='{workflow_stage}'")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get approved clips by stage: {e}")
            return []

    # ========== ENHANCED FILTERING METHODS ==========
    
    def get_latest_processing_run_id(self) -> Optional[str]:
        """Get the ID of the most recent processing run"""
        try:
            result = self.supabase.table('processing_runs')\
                .select('id')\
                .order('start_time', desc=True)\
                .limit(1)\
                .execute()
            
            if result.data:
                latest_run_id = result.data[0]['id']
                logger.info(f"✅ Retrieved latest processing run ID: {latest_run_id}")
                return latest_run_id
            else:
                logger.warning("⚠️ No processing runs found")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get latest processing run ID: {e}")
            return None
    
    def get_clips_ready_for_export(self) -> List[Dict[str, Any]]:
        """Get clips ready for FMS export (workflow_stage='found')"""
        try:
            result = self.supabase.table('clips').select('*').eq('status', 'approved').eq('workflow_stage', 'found').order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} clips ready for export")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get clips ready for export: {e}")
            return []
    
    def get_clips_needing_sentiment_analysis(self) -> List[Dict[str, Any]]:
        """Get clips that need sentiment analysis (workflow_stage='exported')"""
        try:
            result = self.supabase.table('clips').select('*').eq('status', 'approved').eq('workflow_stage', 'exported').order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} clips needing sentiment analysis")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get clips needing sentiment: {e}")
            return []
    
    def get_clips_complete_recent(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get recently completed clips (workflow_stage='exported', last X days)"""
        try:
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            result = self.supabase.table('clips').select('*').eq('status', 'approved').eq('workflow_stage', 'exported').gte('processed_date', cutoff_date).order('processed_date', desc=True).execute()
            
            logger.info(f"✅ Retrieved {len(result.data)} recently completed clips (last {days} days)")
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get recently completed clips: {e}")
            return []
    
    def update_clips_to_exported_basic(self, wo_numbers: List[str]) -> bool:
        """Update clips to exported workflow stage after FMS export"""
        try:
            for wo_number in wo_numbers:
                self.supabase.table('clips').update({
                    'workflow_stage': 'exported'
                }).eq('wo_number', wo_number).execute()
            
            logger.info(f"✅ Updated {len(wo_numbers)} clips to workflow_stage='exported'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update clips to exported_basic: {e}")
            return False
    
    def update_clips_to_complete(self, clip_ids: List[str]) -> bool:
        """Update clips to complete workflow stage after FMS export"""
        try:
            logger.info(f"🔄 Attempting to update {len(clip_ids)} clips to complete status")
            logger.info(f"📋 Clip IDs to update: {clip_ids}")
            
            updated_count = 0
            for clip_id in clip_ids:
                try:
                    result = self.supabase.table('clips').update({
                        'workflow_stage': 'exported'
                    }).eq('id', clip_id).execute()
                    
                    if result.data:
                        updated_count += 1
                        logger.info(f"✅ Updated clip {clip_id} to complete")
                    else:
                        logger.warning(f"⚠️ No data returned for clip {clip_id}")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to update clip {clip_id}: {e}")
            
            logger.info(f"✅ Successfully updated {updated_count}/{len(clip_ids)} clips to workflow_stage='exported'")
            return updated_count > 0
            
        except Exception as e:
            logger.error(f"❌ Failed to update clips to complete: {e}")
            import traceback
            logger.error(f"Full error: {traceback.format_exc()}")
            return False
    
    def delete_clips_older_than_days(self, days: int, export_before_delete: bool = True) -> Dict[str, Any]:
        """Delete clips older than X days with optional export"""
        try:
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Get clips to be deleted for export
            if export_before_delete:
                clips_to_delete = self.supabase.table('clips').select('*').lt('processed_date', cutoff_date).execute()
                exported_clips = clips_to_delete.data
            else:
                exported_clips = []
            
            # Delete old clips
            delete_result = self.supabase.table('clips').delete().lt('processed_date', cutoff_date).execute()
            deleted_count = len(delete_result.data) if delete_result.data else 0
            
            logger.info(f"✅ Deleted {deleted_count} clips older than {days} days")
            
            return {
                'deleted_count': deleted_count,
                'exported_clips': exported_clips if export_before_delete else [],
                'cutoff_date': cutoff_date
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to delete old clips: {e}")
            return {'deleted_count': 0, 'exported_clips': [], 'error': str(e)}

    def get_all_failed_clips(self, run_id: str = None, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """
        Get all failed clips (no_content_found + processing_failed) with optional filtering
        
        Args:
            run_id: Filter by specific processing run ID
            start_date: Filter by start date (YYYY-MM-DD format)
            end_date: Filter by end date (YYYY-MM-DD format)
            
        Returns:
            List of failed clip records
        """
        try:
            # Select only required fields for performance
            fields = 'wo_number,office,make,model,contact,media_outlet,status,processed_date,original_urls,urls_attempted,failure_reason,tier_used,attempt_count,processing_run_id'
            # Get both types of failed clips
            query = self.supabase.table('clips').select(fields).in_('status', ['no_content_found', 'processing_failed'])
            
            # Apply filters
            if run_id:
                query = query.eq('processing_run_id', run_id)
            
            if start_date:
                query = query.gte('processed_date', start_date)
            
            if end_date:
                # Add one day to include the end date
                from datetime import datetime, timedelta
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                end_date_inclusive = (end_date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
                query = query.lt('processed_date', end_date_inclusive)
            
            result = query.order('processed_date', desc=True).execute()
            
            filter_desc = []
            if run_id:
                filter_desc.append(f"run_id={run_id}")
            if start_date:
                filter_desc.append(f"start_date={start_date}")
            if end_date:
                filter_desc.append(f"end_date={end_date}")
            
            filter_str = f" with filters: {', '.join(filter_desc)}" if filter_desc else ""
            logger.info(f"✅ Retrieved {len(result.data)} failed clips{filter_str}")
            
            # Note: Enrichment happens in get_current_run_failed_clips for current run
            # Historical mode typically doesn't need retry status but could be added if needed
            return result.data
            
        except Exception as e:
            logger.error(f"❌ Failed to get all failed clips: {e}")
            return []
    
    def get_current_run_failed_clips(self) -> List[Dict[str, Any]]:
        """Get failed clips from the most recent processing run only"""
        try:
            latest_run_id = self.get_latest_processing_run_id()
            
            if latest_run_id:
                clips = self.get_all_failed_clips(run_id=latest_run_id)
                # Enrich with retry status
                return self._enrich_clips_with_retry_status(clips)
            else:
                logger.warning("⚠️ No processing runs found, returning empty list")
                return []
                
        except Exception as e:
            logger.error(f"❌ Failed to get current run failed clips: {e}")
            return []
    
    def _enrich_clips_with_retry_status(self, clips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add retry status information to failed clips"""
        for clip in clips:
            wo_number = clip.get('wo_number')
            if wo_number and clip['status'] in ['no_content_found', 'processing_failed']:
                # Check WO tracking for retry status
                result = self.supabase.table('wo_tracking').select('retry_after_date').eq('wo_number', wo_number).execute()
                
                if result.data and result.data[0].get('retry_after_date'):
                    retry_after = datetime.fromisoformat(result.data[0]['retry_after_date'])
                    current_time = datetime.now()
                    
                    # Handle timezone awareness
                    if retry_after.tzinfo is not None:
                        from datetime import timezone
                        current_time = datetime.now(timezone.utc)
                    elif current_time.tzinfo is not None:
                        retry_after = retry_after.replace(tzinfo=None)
                    
                    if current_time < retry_after:
                        # Still in cooldown
                        clip['retry_status'] = 'in_cooldown'
                        clip['retry_after'] = retry_after.isoformat()
                    else:
                        # Ready for retry
                        clip['retry_status'] = 'ready'
                else:
                    # No retry date set
                    clip['retry_status'] = 'ready'
        
        return clips
    
    def get_processing_run_info(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific processing run"""
        try:
            result = self.supabase.table('processing_runs').select('*').eq('id', run_id).execute()
            
            if result.data:
                run_info = result.data[0]
                logger.info(f"✅ Retrieved info for processing run: {run_info['run_name']}")
                return run_info
            else:
                logger.warning(f"⚠️ No processing run found with ID {run_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get processing run info: {e}")
            return None
    
    def update_clip_byline_author(self, wo_number: str, new_byline: str) -> bool:
        """Update the byline_author field for a specific clip"""
        try:
            result = self.supabase.table('clips').update({
                'byline_author': new_byline
            }).eq('wo_number', wo_number).execute()
            
            if result.data:
                logger.info(f"✅ Updated byline author for WO# {wo_number} to: {new_byline}")
                return True
            else:
                logger.warning(f"⚠️ No clip found with WO# {wo_number}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update byline author for WO# {wo_number}: {e}")
            return False
    
    def update_clip_media_outlet(self, wo_number: str, media_outlet: str, outlet_id: Optional[str] = None, impressions: Optional[int] = None) -> bool:
        """Update the media outlet information for a specific clip"""
        try:
            update_data = {'media_outlet': media_outlet}
            if outlet_id:
                update_data['outlet_id'] = outlet_id
            if impressions:
                update_data['impressions'] = impressions
                
            result = self.supabase.table('clips').update(update_data).eq('wo_number', wo_number).execute()
            
            if result.data:
                logger.info(f"✅ Updated media outlet for WO# {wo_number} to: {media_outlet}")
                return True
            else:
                logger.warning(f"⚠️ No clip found with WO# {wo_number}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update media outlet for WO# {wo_number}: {e}")
            return False
    
    def update_clip_published_date(self, wo_number: str, new_date: str) -> bool:
        """Update the published_date field for a specific clip"""
        try:
            # Convert date string to proper format for PostgreSQL DATE field
            formatted_date = None
            if new_date and new_date.strip() and new_date not in ['—', '-', 'None', 'null', '']:
                from datetime import datetime
                try:
                    # Try parsing MM/DD/YYYY format
                    date_obj = datetime.strptime(new_date.strip(), '%m/%d/%Y')
                    formatted_date = date_obj.strftime('%Y-%m-%d')  # PostgreSQL DATE format
                except ValueError:
                    try:
                        # Try parsing MM/DD/YY format (legacy)
                        date_obj = datetime.strptime(new_date.strip(), '%m/%d/%y')
                        formatted_date = date_obj.strftime('%Y-%m-%d')
                    except ValueError:
                        logger.warning(f"⚠️ Invalid date format for WO# {wo_number}: {new_date}")
                        return False
            
            # Update with properly formatted date or NULL
            result = self.supabase.table('clips').update({
                'published_date': formatted_date
            }).eq('wo_number', wo_number).execute()
            
            if result.data:
                logger.info(f"✅ Updated published date for WO# {wo_number} to: {formatted_date}")
                return True
            else:
                logger.warning(f"⚠️ No clip found with WO# {wo_number}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update published date for WO# {wo_number}: {e}")
            return False
    
    def update_clip_url(self, wo_number: str, new_url: str) -> bool:
        """Update the clip_url field for a specific clip"""
        try:
            result = self.supabase.table('clips').update({
                'clip_url': new_url
            }).eq('wo_number', wo_number).execute()
            
            if result.data:
                logger.info(f"✅ Updated clip URL for WO# {wo_number} to: {new_url}")
                return True
            else:
                logger.warning(f"⚠️ No clip found with WO# {wo_number}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update clip URL for WO# {wo_number}: {e}")
            return False

# Global database instance
_db_instance = None

def get_database() -> DatabaseManager:
    """Get global database instance (singleton pattern)"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance 