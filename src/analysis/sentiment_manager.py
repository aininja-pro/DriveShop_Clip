"""
Sentiment Analysis Manager for Message Pull-Through Analysis
Handles both current automated flow and new enhanced analysis capabilities
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio

from src.utils.logger import setup_logger
from src.database.connection import get_supabase_client
from src.analysis.gpt_analysis_enhanced import analyze_clip_enhanced
from src.analysis.gpt_analysis import analyze_clip as analyze_clip_original

logger = setup_logger(__name__)

class SentimentManager:
    """
    Manages sentiment analysis operations including:
    - Running enhanced sentiment analysis
    - Re-processing clips with updated prompts
    - Batch processing historical clips
    - Maintaining backward compatibility
    """
    
    def __init__(self, use_enhanced: bool = True):
        """
        Initialize the Sentiment Manager
        
        Args:
            use_enhanced: Whether to use enhanced Message Pull-Through prompt
        """
        self.supabase = get_supabase_client()
        self.use_enhanced = use_enhanced
        
    def analyze_clip(self, clip_data: Dict[str, Any], force_enhanced: bool = None) -> Optional[Dict[str, Any]]:
        """
        Analyze a single clip with sentiment analysis
        
        Args:
            clip_data: Clip data including content, make, model, etc.
            force_enhanced: Override the default analysis type
            
        Returns:
            Analysis results or None if failed
        """
        try:
            # Determine which analyzer to use
            use_enhanced_analysis = force_enhanced if force_enhanced is not None else self.use_enhanced
            
            # Extract required fields
            content = clip_data.get('extracted_content', '')
            make = clip_data.get('make', '')
            model = clip_data.get('model', '')
            url = clip_data.get('clip_url', '')
            
            # Extract year and trim if available (from model field or separate)
            year = None
            trim = None
            
            # Try to parse year from model (e.g., "2024 Camry XLE")
            model_parts = model.split()
            if model_parts and model_parts[0].isdigit() and len(model_parts[0]) == 4:
                year = model_parts[0]
                # Reconstruct model without year
                model = ' '.join(model_parts[1:])
                
                # Check if last part might be trim
                if len(model_parts) > 2:
                    potential_trim = model_parts[-1]
                    # Common trim indicators
                    if any(indicator in potential_trim.upper() for indicator in ['XLE', 'XSE', 'SR', 'LIMITED', 'SPORT', 'BASE', 'LX', 'EX', 'SI']):
                        trim = potential_trim
                        model = ' '.join(model_parts[1:-1])
            
            logger.info(f"Analyzing clip: {make} {model} {year} {trim} - Using {'enhanced' if use_enhanced_analysis else 'original'} analyzer")
            
            if use_enhanced_analysis:
                # Use enhanced Message Pull-Through analysis
                analysis_result = analyze_clip_enhanced(
                    content=content,
                    make=make,
                    model=model,
                    year=year,
                    trim=trim,
                    url=url
                )
            else:
                # Use original analysis for backward compatibility
                analysis_result = analyze_clip_original(
                    content=content,
                    make=make,
                    model=model,
                    url=url
                )
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing clip: {e}")
            return None
    
    def save_analysis_results(self, clip_id: str, analysis_result: Dict[str, Any], is_enhanced: bool = None) -> bool:
        """
        Save analysis results to database
        
        Args:
            clip_id: ID of the clip
            analysis_result: Analysis results from GPT
            is_enhanced: Whether this is enhanced analysis
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if is_enhanced is None:
                is_enhanced = self.use_enhanced
            
            # Prepare update data
            update_data = {
                'sentiment_analysis_date': datetime.utcnow().isoformat(),
                'workflow_stage': 'sentiment_analyzed'
            }
            
            if is_enhanced and analysis_result:
                # Save enhanced data to JSONB column
                update_data['sentiment_data_enhanced'] = json.dumps(analysis_result)
                update_data['sentiment_version'] = 'v2'
                
                # Also update legacy fields for backward compatibility
                update_data['relevance_score'] = analysis_result.get('relevance_score', 0)
                update_data['overall_sentiment'] = analysis_result.get('overall_sentiment', 'neutral')
                update_data['brand_alignment'] = analysis_result.get('brand_alignment', False)
                update_data['summary'] = analysis_result.get('summary', '')
                
            else:
                # Save original format
                update_data['relevance_score'] = analysis_result.get('relevance_score', 0)
                update_data['overall_sentiment'] = analysis_result.get('overall_sentiment', 'neutral')
                update_data['brand_alignment'] = analysis_result.get('brand_alignment', False)
                update_data['summary'] = analysis_result.get('summary', '')
                update_data['sentiment_version'] = 'v1'
            
            # Update the clip
            response = self.supabase.table('clips').update(update_data).eq('id', clip_id).execute()
            
            if response.data:
                logger.info(f"Successfully saved {'enhanced' if is_enhanced else 'original'} sentiment analysis for clip {clip_id}")
                return True
            else:
                logger.error(f"Failed to save sentiment analysis for clip {clip_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving analysis results: {e}")
            return False
    
    def get_clips_for_analysis(self, 
                               status: str = 'approved',
                               limit: int = 100,
                               force_reanalyze: bool = False,
                               only_missing: bool = True) -> List[Dict[str, Any]]:
        """
        Get clips that need sentiment analysis
        
        Args:
            status: Clip status to filter by
            limit: Maximum number of clips to return
            force_reanalyze: Include clips that already have sentiment
            only_missing: Only return clips without any sentiment analysis
            
        Returns:
            List of clips needing analysis
        """
        try:
            query = self.supabase.table('clips').select('*').eq('status', status)
            
            if only_missing and not force_reanalyze:
                # Only clips without sentiment analysis
                query = query.is_('sentiment_analysis_date', 'null')
            elif not force_reanalyze:
                # Clips without enhanced analysis (even if they have v1)
                query = query.or_('sentiment_version.neq.v2,sentiment_version.is.null')
            
            # Order by processed date and limit
            query = query.order('processed_date', desc=True).limit(limit)
            
            response = query.execute()
            
            if response.data:
                logger.info(f"Found {len(response.data)} clips for sentiment analysis")
                return response.data
            else:
                logger.info("No clips found for sentiment analysis")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching clips for analysis: {e}")
            return []
    
    async def process_batch(self, clips: List[Dict[str, Any]], use_enhanced: bool = None) -> Dict[str, Any]:
        """
        Process a batch of clips for sentiment analysis
        
        Args:
            clips: List of clips to analyze
            use_enhanced: Override default analysis type
            
        Returns:
            Summary of processing results
        """
        results = {
            'total': len(clips),
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for clip in clips:
            try:
                # Check if content exists
                if not clip.get('extracted_content'):
                    logger.warning(f"Skipping clip {clip['id']} - no content")
                    results['skipped'] += 1
                    continue
                
                # Analyze the clip
                analysis_result = self.analyze_clip(clip, force_enhanced=use_enhanced)
                
                if analysis_result:
                    # Save results
                    if self.save_analysis_results(clip['id'], analysis_result, is_enhanced=use_enhanced):
                        results['successful'] += 1
                        logger.info(f"Successfully analyzed clip {clip['id']}")
                    else:
                        results['failed'] += 1
                        logger.error(f"Failed to save results for clip {clip['id']}")
                else:
                    results['failed'] += 1
                    logger.error(f"Failed to analyze clip {clip['id']}")
                    
                # Add small delay to avoid rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing clip {clip.get('id', 'unknown')}: {e}")
                results['failed'] += 1
        
        logger.info(f"Batch processing complete: {results}")
        return results
    
    def reprocess_with_enhanced_prompt(self, make: str = None, model: str = None, limit: int = 50) -> Dict[str, Any]:
        """
        Reprocess existing clips with the enhanced sentiment prompt
        
        Args:
            make: Filter by vehicle make
            model: Filter by vehicle model  
            limit: Maximum number to process
            
        Returns:
            Processing summary
        """
        try:
            # Build query for clips to reprocess
            query = self.supabase.table('clips').select('*').eq('status', 'approved')
            
            # Only get clips with v1 sentiment or no version
            query = query.or_('sentiment_version.eq.v1,sentiment_version.is.null')
            
            # Apply filters if provided
            if make:
                query = query.eq('make', make)
            if model:
                query = query.eq('model', model)
                
            # Get clips with existing sentiment first (to prioritize re-analysis)
            query = query.not_.is_('sentiment_analysis_date', 'null')
            query = query.order('sentiment_analysis_date', desc=True).limit(limit)
            
            response = query.execute()
            
            if response.data:
                logger.info(f"Found {len(response.data)} clips to reprocess with enhanced prompt")
                
                # Process them with enhanced prompt
                return asyncio.run(self.process_batch(response.data, use_enhanced=True))
            else:
                logger.info("No clips found for reprocessing")
                return {'total': 0, 'successful': 0, 'failed': 0, 'skipped': 0}
                
        except Exception as e:
            logger.error(f"Error in reprocess_with_enhanced_prompt: {e}")
            return {'total': 0, 'successful': 0, 'failed': 0, 'skipped': 0}
    
    def get_analysis_summary(self, make: str, model: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Get summary of sentiment analysis for a vehicle
        
        Args:
            make: Vehicle make
            model: Vehicle model
            days_back: Number of days to look back
            
        Returns:
            Summary statistics and insights
        """
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            
            # Query clips with enhanced sentiment
            response = self.supabase.table('clips').select('*').eq('make', make).eq('model', model).eq('status', 'approved').not_.is_('sentiment_data_enhanced', 'null').gte('published_date', start_date.date().isoformat()).lte('published_date', end_date.date().isoformat()).execute()
            
            if not response.data:
                return {'error': 'No analyzed clips found for this vehicle'}
            
            clips = response.data
            
            # Aggregate data
            summary = {
                'vehicle': f"{make} {model}",
                'period': f"{start_date.date()} to {end_date.date()}",
                'total_clips': len(clips),
                'sentiment_breakdown': {},
                'top_features': [],
                'top_attributes': [],
                'top_purchase_drivers': [],
                'competitive_mentions': []
            }
            
            # Count sentiments
            sentiment_counts = {}
            all_features = {}
            all_attributes = {}
            all_drivers = {}
            all_competitors = set()
            
            for clip in clips:
                if clip.get('sentiment_data_enhanced'):
                    try:
                        enhanced_data = json.loads(clip['sentiment_data_enhanced'])
                        
                        # Count overall sentiment
                        sentiment = enhanced_data.get('sentiment_classification', {}).get('overall', 'neutral')
                        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
                        
                        # Aggregate features
                        for feature in enhanced_data.get('key_features_mentioned', []):
                            feature_name = feature.get('feature', '')
                            if feature_name not in all_features:
                                all_features[feature_name] = {'positive': 0, 'neutral': 0, 'negative': 0}
                            all_features[feature_name][feature.get('sentiment', 'neutral')] += 1
                        
                        # Aggregate attributes
                        for attr in enhanced_data.get('brand_attributes_captured', []):
                            attr_name = attr.get('attribute', '')
                            if attr_name not in all_attributes:
                                all_attributes[attr_name] = {'reinforced': 0, 'neutral': 0, 'challenged': 0}
                            all_attributes[attr_name][attr.get('sentiment', 'neutral')] += 1
                        
                        # Aggregate drivers
                        for driver in enhanced_data.get('purchase_drivers', []):
                            driver_reason = driver.get('reason', '')
                            if driver_reason not in all_drivers:
                                all_drivers[driver_reason] = {'positive': 0, 'negative': 0, 'primary': 0}
                            all_drivers[driver_reason][driver.get('sentiment', 'positive')] += 1
                            if driver.get('strength') == 'primary':
                                all_drivers[driver_reason]['primary'] += 1
                        
                        # Collect competitors
                        competitive = enhanced_data.get('competitive_context', {})
                        for comp in competitive.get('direct_comparisons', []):
                            if ':' in comp:
                                competitor = comp.split(':')[0].strip()
                                all_competitors.add(competitor)
                                
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse enhanced data for clip {clip['id']}")
            
            # Format results
            summary['sentiment_breakdown'] = sentiment_counts
            
            # Top features (sorted by total mentions)
            feature_list = []
            for feat, counts in all_features.items():
                total = sum(counts.values())
                feature_list.append({
                    'feature': feat,
                    'total_mentions': total,
                    'sentiment_breakdown': counts
                })
            summary['top_features'] = sorted(feature_list, key=lambda x: x['total_mentions'], reverse=True)[:10]
            
            # Top attributes
            attr_list = []
            for attr, counts in all_attributes.items():
                total = sum(counts.values())
                attr_list.append({
                    'attribute': attr,
                    'total_mentions': total,
                    'sentiment_breakdown': counts
                })
            summary['top_attributes'] = sorted(attr_list, key=lambda x: x['total_mentions'], reverse=True)[:5]
            
            # Top purchase drivers
            driver_list = []
            for driver, counts in all_drivers.items():
                total = counts.get('positive', 0) + counts.get('negative', 0)
                driver_list.append({
                    'driver': driver,
                    'total_mentions': total,
                    'primary_mentions': counts.get('primary', 0),
                    'sentiment_breakdown': {k: v for k, v in counts.items() if k != 'primary'}
                })
            summary['top_purchase_drivers'] = sorted(driver_list, key=lambda x: (x['primary_mentions'], x['total_mentions']), reverse=True)[:5]
            
            # Competitive mentions
            summary['competitive_mentions'] = list(all_competitors)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting analysis summary: {e}")
            return {'error': str(e)}


# Utility functions for backward compatibility
def run_sentiment_analysis_batch(limit: int = 50, use_enhanced: bool = True) -> Dict[str, Any]:
    """
    Run sentiment analysis on a batch of approved clips
    
    Args:
        limit: Number of clips to process
        use_enhanced: Whether to use enhanced analysis
        
    Returns:
        Processing summary
    """
    manager = SentimentManager(use_enhanced=use_enhanced)
    clips = manager.get_clips_for_analysis(limit=limit, only_missing=True)
    
    if clips:
        return asyncio.run(manager.process_batch(clips))
    else:
        return {'total': 0, 'successful': 0, 'failed': 0, 'skipped': 0}


def reprocess_clips_enhanced(make: str = None, model: str = None, limit: int = 50) -> Dict[str, Any]:
    """
    Reprocess existing clips with enhanced sentiment analysis
    
    Args:
        make: Filter by make
        model: Filter by model
        limit: Number to process
        
    Returns:
        Processing summary
    """
    manager = SentimentManager(use_enhanced=True)
    return manager.reprocess_with_enhanced_prompt(make=make, model=model, limit=limit)