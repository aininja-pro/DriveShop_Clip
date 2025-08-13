"""
Sentiment Analysis utilities for clip content
"""

import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

from src.utils.logger import setup_logger
from src.analysis.gpt_analysis import analyze_clip
try:
    # Try to import the v1 API version first (for OpenAI 1.x)
    from src.analysis.gpt_analysis_enhanced_v1 import analyze_clip_enhanced
    logger = setup_logger(__name__)
    logger.info("Using OpenAI v1.x compatible enhanced analyzer")
except ImportError:
    # Fall back to original if v1 doesn't exist
    from src.analysis.gpt_analysis_enhanced import analyze_clip_enhanced
    logger = setup_logger(__name__)
    logger.info("Using original enhanced analyzer")

from src.utils.youtube_handler import extract_video_id, get_transcript
from src.utils.database import DatabaseManager

class SentimentAnalyzer:
    """Handles sentiment analysis for clips using OpenAI"""
    
    def __init__(self, use_enhanced=True):
        """Initialize the sentiment analyzer
        
        Args:
            use_enhanced: Whether to use enhanced Message Pull-Through analysis
        """
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.use_enhanced = use_enhanced
        self.db = DatabaseManager()
        # Note: We'll use the existing analyze_clip function which handles API key internally
        
    async def analyze_clip_sentiment(self, clip_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze sentiment for a single clip using the advanced GPT analysis
        
        Args:
            clip_data: Dictionary containing clip information including extracted_content
            
        Returns:
            Dictionary with sentiment analysis results
        """
        try:
            content = clip_data.get('extracted_content', '')
            
            # Check if this is a YouTube video with insufficient content
            if 'youtube.com' in clip_data.get('clip_url', '') or 'youtu.be' in clip_data.get('clip_url', ''):
                # Check if content is too short OR looks like metadata
                is_metadata = (
                    'Video Title:' in content and 'Channel:' in content and 'Video Description:' in content
                ) or (
                    'video_title' in content.lower() or 'channel_name' in content.lower()
                )
                
                # If content is too short (likely just metadata), try to re-extract
                if not content or len(content) < 1000 or is_metadata:
                    logger.info(f"YouTube clip {clip_data.get('wo_number')} has insufficient content ({len(content or '')} chars), attempting re-extraction...")
                    
                    video_id = extract_video_id(clip_data.get('clip_url', ''))
                    if video_id:
                        try:
                            # Re-extract with Whisper fallback - but with timeout protection
                            new_content = get_transcript(video_id, video_url=clip_data.get('clip_url', ''), use_whisper_fallback=True)
                            
                            if new_content and len(new_content) > len(content or ''):
                                logger.info(f"✅ Re-extracted YouTube content: {len(new_content)} chars (was {len(content or '')} chars)")
                                content = new_content
                            else:
                                logger.warning(f"Re-extraction failed or returned no better content, using original {len(content or '')} chars")
                        except Exception as e:
                            logger.error(f"Failed to re-extract YouTube content: {e}")
                            logger.warning(f"Falling back to minimal content ({len(content or '')} chars) for sentiment analysis")
                            # Continue with what we have rather than failing
                            
                            # Update the database with new content
                            self.db.supabase.table('clips').update({
                                'extracted_content': content
                            }).eq('id', clip_data['id']).execute()
                        else:
                            logger.warning(f"Failed to get better content for YouTube video {video_id}")
            
            if not content:
                logger.warning(f"No content found for clip {clip_data.get('wo_number')}")
                return {
                    'error': 'No content to analyze',
                    'sentiment_completed': False
                }
            
            # Extract vehicle details
            make = clip_data.get('make', '')
            model = clip_data.get('model', '')
            url = clip_data.get('clip_url', '')
            
            # Extract year and trim if available
            year = None
            trim = None
            
            # Try to parse year from model (e.g., "2024 Camry XLE")
            model_parts = model.split()
            if model_parts and model_parts[0].isdigit() and len(model_parts[0]) == 4:
                year = model_parts[0]
                model = ' '.join(model_parts[1:])
                
                # Check if last part might be trim
                if len(model_parts) > 2:
                    potential_trim = model_parts[-1]
                    if any(indicator in potential_trim.upper() for indicator in ['XLE', 'XSE', 'SR', 'LIMITED', 'SPORT', 'BASE', 'LX', 'EX', 'SI']):
                        trim = potential_trim
                        model = ' '.join(model_parts[1:-1])
            
            # Choose analyzer based on configuration
            if self.use_enhanced:
                analyzer_func = analyze_clip_enhanced
                analyzer_args = (content, make, model, year, trim, 3, url)
            else:
                analyzer_func = analyze_clip
                analyzer_args = (content, make, model, 3, url)
            
            # Run analysis in thread pool since analyze_clip is synchronous
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                analyzer_func,
                *analyzer_args
            )
            
            # Handle None result (no API key or parsing failed)
            if result is None:
                return {
                    'error': 'Analysis failed - no data returned from GPT',
                    'sentiment_completed': False
                }
            
            # Add sentiment completion fields
            result['sentiment_completed'] = True
            result['sentiment_analysis_date'] = datetime.now().isoformat()
            
            # Ensure we have all required fields for database
            if 'overall_sentiment' not in result:
                result['overall_sentiment'] = result.get('sentiment', 'neutral')
            
            logger.info(f"✅ Advanced sentiment analysis completed for WO# {clip_data.get('wo_number')}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error analyzing sentiment for clip {clip_data.get('wo_number')}: {e}")
            return {
                'error': str(e),
                'sentiment_completed': False
            }
    
    async def analyze_clips_batch(self, clips: List[Dict[str, Any]], 
                                 progress_callback=None) -> List[Dict[str, Any]]:
        """
        Analyze sentiment for multiple clips in batch
        
        Args:
            clips: List of clip dictionaries
            progress_callback: Optional callback function to report progress
            
        Returns:
            List of sentiment analysis results
        """
        results = []
        total = len(clips)
        
        # Process in smaller batches to avoid rate limits
        batch_size = 5
        for i in range(0, total, batch_size):
            batch = clips[i:i+batch_size]
            
            # Create tasks for concurrent processing
            tasks = [self.analyze_clip_sentiment(clip) for clip in batch]
            batch_results = await asyncio.gather(*tasks)
            
            results.extend(batch_results)
            
            # Report progress
            if progress_callback:
                progress = min(i + batch_size, total) / total
                progress_callback(progress, f"Analyzed {min(i + batch_size, total)}/{total} clips")
            
            # Small delay to avoid rate limits
            if i + batch_size < total:
                await asyncio.sleep(1)
        
        return results
    
    def analyze_clips_sync(self, clips: List[Dict[str, Any]], 
                          progress_callback=None) -> List[Dict[str, Any]]:
        """
        Synchronous wrapper for batch sentiment analysis
        
        Args:
            clips: List of clip dictionaries
            progress_callback: Optional callback function to report progress
            
        Returns:
            List of sentiment analysis results
        """
        try:
            # Create new event loop if none exists
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run the async function
            results = loop.run_until_complete(
                self.analyze_clips_batch(clips, progress_callback)
            )
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in batch sentiment analysis: {e}")
            return []


def run_sentiment_analysis(clips: List[Dict[str, Any]], 
                         progress_callback=None) -> Dict[str, Any]:
    """
    Main function to run sentiment analysis on clips
    
    Args:
        clips: List of clip dictionaries
        progress_callback: Optional callback function to report progress
        
    Returns:
        Dictionary with results and statistics
    """
    try:
        analyzer = SentimentAnalyzer()
        results = analyzer.analyze_clips_sync(clips, progress_callback)
        
        # Calculate statistics
        successful = [r for r in results if r.get('sentiment_completed', False)]
        failed = [r for r in results if not r.get('sentiment_completed', False)]
        
        stats = {
            'total_processed': len(results),
            'successful': len(successful),
            'failed': len(failed),
            'results': results
        }
        
        logger.info(f"✅ Sentiment analysis completed: {len(successful)}/{len(results)} successful")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Failed to run sentiment analysis: {e}")
        return {
            'total_processed': 0,
            'successful': 0,
            'failed': len(clips),
            'results': [],
            'error': str(e)
        }