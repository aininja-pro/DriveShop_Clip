"""
Sentiment Analysis utilities for clip content
"""

import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

from src.utils.logger import setup_logger
from src.analysis.gpt_analysis import analyze_clip

logger = setup_logger(__name__)

class SentimentAnalyzer:
    """Handles sentiment analysis for clips using OpenAI"""
    
    def __init__(self):
        """Initialize the sentiment analyzer"""
        self.api_key = os.environ.get("OPENAI_API_KEY")
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
            if not content:
                logger.warning(f"No content found for clip {clip_data.get('wo_number')}")
                return {
                    'error': 'No content to analyze',
                    'sentiment_completed': False
                }
            
            # Use the existing advanced analyze_clip function
            make = clip_data.get('make', '')
            model = clip_data.get('model', '')
            url = clip_data.get('clip_url', '')
            
            # Run analysis in thread pool since analyze_clip is synchronous
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                analyze_clip,
                content,
                make,
                model,
                3,  # max_retries
                url
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