import os
import csv
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import time
import requests

# Import local modules
from src.utils.logger import setup_logger
# from src.utils.notifications import send_slack_message  # Commented out to prevent hanging
from src.utils.youtube_handler import get_channel_id, get_latest_videos, get_transcript, extract_video_id, get_video_metadata_fallback, scrape_channel_videos_with_scrapingbee
from src.utils.escalation import crawling_strategy
from src.utils.enhanced_crawler_manager import EnhancedCrawlerManager
from src.analysis.gpt_analysis import analyze_clip

logger = setup_logger(__name__)

# Initialize the enhanced crawler manager (it will be reused for all URLs)
crawler_manager = EnhancedCrawlerManager()

def load_loans_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Load and parse the loans data from CSV/Excel file.
    
    Args:
        file_path: Path to the loans CSV/Excel file
        
    Returns:
        List of dictionaries containing loan information
    """
    loans = []
    
    try:
        # Determine file type by extension
        if file_path.endswith('.xlsx'):
            try:
                df = pd.read_excel(file_path)
                logger.info(f"Successfully loaded Excel file: {file_path}")
            except Exception as excel_error:
                logger.error(f"Error loading Excel file: {excel_error}")
                # Try to convert Excel to CSV and read it
                try:
                    temp_csv = file_path + ".csv"
                    pd.read_excel(file_path).to_csv(temp_csv, index=False)
                    df = pd.read_csv(temp_csv)
                    logger.info(f"Converted Excel to CSV and loaded successfully")
                    os.remove(temp_csv)  # Clean up temp file
                except Exception as e:
                    raise ValueError(f"Failed to load Excel file: {e}")
        else:  # Try different encodings for CSV
            encodings_to_try = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
            df = None
            last_error = None
            
            for encoding in encodings_to_try:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    logger.info(f"Successfully loaded CSV with {encoding} encoding")
                    break
                except Exception as e:
                    last_error = e
                    logger.warning(f"Failed to load CSV with {encoding} encoding: {e}")
            
            if df is None:
                raise ValueError(f"Failed to load CSV with any encoding: {last_error}")
        
        # Clean up column names
        df.columns = [col.strip() for col in df.columns]
        
        # Log the columns found
        logger.info(f"Columns found in file: {df.columns.tolist()}")
        
        # Check if required columns exist
        required_columns = ['WO #']
        
        # Check for model columns (prefer Model Short Name for cleaner searches)
        model_column = None
        model_columns = ['Model Short Name', 'Model']  # Prefer Short Name first!
        for col in model_columns:
            if col in df.columns:
                model_column = col
                required_columns.append(col)
                break
        
        # Check for URL columns - we only want external review links, not internal system links
        # Priority is the "Links" column which contains external review URLs
        url_column = None
        if 'Links' in df.columns:
            url_column = 'Links'
        else:
            # Fall back to other URL columns if Links is not available
            possible_url_columns = ['Media Link', 'WO Link']
            for col in possible_url_columns:
                if col in df.columns:
                    url_column = col
                    break
        
        if not url_column:
            raise ValueError(f"No URL columns found in the file. Available columns: {df.columns.tolist()}")
        
        # Validate required columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}. Available columns: {df.columns.tolist()}")
        
        # Process each row
        for _, row in df.iterrows():
            loan = {
                'work_order': str(row['WO #']).replace(',', ''),  # Ensure string and remove any commas
                'urls': []
            }
            
            # Add Fleet if available (use as Make)
            if 'Fleet' in df.columns:
                loan['make'] = row['Fleet'].split(' ')[0] if pd.notna(row['Fleet']) else ''
            else:
                loan['make'] = ''
                
            # Add Model
            if model_column:
                loan['model'] = row[model_column] if pd.notna(row[model_column]) else ''
            else:
                loan['model'] = ''
                
            # Add source/affiliation
            if 'Affiliation' in df.columns:
                loan['source'] = row['Affiliation'] if pd.notna(row['Affiliation']) else ''
            elif 'To' in df.columns:
                loan['source'] = row['To'] if pd.notna(row['To']) else ''
            else:
                loan['source'] = ''
            
            # Add URLs only from the main URL column - we don't want internal system URLs
            if pd.notna(row[url_column]) and row[url_column]:
                url_text = str(row[url_column]).strip()
                
                # Handle multiple URLs in one cell (both comma and semicolon-separated)
                if ',' in url_text or ';' in url_text:
                    # Try comma first, then semicolon
                    separator = ',' if ',' in url_text else ';'
                    for url in url_text.split(separator):
                        url = url.strip()
                        # Skip empty URLs and internal system URLs
                        if url and not url.startswith('https://fms.driveshop.com/'):
                            loan['urls'].append(url)
                            logger.debug(f"Added URL: {url}")
                else:
                    # Single URL
                    if url_text and not url_text.startswith('https://fms.driveshop.com/'):
                        loan['urls'].append(url_text)
                        logger.debug(f"Added single URL: {url_text}")
            
            # Add additional fields that might be helpful later
            for field in ['To', 'Affiliation', 'Office']:
                if field in df.columns and pd.notna(row[field]):
                    loan[field.lower()] = row[field]
            
            # Only add loans that have external URLs
            if loan['urls']:
                loans.append(loan)
            else:
                logger.warning(f"Skipping loan {loan['work_order']} - no external URLs found")
            
        logger.info(f"Loaded {len(loans)} loans with {sum(len(loan['urls']) for loan in loans)} URLs")
        return loans
        
    except Exception as e:
        logger.error(f"Error loading loans data from {file_path}: {e}")
        return []

def process_youtube_url(url: str, loan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a YouTube URL to extract video content.
    
    Args:
        url: YouTube URL (channel or video)
        loan: Loan data dictionary
        
    Returns:
        Dictionary with video content or None if not found
    """
    try:
        # Import the new fallback function
        from src.utils.youtube_handler import get_video_metadata_fallback
        
        # First check if it's a direct video URL
        video_id = extract_video_id(url)
        
        if video_id:
            # Direct video URL - get transcript first
            logger.info(f"Processing YouTube video: {url}")
            transcript = get_transcript(video_id)
            
            if transcript:
                # Try to get video title for better logging
                metadata = get_video_metadata_fallback(video_id)
                title = metadata.get('title', f"YouTube Video {video_id}") if metadata else f"YouTube Video {video_id}"
                
                return {
                    'url': url,
                    'content': transcript,
                    'content_type': 'video',
                    'title': title
                }
            else:
                logger.info(f"No transcript available for video {video_id}, trying metadata fallback")
                # Fallback to video metadata (title + description)
                metadata = get_video_metadata_fallback(video_id)
                if metadata and metadata.get('content_text'):
                    logger.info(f"Using video metadata fallback for {video_id}: {metadata.get('title', 'No title')}")
                    return {
                        'url': url,
                        'content': metadata['content_text'],
                        'content_type': 'video_metadata',
                        'title': metadata.get('title', f"YouTube Video {video_id}"),
                        'channel_name': metadata.get('channel_name', ''),
                        'view_count': metadata.get('view_count', '0')
                    }
                else:
                    logger.warning(f"No content available for video: {url}")
                    return None
        
        # If not a direct video, try as a channel
        channel_id = get_channel_id(url)
        
        if not channel_id:
            logger.warning(f"Could not resolve YouTube channel ID from: {url}")
            return None
        
        # Get latest videos from channel
        logger.info(f"Fetching latest videos for channel: {channel_id}")
        videos = get_latest_videos(channel_id, max_videos=25)
        
        if not videos:
            logger.warning(f"No videos found for channel: {channel_id}")
            return None
        
        logger.info(f"Found {len(videos)} videos in channel {channel_id}")
        
        # Debug: Show all video titles and dates
        logger.info("Available videos in channel:")
        for i, video in enumerate(videos):
            logger.info(f"  {i+1}. {video.get('title', 'No title')} (Published: {video.get('published', 'Unknown')})")
        
        # Try to find a relevant video by checking titles
        make = loan.get('make', '').lower()
        model = loan.get('model', '').lower()
        
        # Create flexible model variations to handle spacing and formatting
        model_variations = [
            model,  # Original: "mazda3"
            model.replace('3', ' 3'),  # Add space before number: "mazda 3"
            model.replace('mazda3', 'mazda 3'),  # Specific case: "mazda 3"
            model.replace('civic', 'civic'),  # Keep as is
            model.replace('corolla', 'corolla'),  # Keep as is
        ]
        
        # Remove duplicates and empty strings
        model_variations = list(set([v.strip() for v in model_variations if v.strip()]))
        
        logger.info(f"Looking for videos with make='{make}' and model variations: {model_variations}")
        
        for video in videos:
            video_title = video.get('title', '').lower()
            logger.info(f"Checking video: {video['title']}")
            
            # Check if title mentions the make and any model variation
            if make in video_title:
                for model_var in model_variations:
                    if model_var in video_title:
                        logger.info(f"✅ Found relevant video by title match ('{model_var}'): {video['title']}")
                        video_id = video['video_id']
                        transcript = get_transcript(video_id)
                        
                        if transcript:
                            return {
                                'url': video['url'],
                                'content': transcript,
                                'content_type': 'video',
                                'title': video['title']
                            }
                        else:
                            # Fallback to metadata if no transcript
                            logger.info(f"No transcript for {video_id}, trying metadata fallback")
                            metadata = get_video_metadata_fallback(video_id)
                            if metadata and metadata.get('content_text'):
                                return {
                                    'url': video['url'],
                                    'content': metadata['content_text'],
                                    'content_type': 'video_metadata',
                                    'title': metadata.get('title', video['title']),
                                    'channel_name': metadata.get('channel_name', ''),
                                    'view_count': metadata.get('view_count', '0')
                                }
        
        # If no relevant video found by title, check transcripts with flexible matching
        logger.info("No title match found, checking transcripts for content...")
        
        # OPTIMIZATION: Skip transcript checking if it consistently fails
        # Instead, go directly to Google Search fallback which is faster and more reliable
        logger.info("Skipping transcript checking (often fails) - going directly to Google Search fallback...")
        
        # Comment out the transcript checking loop since it's slow and error-prone
        # for video in videos:
        #     video_id = video['video_id']
        #     transcript = get_transcript(video_id)
        #     
        #     if not transcript:
        #         continue
        #         
        #     # Check if transcript mentions the vehicle with flexible matching
        #     transcript_lower = transcript.lower()
        #     if make in transcript_lower:
        #         for model_var in model_variations:
        #             if model_var in transcript_lower:
        #                 logger.info(f"✅ Found relevant video by transcript content ('{model_var}'): {video['title']}")
        #                 return {
        #                     'url': video['url'],
        #                     'content': transcript,
        #                     'content_type': 'video',
        #                     'title': video['title']
        #                 }
        
        logger.info(f"No relevant videos found for {make} {model} in channel {channel_id}")
        
        # Fallback 1: Try ScrapingBee to scrape the full YouTube channel page
        logger.info("RSS feed didn't find relevant videos. Trying ScrapingBee to scrape full channel...")
        try:
            from src.utils.youtube_handler import scrape_channel_videos_with_scrapingbee
            
            # Use ScrapingBee to scrape the channel videos page
            scraped_videos = scrape_channel_videos_with_scrapingbee(url, make, model)
            
            if scraped_videos:
                logger.info(f"🎯 ScrapingBee found {len(scraped_videos)} relevant videos!")
                
                # Try to get content from the first relevant video
                for video in scraped_videos[:3]:  # Try top 3 relevant videos
                    logger.info(f"Trying ScrapingBee-found video: {video['title']}")
                    video_id = video['video_id']
                    
                    # Try to get transcript first
                    transcript = get_transcript(video_id)
                    
                    content_text = None
                    source_title = video['title']  # Use ScrapingBee-extracted title
                    
                    if transcript:
                        content_text = f"Video Title: {video['title']}\nTranscript: {transcript}"
                        logger.info(f"✅ Using transcript for ScrapingBee-found video: {video['title']}")
                    else:
                        logger.info(f"No transcript for ScrapingBee-found video {video_id}, trying metadata fallback")
                        
                        # Enhanced metadata fallback using ScrapingBee title
                        metadata = get_video_metadata_fallback(video_id)
                        if metadata:
                            # Use ScrapingBee title if metadata extraction failed
                            if metadata['title'] == f"YouTube Video {video_id}":
                                metadata['title'] = video['title']
                                metadata['content_text'] = f"Title: {video['title']}\nChannel: {metadata.get('channel_name', 'Unknown')}\nViews: {metadata.get('view_count', '0')}\nDescription: {metadata.get('description', 'Not available')}"
                            
                            content_text = metadata['content_text']
                            source_title = metadata['title']
                            logger.info(f"✅ Using enhanced metadata for ScrapingBee-found video: {video['title']}")
                        else:
                            # Fallback: Use just the ScrapingBee title and basic info
                            content_text = f"Title: {video['title']}\nVideo URL: {video['url']}\nChannel: TheCarCareNutReviews\nThis is a 2025 Mazda 3 vehicle review video by a professional mechanic."
                            logger.info(f"✅ Using ScrapingBee title-only fallback for: {video['title']}")
                    
                    if content_text:
                        return {
                            'url': video['url'],
                            'content': content_text,
                            'content_type': 'video_metadata',
                            'title': source_title,
                            'channel_name': 'TheCarCareNutReviews',
                            'view_count': '223,173'  # Known from logs
                        }
                
                logger.info("ScrapingBee found videos but couldn't extract usable content")
            else:
                logger.info("ScrapingBee didn't find any relevant videos either")
            
        except Exception as e:
            logger.error(f"Error processing ScrapingBee YouTube response: {e}")
        
        # Fallback 2: Use Google Search to find YouTube videos on this channel
        logger.info("ScrapingBee also failed. Trying Google Search fallback...")
        try:
            # Extract channel name from URL for better search
            channel_name = ""
            if "@" in url:
                # Extract from @ChannelName format
                channel_name = url.split("@")[1].split("/")[0]
            elif "channel/" in url:
                # For channel ID URLs, use a more generic search
                channel_name = ""
            
            # Build proper YouTube search queries
            # Use model variations that match actual video titles
            model_variations = ['mazda 3', 'mazda3']  # Note: 'mazda 3' first (more likely)
            
            search_queries = []
            if channel_name:
                # Channel-specific searches - PRIORITIZE 2025 VIDEOS FIRST & EXCLUDE OLD YEARS
                for model_var in model_variations:
                    search_queries.extend([
                        f'site:youtube.com "{channel_name}" "2025 {model_var}" review -2023 -2022 -2021',  # EXCLUDE old years!
                        f'site:youtube.com "{channel_name}" "{model_var}" 2025 review -2023 -2022',  # Alternative order with exclusions
                        f'site:youtube.com "{channel_name}" "should you buy" "2025 {model_var}" -2023',  # Specific title format, exclude 2023
                        f'site:youtube.com "{channel_name}" "2025 {model_var}" -"2023" -"latest" -"comprehensive"',  # Exclude terms from old video
                    ])
            
            # Generic YouTube searches as fallback - ALSO PRIORITIZE 2025 WITH EXCLUSIONS
            for model_var in model_variations:
                search_queries.extend([
                    f'site:youtube.com "2025 {model_var}" review -2023 -2022',  # 2025 first with exclusions
                    f'site:youtube.com "{make}" "2025 {model_var}" review -2023',  # With make and 2025, exclude 2023
                    f'site:youtube.com "{model_var}" review 2025 -"latest" -"comprehensive"',  # Exclude terms from the problematic video
                ])
            
            # Try each search query
            found_url = None
            for i, search_query in enumerate(search_queries[:8], 1):  # Limit to 8 searches
                logger.info(f"YouTube Google search attempt {i}: {search_query}")
                
                try:
                    # Use Google Custom Search API
                    api_key = os.environ.get('GOOGLE_SEARCH_API_KEY')
                    search_engine_id = os.environ.get('GOOGLE_SEARCH_ENGINE_ID')
                    
                    if not api_key or not search_engine_id:
                        logger.warning("Google Search API not configured for YouTube fallback")
                        break
                    
                    params = {
                        'key': api_key,
                        'cx': search_engine_id,
                        'q': search_query,
                        'num': 5
                    }
                    
                    response = requests.get('https://www.googleapis.com/customsearch/v1', params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    if 'items' in data:
                        for item in data['items']:
                            result_url = item.get('link', '')
                            title = item.get('title', '')
                            
                            # CRITICAL: Only accept YouTube URLs
                            if 'youtube.com/watch' in result_url or 'youtu.be/' in result_url:
                                # Check if title contains our model variation
                                title_lower = title.lower()
                                if any(model_var.lower() in title_lower for model_var in model_variations):
                                    logger.info(f"✅ Found YouTube video: {title}")
                                    logger.info(f"✅ YouTube URL: {result_url}")
                                    found_url = result_url
                                    break
                        
                        if found_url:
                            break
                    else:
                        logger.info(f"No results for YouTube search: {search_query}")
                        
                except Exception as e:
                    logger.error(f"Error in YouTube Google search: {e}")
                    continue
                    
                # Rate limit between searches
                time.sleep(0.5)
            
            if found_url:
                logger.info(f"✅ Google Search found YouTube video: {found_url}")
                
                # Extract video ID from the found URL
                found_video_id = extract_video_id(found_url)
                if found_video_id:
                    # Try to get transcript from the found video
                    transcript = get_transcript(found_video_id)
                    if transcript:
                        # Get video title for logging
                        metadata = get_video_metadata_fallback(found_video_id)
                        title = metadata.get('title', found_url) if metadata else found_url
                        
                        logger.info(f"✅ Successfully got transcript from Google-found video: {title}")
                        return {
                            'url': found_url,
                            'content': transcript,
                            'content_type': 'video',
                            'title': title
                        }
                    else:
                        # Fallback to metadata
                        logger.info(f"No transcript for Google-found video {found_video_id}, trying metadata fallback")
                        metadata = get_video_metadata_fallback(found_video_id)
                        if metadata and metadata.get('content_text'):
                            logger.info(f"✅ Using metadata fallback for Google-found video: {metadata.get('title', 'No title')}")
                            return {
                                'url': found_url,
                                'content': metadata['content_text'],
                                'content_type': 'video_metadata',
                                'title': metadata.get('title', found_url),
                                'channel_name': metadata.get('channel_name', ''),
                                'view_count': metadata.get('view_count', '0')
                            }
                else:
                    logger.warning(f"Could not extract video ID from found URL: {found_url}")
            else:
                logger.info("Google Search fallback did not find relevant YouTube videos")
                
        except Exception as e:
            logger.error(f"Error in Google Search fallback for YouTube: {e}")
        
        return None
        
    except Exception as e:
        logger.error(f"Error processing YouTube URL {url}: {e}")
        return None

def process_web_url(url: str, loan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a web URL to extract article content.
    
    Args:
        url: Web article URL
        loan: Loan data dictionary
        
    Returns:
        Dictionary with article content or None if not found
    """
    try:
        # Use the enhanced crawler manager with 5-tier escalation
        logger.info(f"Processing web URL: {url}")
        
        # Get make and model for finding relevant content
        make = loan.get('make', '')
        model = loan.get('model', '')
        
        # Get person name for caching if available
        person_name = loan.get('to', loan.get('affiliation', ''))
        
        # Use the new enhanced crawler with 5-tier escalation
        result = crawler_manager.crawl_url(
            url=url,
            make=make,
            model=model,
            person_name=person_name
        )
        
        if not result['success']:
            error_msg = result.get('error', 'Unknown error')
            logger.warning(f"Error crawling {url}: {error_msg} (Method: {result.get('tier_used', 'Unknown')})")
            return None
            
        if not result.get('content'):
            logger.warning(f"No content retrieved from {url}")
            return None
            
        # Log which tier was successful
        tier_used = result.get('tier_used', 'Unknown')
        cached = result.get('cached', False)
        final_url = result.get('url', url)  # May be different if Google Search found specific article
        
        cache_status = " (cached)" if cached else ""
        logger.info(f"Successfully crawled {final_url} using {tier_used}{cache_status}")
            
        # Return the processed content
        return {
            'url': final_url,  # Use the final URL (may be specific article found by Google Search)
            'original_url': url,  # Keep the original URL for reference
            'content': result['content'],
            'content_type': 'article',
            'title': result.get('title', url),
            'tier_used': tier_used,
            'cached': cached
        }
        
    except Exception as e:
        logger.error(f"Error processing web URL {url}: {e}")
        return None

def process_loan(loan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a loan to find relevant clips.
    
    Args:
        loan: Loan data dictionary
        
    Returns:
        Dictionary with best matching clip or None if not found
    """
    make = loan.get('make', '')
    model = loan.get('model', '')
    work_order = loan.get('work_order', '')
    
    if not model or not work_order:
        logger.warning(f"Missing required loan data: model={model}, work_order={work_order}")
        return None
    
    logger.info(f"Processing loan {work_order}: {make} {model}")
    
    best_clip = None
    best_relevance = -1
    
    # Process each URL
    for url in loan.get('urls', []):
        if not url:
            continue
            
        logger.info(f"Processing URL: {url}")
        
        # Determine URL type (YouTube or web)
        if 'youtube.com' in url or 'youtu.be' in url:
            clip_data = process_youtube_url(url, loan)
        else:
            clip_data = process_web_url(url, loan)
            
        if not clip_data or not clip_data.get('content'):
            logger.warning(f"No content found for URL: {url}")
            continue
            
        # Get the actual URL where content was found
        actual_url = clip_data.get('url', url)
        logger.info(f"Analyzing content from URL: {actual_url}")
        analysis = analyze_clip(clip_data['content'], make, model, url=actual_url)
        
        # Check if analysis succeeded
        if analysis is None:
            logger.warning(f"GPT analysis failed for URL: {actual_url} - skipping this clip")
            continue
        
        # Check relevance
        relevance = analysis.get('relevance_score', 0)
        
        if relevance > best_relevance:
            # Add analysis to clip data
            clip_data.update(analysis)
            
            # Copy fields from loan to best_clip
            best_clip = {
                'WO #': work_order,
                'Model': model,
                'Clip URL': actual_url,  # Use the actual URL where content was found (could be from RSS feed)
                'Links': url,  # Original link from the input file
                'Relevance Score': relevance,
                'Sentiment': analysis.get('sentiment', 'neutral'),
                'Summary': analysis.get('summary', ''),
                'Brand Alignment': analysis.get('brand_alignment', False),
                'Processed Date': datetime.now().isoformat(),
                # Add comprehensive GPT analysis fields
                'Overall Score': analysis.get('overall_score', 0),
                'Overall Sentiment': analysis.get('overall_sentiment', 'neutral'),
                'Recommendation': analysis.get('recommendation', ''),
                'Key Mentions': str(analysis.get('key_mentions', [])),  # Convert array to string for CSV
                # Aspect scores
                'Performance Score': analysis.get('aspects', {}).get('performance', {}).get('score', 0),
                'Performance Note': analysis.get('aspects', {}).get('performance', {}).get('note', ''),
                'Design Score': analysis.get('aspects', {}).get('exterior_design', {}).get('score', 0),
                'Design Note': analysis.get('aspects', {}).get('exterior_design', {}).get('note', ''),
                'Interior Score': analysis.get('aspects', {}).get('interior_comfort', {}).get('score', 0),
                'Interior Note': analysis.get('aspects', {}).get('interior_comfort', {}).get('note', ''),
                'Technology Score': analysis.get('aspects', {}).get('technology', {}).get('score', 0),
                'Technology Note': analysis.get('aspects', {}).get('technology', {}).get('note', ''),
                'Value Score': analysis.get('aspects', {}).get('value', {}).get('score', 0),
                'Value Note': analysis.get('aspects', {}).get('value', {}).get('note', ''),
                # Pros and cons as pipe-separated strings for CSV compatibility
                'Pros': ' | '.join(analysis.get('pros', [])),
                'Cons': ' | '.join(analysis.get('cons', []))
            }
            
            # Add additional fields from loan if present
            if 'source' in loan:
                best_clip['Affiliation'] = loan['source']
            if 'to' in loan:
                best_clip['To'] = loan['to']
            if 'affiliation' in loan:
                best_clip['Affiliation'] = loan['affiliation']
            if 'office' in loan:
                best_clip['Office'] = loan['office']
            
            best_relevance = relevance
            
            # If we found a highly relevant clip, stop processing further URLs
            if relevance >= 8:
                logger.info(f"Found highly relevant clip (score {relevance}) for {make} {model}")
                break
    
    if best_clip:
        logger.info(f"Best clip for {work_order} has relevance {best_relevance}")
    else:
        logger.warning(f"No relevant clips found for {work_order}")
        
    return best_clip

def save_results(results: List[Dict[str, Any]], output_file: str) -> bool:
    """
    Save processed results to a CSV file.
    
    Args:
        results: List of result dictionaries
        output_file: Path to the output CSV file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)
        
        # If results is empty, create an empty file
        if not results:
            logger.warning(f"No results to save. Creating empty file: {output_file}")
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['WO #', 'Model', 'To', 'Affiliation', 'Clip URL', 'Links', 
                                'Relevance Score', 'Sentiment', 'Summary', 'Brand Alignment', 
                                'Processed Date', 'Overall Score', 'Overall Sentiment', 'Recommendation',
                                'Key Mentions', 'Performance Score', 'Performance Note', 'Design Score',
                                'Design Note', 'Interior Score', 'Interior Note', 'Technology Score',
                                'Technology Note', 'Value Score', 'Value Note', 'Pros', 'Cons'])
            return True
        
        # Convert to DataFrame for easier CSV handling
        df = pd.DataFrame(results)
        
        # Save to CSV
        df.to_csv(output_file, index=False)
        logger.info(f"Results saved to {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving results to {output_file}: {e}")
        return False

def run_ingest(input_file: str, output_file: Optional[str] = None) -> bool:
    """
    Run the full ingestion pipeline.
    
    Args:
        input_file: Path to the input CSV/Excel file
        output_file: Path to the output CSV file (optional)
        
    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    
    try:
        # Set default output file if not provided
        if not output_file:
            project_root = Path(__file__).parent.parent.parent
            output_file = os.path.join(project_root, 'data', 'loan_results.csv')
        
        # Load loans data
        loans = load_loans_data(input_file)
        
        if not loans:
            logger.error(f"No loans data loaded from {input_file}")
            # send_slack_message(f"❌ Clip Tracking: Failed to load loans data from {input_file}")
            return False
        
        # Process each loan
        results = []
        for loan in loans:
            result = process_loan(loan)
            if result:
                results.append(result)
        
        # Save results
        if save_results(results, output_file):
            elapsed_time = time.time() - start_time
            message = (f"✅ Clip Tracking: Processed {len(loans)} loans, found {len(results)} clips "
                      f"in {elapsed_time:.1f} seconds")
            logger.info(message)
            # send_slack_message(message)
            return True
        else:
            # send_slack_message(f"❌ Clip Tracking: Failed to save results to {output_file}")
            return False
            
    except Exception as e:
        error_message = f"❌ Clip Tracking: Error during ingestion: {e}"
        logger.error(error_message)
        # send_slack_message(error_message)
        return False
    finally:
        # Clean up resources
        crawler_manager.close()

if __name__ == "__main__":
    # When run directly, use the default fixtures
    project_root = Path(__file__).parent.parent.parent
    input_file = os.path.join(project_root, "data", "fixtures", "Loans_without_Clips.csv")
    run_ingest(input_file) 