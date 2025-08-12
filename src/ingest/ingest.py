### DO NOT TOUCH THIS CONTRACT ###
# `process_loan(loan)` MUST keep its current logic:
#  - Four-tier escalation (Google, HTTP, ScrapFly, playwright)
#  - Vehicle-specific GPT prompt with {make} {model}
#  - Returns dict with keys:
#       work_order, media, make_model, status, url, snippet, logs
#
# It currently achieves ~100% recall on our test set.
#
# We only want to speed up **overall throughput** by running
# many of these calls in parallel, WITHOUT changing inside
# `process_loan`.  Acceptable changes:
#  - Async / ThreadPool wrapper
#  - Result aggregation
#  - Caching layer (per-URL, per-YouTube-video) behind an LRU
#  - Graceful fallback to `Status="Not found"` after ladder exhausted
#
# Absolutely NO changes to:
#  * YouTube transcript parser
#  * GPT prompt strings
#  * Escalation tier order
#
# Down-stream code (dashboard) will group the final DataFrame
# by `media` for UX only.  No business logic relies on batching.
### END OF GUARANTEED CONTRACT ###

import os
import csv
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import time
import requests
import asyncio
import logging
import re
import argparse
import dateutil.parser
import io

# Import local modules
from src.utils.logger import setup_logger
# from src.utils.notifications import send_slack_message  # Commented out to prevent hanging
from src.utils.youtube_handler import get_channel_id, get_latest_videos, get_transcript, extract_video_id, get_video_metadata_fallback, scrape_channel_videos_with_scrapfly
from src.utils.escalation import crawling_strategy
from src.utils.enhanced_crawler_manager import EnhancedCrawlerManager
from src.analysis.gpt_analysis import analyze_clip
from src.utils.date_extractor import extract_date_from_html, extract_youtube_upload_date, parse_date_string
from src.utils.tiktok_handler import process_tiktok_video, search_channel_for_vehicle as search_tiktok_channel
from src.utils.instagram_handler import process_instagram_post, search_profile_for_vehicle as search_instagram_profile
from src.utils.enhanced_date_filter import is_content_acceptable

logger = setup_logger(__name__)

def flexible_model_match(video_title: str, model_variation: str) -> bool:
    """
    Check if the model variation matches the video title with flexible matching.
    Uses a threshold-based approach instead of requiring ALL words.
    
    Examples:
    - "kona limited awd" matches "2025 Hyundai Kona Limited" (2/3 words = 67%)
    - "accord hybrid touring" matches "The 2025 Honda Accord Touring Is A Blissful Hybrid Sedan"
    - "cx-50 turbo" matches "The Mazda CX-50 2.5 Turbo Review"
    
    Args:
        video_title: The video title to search in (already lowercased)
        model_variation: The model string to search for (already lowercased)
        
    Returns:
        True if enough words from model_variation appear in video_title
    """
    # First, check for exact model number patterns to prevent false matches (e.g., CX-50 vs CX-5)
    # Extract model number patterns from both strings
    model_number_pattern = r'\b([a-z]+[-\s]?\d+)\b'
    
    # Find all model numbers in the variation (e.g., "cx-50", "es 350", "3 series")
    model_numbers_in_variation = re.findall(model_number_pattern, model_variation)
    
    # If we have model numbers in the variation, check for exact matches
    if model_numbers_in_variation:
        # Find all model numbers in the title
        model_numbers_in_title = re.findall(model_number_pattern, video_title)
        
        # Normalize model numbers by removing spaces/hyphens for comparison
        normalized_variation_models = [re.sub(r'[-\s]+', '', m.lower()) for m in model_numbers_in_variation]
        normalized_title_models = [re.sub(r'[-\s]+', '', m.lower()) for m in model_numbers_in_title]
        
        # Check if ANY model number from variation appears in title
        model_number_found = False
        for var_model in normalized_variation_models:
            if var_model in normalized_title_models:
                model_number_found = True
                break
        
        # If we're looking for a specific model number but it's not in the title, reject
        if not model_number_found:
            # Special check: make sure we're not matching partial model numbers
            # e.g., "cx50" should not match "cx5" in "#cx5"
            for var_model in normalized_variation_models:
                # Check if this model number appears as a substring anywhere
                # but ensure it's not part of a different model number
                for title_model in normalized_title_models:
                    if var_model != title_model and (var_model in title_model or title_model in var_model):
                        # This is a partial match (e.g., "cx5" in "cx50" or vice versa)
                        logger.debug(f"❌ Rejecting partial model match: '{var_model}' vs '{title_model}'")
                        return False
            
            # If no model number match at all, might still match on other criteria
            # but log it for debugging
            logger.debug(f"⚠️ Model number mismatch: looking for {normalized_variation_models} but found {normalized_title_models}")
    
    # Split model variation into words, handling hyphens as word boundaries
    # BUT preserve model numbers as single units
    model_words = []
    remaining_text = model_variation.strip()
    
    # First extract model numbers as complete units
    for model_num in model_numbers_in_variation:
        remaining_text = remaining_text.replace(model_num, ' ', 1)
        # Add the model number as a single word (normalized)
        model_words.append(re.sub(r'[-\s]+', '', model_num.lower()))
    
    # Then split the remaining text into words
    other_words = re.split(r'[-\s]+', remaining_text.strip())
    model_words.extend([word for word in other_words if word])
    
    if not model_words:
        return False
    
    # Count how many model words appear in the title
    matches = 0
    core_matches = 0  # Track matches of important words
    
    # Define less important words that shouldn't be strictly required
    optional_words = {'awd', '4wd', 'fwd', 'rwd', '2wd', 'drive', 'wheel', 'all'}
    
    for word in model_words:
        # For model numbers, check exact normalized match
        if re.match(r'[a-z]+\d+', word):
            # This is a model number - check for exact match in normalized title models
            if word in normalized_title_models:
                matches += 1
                core_matches += 1
        else:
            # Regular word - check if it appears in the title
            if word in video_title:
                matches += 1
                if word not in optional_words:
                    core_matches += 1
    
    # Calculate match percentage
    match_percentage = matches / len(model_words)
    
    # More flexible matching rules:
    # 1. If we have 80% or more matches, it's a match
    if match_percentage >= 0.8:
        return True
    
    # 2. If we have at least 2 core (non-optional) word matches, it's a match
    if core_matches >= 2:
        return True
    
    # 3. If we have 60% or more matches AND at least 1 core match, it's a match
    if match_percentage >= 0.6 and core_matches >= 1:
        return True
    
    # 4. Special case: if model variation is just 2 words and we match both core words
    core_words = [w for w in model_words if w not in optional_words]
    if len(core_words) <= 2 and all(word in video_title for word in core_words):
        return True
    
    return False

# Initialize the enhanced crawler manager (it will be reused for all URLs)
crawler_manager = EnhancedCrawlerManager()

# Global list to track rejected records for transparency dashboard
REJECTED_RECORDS = []

def clear_rejected_records():
    """Clear the global rejected records list (called at start of each processing run)"""
    global REJECTED_RECORDS
    REJECTED_RECORDS = []

def add_rejected_record(loan: Dict[str, Any], rejection_reason: str, url_details: str = ""):
    """
    Add a rejected record to the global list for transparency tracking.
    
    Args:
        loan: Original loan data
        rejection_reason: Why the loan was rejected
        url_details: Details about URLs processed (optional)
    """
    global REJECTED_RECORDS
    
    # Use exact same structure as manual rejection in dashboard
    rejected_record = {
        'WO #': loan.get('work_order', ''),
        'Activity_ID': loan.get('activity_id', ''),
        'Make': loan.get('make', ''),
        'Model': loan.get('model', ''),
        'To': loan.get('to', ''),
        'Affiliation': loan.get('affiliation', ''),
        'Office': loan.get('office', ''),
        'Links': loan.get('links', ''),
        'URLs_Processed': len(loan.get('links', '').split(';')) if loan.get('links') else 0,
        'URLs_Successful': 0,  # If rejected, none were successful
        'Rejection_Reason': rejection_reason,
        'URL_Details': url_details,
        'Processed_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Loan_Start_Date': loan.get('start_date', '')
    }
    
    REJECTED_RECORDS.append(rejected_record)
    logger.info(f"📝 Added rejected record: {loan.get('work_order')} - {rejection_reason}")

def parse_start_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string from the Start Date column.
    Handles various date formats commonly found in spreadsheets.
    
    Args:
        date_str: Date string from the spreadsheet
        
    Returns:
        datetime object or None if parsing fails
    """
    if not date_str or pd.isna(date_str):
        return None
    
    try:
        # Convert to string if it's not already
        date_str = str(date_str).strip()
        
        # Handle empty strings
        if not date_str:
            return None
        
        # Use dateutil parser which handles many formats automatically
        parsed_date = dateutil.parser.parse(date_str)
        return parsed_date
    
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        return None

# Legacy function - kept for backward compatibility but now uses enhanced filter
def is_content_within_date_range(content_date: Optional[datetime], 
                                start_date: Optional[datetime], 
                                days_forward: int = 90,
                                content_type: str = "unknown",
                                content_url: str = None) -> bool:
    """
    Legacy wrapper around the enhanced date filter.
    Now uses platform-aware filtering.
    """
    return is_content_acceptable(
        content_date=content_date,
        loan_start_date=start_date,
        content_type=content_type,
        content_url=content_url
    )

# NOTE: Make guessing functions removed - now using direct Make column from CSV

def load_loans_data_from_url(url: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Load and parse the loans data from a URL.
    This is specifically for the new "media_loans_without_clips" report.
    
    Args:
        url: URL to the loans CSV file.
        limit: Optional integer to limit the number of records returned.
        
    Returns:
        List of dictionaries containing loan information, mapped to the application's expected keys.
    """
    logger.info(f"Fetching loans data from URL: {url}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    # Define headers manually for this specific report, as it has no header row
    headers = [
        "ActivityID", "Person_ID", "Make", "Model", "WO #", "Office", "To", 
        "Affiliation", "Start Date", "Stop Date", "Model Short Name", "Links"
    ]
    
    # Use StringIO to treat the string content as a file
    csv_content = response.content.decode('utf-8')
    df = pd.read_csv(io.StringIO(csv_content), header=None, names=headers, on_bad_lines='warn')
    
    # Clean up column names (just in case)
    df.columns = [col.strip() for col in df.columns]
    logger.info(f"Columns assigned: {df.columns.tolist()}")
    
    # Apply limit if provided
    if limit is not None and limit > 0:
        logger.info(f"Limiting records to the first {limit}")
        df = df.head(limit)
        
    # Convert to a list of dictionaries to process each record
    records = df.to_dict('records')
    logger.info(f"Loaded {len(records)} loans from URL.")
    
    # Map the columns to the internal variable names the rest of the script expects
    processed_loans = []
    for record in records:
        # Convert to dictionary and handle potential NaN values
        loan_dict = {k: v if pd.notna(v) else '' for k, v in record.items()}
        
        # Parse URLs from the Links field - handle comma-separated URLs properly
        urls = []
        links_text = loan_dict.get('Links', '')
        if links_text:
            # Split by comma and clean up each URL
            url_parts = [url.strip() for url in str(links_text).split(',')]
            for url in url_parts:
                # Remove quotes if present
                url = url.strip('"\'')
                # Skip empty URLs and internal system URLs
                if url and not url.startswith('https://fms.driveshop.com/'):
                    urls.append(url)
        
        # Log URL parsing for debugging
        logger.info(f"Loan {loan_dict.get('WO #')}: Parsed {len(urls)} URLs from '{links_text[:100]}...'")
        
        processed_loan = {
            'work_order': loan_dict.get('WO #'),
            'model': loan_dict.get('Model'),
            'to': loan_dict.get('To'),
            'affiliation': loan_dict.get('Affiliation'),
            'urls': urls,  # Use the properly parsed URLs
            'start_date': None,  # Initialize as None, then parse below
            'make': loan_dict.get('Make'),
            # Add the new fields
            'activity_id': loan_dict.get('ActivityID'),
            'person_id': loan_dict.get('Person_ID'),
            'office': loan_dict.get('Office')
        }
        
        # Parse start date properly (same logic as file upload function)
        start_date_str = loan_dict.get('Start Date')
        if start_date_str and pd.notna(start_date_str):
            parsed_date = parse_start_date(start_date_str)
            if parsed_date:
                processed_loan['start_date'] = parsed_date
                logger.debug(f"Parsed start date for {processed_loan['work_order']}: {parsed_date.strftime('%Y-%m-%d')}")
            else:
                logger.warning(f"Could not parse start date for {processed_loan['work_order']}: {start_date_str}")
        
        processed_loans.append(processed_loan)

    logger.info(f"Total loans processed: {len(processed_loans)}")
    total_urls = sum(len(loan['urls']) for loan in processed_loans)
    logger.info(f"Total URLs to process: {total_urls}")
    
    return processed_loans

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
        
        # Check for Make column (REQUIRED!)
        if 'Make' not in df.columns:
            raise ValueError(f"Make column is required. Available columns: {df.columns.tolist()}")
        required_columns.append('Make')

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
            
                        # Get Make directly from CSV column (SIMPLIFIED!)
            loan['make'] = row['Make'] if pd.notna(row['Make']) else ''

            # Get Model from model columns
            model_value = ''
            model_short_value = ''
            
            if model_column:
                model_value = row[model_column] if pd.notna(row[model_column]) else ''
                loan['model'] = model_value
            else:
                loan['model'] = ''

            # ENHANCEMENT: Also get Model Short Name (Column M) for search variations
            if 'Model Short Name' in df.columns:
                model_short_value = row['Model Short Name'] if pd.notna(row['Model Short Name']) else ''

            # Log the vehicle for verification
            if loan['make'] and loan['model']:
                logger.info(f"Vehicle: {loan['make']} {loan['model']} (from Make column + Model: '{model_value}', Short: '{model_short_value}')")
            
            # ENHANCEMENT: Build hierarchical model name for smarter searching
            # The goal is to create the most specific model name possible, which our
            # hierarchical search will then intelligently strip back if needed
            
            # Start with the base model (short name is usually cleaner)
            base_model = model_short_value if model_short_value else model_value
            
            # FIXED: Use SHORT model for initial search (broad to specific approach)
            # This allows finding articles that use just "Tacoma" in the title
            # even when we're looking for "Tacoma TRD Pro Double Cab"
            if model_short_value:
                # We have a short model - use it for searching
                search_model = model_short_value
                logger.info(f"Using SHORT model for search: '{search_model}' (full: '{model_value}')")
            else:
                # No short model - use whatever we have
                search_model = model_value
                logger.info(f"No short model available, using full: '{search_model}'")
            
            # Clean up the search model
            search_model = search_model.strip()
            
            # Store all variations for different uses
            loan['model'] = base_model  # Keep this for compatibility
            loan['model_full'] = model_value if model_value else base_model  # Original full from CSV
            loan['model_short'] = model_short_value  # Store short model explicitly
            loan['search_model'] = search_model  # This is what we'll use for searching (SHORT first!)
            
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
            
            # Add Start Date for date filtering
            loan['start_date'] = None
            if 'Start Date' in df.columns and pd.notna(row['Start Date']):
                parsed_date = parse_start_date(row['Start Date'])
                if parsed_date:
                    loan['start_date'] = parsed_date
                    logger.debug(f"Parsed start date for {loan['work_order']}: {parsed_date.strftime('%Y-%m-%d')}")
                else:
                    logger.warning(f"Could not parse start date for {loan['work_order']}: {row['Start Date']}")
            
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

def process_youtube_url(url: str, loan: Dict[str, Any], cancel_check: Optional[callable] = None) -> Optional[Dict[str, Any]]:
    """
    Process a YouTube URL to extract video content with date filtering.
    Implements graceful degradation: 90 days -> 180 days if nothing found.
    
    Args:
        url: YouTube URL (channel or video)
        loan: Loan data dictionary
        
    Returns:
        Dictionary with video content or None if not found
    """
    try:
        # Early cancellation
        if cancel_check and cancel_check():
            raise Exception("Job cancelled by user")
        # Import the new fallback function
        from src.utils.youtube_handler import get_video_metadata_fallback
        
        # First check if it's a direct video URL
        video_id = extract_video_id(url)
        
        if video_id:
            if cancel_check and cancel_check():
                raise Exception("Job cancelled by user")
            # Direct video URL - get metadata first to check upload date
            logger.info(f"Processing YouTube video: {url}")
            metadata = get_video_metadata_fallback(video_id)
            
            # Check video upload date against loan start date
            start_date = loan.get('start_date')
            video_date = extract_youtube_upload_date(metadata) if metadata else None
            
            # Apply date filtering with graceful degradation (forward from start date)
            is_within_range = False
            days_attempted = [90, 180]
            
            for days_forward in days_attempted:
                if is_content_within_date_range(video_date, start_date, days_forward, content_type="youtube", content_url=url):
                    if video_date and start_date:
                        if video_date >= start_date:
                            days_diff = (video_date - start_date).days
                            logger.info(f"✅ Video is within {days_forward}-day range: uploaded {days_diff} days after start date")
                        else:
                            days_diff = (start_date - video_date).days
                            logger.warning(f"⚠️ Video uploaded {days_diff} days BEFORE start date, but allowing due to fallback")
                    else:
                        logger.info(f"✅ Video accepted (date filtering skipped - missing date info)")
                    is_within_range = True
                    break
            
            if not is_within_range and video_date and start_date:
                if video_date < start_date:
                    days_diff = (start_date - video_date).days
                    # Only reject videos that are extremely old (more than 365 days before start)
                    if days_diff > 365:
                        logger.warning(f"❌ Video too old: uploaded {days_diff} days BEFORE start date (videos should be after loan placement)")
                        return None
                    else:
                        logger.info(f"⚠️ Allowing slightly old video: uploaded {days_diff} days before start date")
                else:
                    days_diff = (video_date - start_date).days
                    logger.warning(f"❌ Video too far in future: uploaded {days_diff} days after start date (max: 180 days)")
                    return None
            
            # If date is acceptable, proceed with content extraction
            if cancel_check and cancel_check():
                raise Exception("Job cancelled by user")
            transcript = get_transcript(video_id, video_url=url)
            
            if transcript:
                title = metadata.get('title', f"YouTube Video {video_id}") if metadata else f"YouTube Video {video_id}"
                
                return {
                    'url': url,
                    'content': transcript,
                    'content_type': 'video',
                    'title': title,
                    'published_date': video_date
                }
            else:
                logger.info(f"No transcript available for video {video_id}, trying metadata fallback")
                # Fallback to video metadata (title + description)
                if metadata and metadata.get('content_text'):
                    logger.info(f"Using video metadata fallback for {video_id}: {metadata.get('title', 'No title')}")
                    return {
                        'url': url,
                        'content': metadata['content_text'],
                        'content_type': 'video_metadata',
                        'title': metadata.get('title', f"YouTube Video {video_id}"),
                        'channel_name': metadata.get('channel_name', ''),
                        'view_count': metadata.get('view_count', '0'),
                        'published_date': video_date
                    }
                else:
                    logger.warning(f"No content available for video: {url}")
                    return None
        
        # If not a direct video, try as a channel
        if cancel_check and cancel_check():
            raise Exception("Job cancelled by user")
        channel_id = get_channel_id(url)
        
        if not channel_id:
            logger.warning(f"Could not resolve YouTube channel ID from: {url}")
            # Don't return None here - let it fall through to try ScrapFly
            # The ScrapFly fallback below will handle channel URLs without channel IDs
        
        # Get latest videos from channel (only if we have a channel_id)
        videos = []
        if channel_id:
            logger.info(f"Fetching latest videos for channel: {channel_id}")
            if cancel_check and cancel_check():
                raise Exception("Job cancelled by user")
            videos = get_latest_videos(channel_id, max_videos=25)
            
            if not videos:
                logger.warning(f"No videos found for channel: {channel_id}")
                # Don't return None - let it fall through to ScrapFly
        else:
            logger.info("No channel ID available - will try ScrapFly directly")
        
        if videos:
            logger.info(f"Found {len(videos)} videos in channel {channel_id}")
            
            # Debug: Show all video titles and dates
            logger.info("Available videos in channel:")
            for i, video in enumerate(videos):
                logger.info(f"  {i+1}. {video.get('title', 'No title')} (Published: {video.get('published', 'Unknown')})")
        
        # Try to find a relevant video by checking titles
        make = loan.get('make', '').lower()
        model = loan.get('model', '').lower()
        model_full = loan.get('model_full', model).lower()  # Get full model for enhanced matching
        
        # ENHANCEMENT: Create flexible model variations including both short and full names
        model_variations = [
            model,  # Original: "cx-50"
            model_full,  # Full: "mazda cx-50"
        ]
        
        # Handle hyphen/space variations (CX-50 vs CX 50)
        if '-' in model:
            model_variations.append(model.replace('-', ' '))  # "cx-50" -> "cx 50"
            model_variations.append(model.replace('-', ''))   # "cx-50" -> "cx50"
        if ' ' in model:
            model_variations.append(model.replace(' ', '-'))  # "cx 50" -> "cx-50"
            model_variations.append(model.replace(' ', ''))   # "cx 50" -> "cx50"
        
        # Handle number variations (add/remove spaces before numbers)
        import re
        # Add space before numbers: "mazda3" -> "mazda 3"
        model_with_space = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', model)
        if model_with_space != model:
            model_variations.append(model_with_space)
        
        # Remove spaces before numbers: "mazda 3" -> "mazda3"
        model_no_space = re.sub(r'([a-zA-Z])\s+(\d)', r'\1\2', model)
        if model_no_space != model:
            model_variations.append(model_no_space)
        
        # Add make + model combinations for better matching
        if make and model_full != f"{make} {model}":
            model_variations.append(f"{make} {model}")  # "mazda cx-50"
            
            # Also add variations with make for hyphen/space handling
            if '-' in model:
                model_variations.append(f"{make} {model.replace('-', ' ')}")  # "mazda cx 50"
            if ' ' in model:
                model_variations.append(f"{make} {model.replace(' ', '-')}")  # "mazda cx-50"
        
        # Remove duplicates and empty strings
        model_variations = list(set([v.strip() for v in model_variations if v.strip()]))
        
        logger.info(f"Looking for videos with make='{make}' and model variations: {model_variations}")
        
        # Apply date filtering with graceful degradation (forward from start date)
        start_date = loan.get('start_date')
        days_attempted = [90, 180]  # Graceful degradation: 90 days forward, then 180 days forward
        
        for days_forward in days_attempted:
            if cancel_check and cancel_check():
                raise Exception("Job cancelled by user")
            logger.info(f"Looking for YouTube videos within {days_forward} days forward of start date")
            
            for video in videos:
                if cancel_check and cancel_check():
                    raise Exception("Job cancelled by user")
                video_title = video.get('title', '').lower()
                logger.info(f"Checking video: {video['title']}")
                
                # Extract video upload date
                video_date = None
                logger.info(f"DEBUG: Video data keys: {list(video.keys())}")
                if 'published' in video:
                    published_str = str(video['published'])
                    logger.info(f"DEBUG: Found published field: {published_str}")
                    video_date = parse_date_string(published_str)
                    if video_date:
                        logger.info(f"DEBUG: ✅ Parsed date successfully: {video_date}")
                    else:
                        logger.warning(f"DEBUG: ❌ parse_date_string returned None for: {published_str}")
                else:
                    logger.warning(f"DEBUG: ❌ No 'published' field in video data for: {video.get('title', 'Unknown')}")
                
                # Check if video is within acceptable date range
                if not is_content_within_date_range(video_date, start_date, days_forward, content_type="youtube", content_url=video.get('url')):
                    if video_date and start_date:
                        if video_date < start_date:
                            days_diff = (start_date - video_date).days
                            logger.info(f"⏭️ Skipping video (too old): {days_diff} days BEFORE start date (limit: {days_forward} days forward)")
                        else:
                            days_diff = (video_date - start_date).days
                            logger.info(f"⏭️ Skipping video (too far future): {days_diff} days after start date (limit: {days_forward})")
                    continue
                
                # Check if title mentions the make and any model variation
                if make in video_title:
                    for model_var in model_variations:
                        if flexible_model_match(video_title, model_var):
                            if video_date and start_date:
                                days_diff = (video_date - start_date).days
                                logger.info(f"✅ Found relevant video within date range ('{model_var}', {days_diff} days after start): {video['title']}")
                            else:
                                logger.info(f"✅ Found relevant video by title match ('{model_var}'): {video['title']}")
                            
                            video_id = video['video_id']
                            
                            # Always fetch metadata to get the date from the video page
                            if cancel_check and cancel_check():
                                raise Exception("Job cancelled by user")
                            metadata = get_video_metadata_fallback(video_id, known_title=video['title'])
                            
                            # Extract date from metadata if we don't have one from RSS
                            if not video_date and metadata:
                                video_date = metadata.get('upload_date') or metadata.get('published_date')
                                if video_date and isinstance(video_date, str):
                                    video_date = parse_date_string(video_date)
                                if video_date:
                                    logger.info(f"📅 Extracted date from video metadata: {video_date}")
                            
                            if cancel_check and cancel_check():
                                raise Exception("Job cancelled by user")
                            transcript = get_transcript(video_id, video_url=video['url'])
                            
                            if transcript:
                                result_dict = {
                                    'url': video['url'],
                                    'content': transcript,
                                    'content_type': 'video',
                                    'title': video['title'],
                                    'published_date': video_date
                                }
                                logger.info(f"📅 Returning YouTube result with published_date: {video_date}")
                                return result_dict
                            else:
                                # Fallback to metadata if no transcript
                                logger.info(f"No transcript for {video_id}, trying metadata fallback")
                                # Re-fetch metadata only if we didn't already get it
                                if not metadata:
                                    metadata = get_video_metadata_fallback(video_id)
                                if metadata and metadata.get('content_text'):
                                    return {
                                        'url': video['url'],
                                        'content': metadata['content_text'],
                                        'content_type': 'video_metadata',
                                        'title': metadata.get('title', video['title']),
                                        'channel_name': metadata.get('channel_name', ''),
                                        'view_count': metadata.get('view_count', '0'),
                                        'published_date': video_date
                                    }
            
            # If we found something in this time window, stop looking
            if days_forward == 90:
                logger.info(f"No relevant videos found in {days_forward} days forward, trying {days_attempted[1]} days...")
            else:
                logger.info(f"No relevant videos found in {days_forward} days forward either")
        
        if channel_id:
            logger.info(f"No relevant videos found for {make} {model} in channel {channel_id}")
        else:
            logger.info(f"No channel ID available for URL: {url}")
        
        # Try ScrapFly channel search as fallback when RSS feed fails OR when we don't have a channel ID
        logger.info(f"🔄 Falling back to ScrapFly channel search for {make} {model}")
        
        try:
            # Use ScrapFly to search the full channel content with date filtering
            start_date = loan.get('start_date')
            channel_videos = scrape_channel_videos_with_scrapfly(url, make, model, start_date, 90)
            
            if channel_videos:
                logger.info(f"✅ ScrapFly found {len(channel_videos)} relevant videos in channel")
                
                # Process ALL relevant videos and collect successful extractions
                successful_videos = []
                
                for i, video_info in enumerate(channel_videos):
                    video_id = video_info.get('video_id')
                    if not video_id:
                        continue
                        
                    logger.info(f"Processing video {i+1}/{len(channel_videos)}: {video_info['title']}")
                    
                    # Try metadata fallback first since transcript fetching is consistently failing
                    metadata = get_video_metadata_fallback(video_id, known_title=video_info['title'])
                    if metadata and metadata.get('content_text'):
                        logger.info(f"✅ ScrapFly + metadata success: {video_info['title']}")
                        # Get published date from various possible sources
                        # Priority: 1) RSS feed date, 2) metadata extracted date, 3) other sources
                        published_date = video_info.get('published') or video_info.get('published_date') or metadata.get('upload_date')
                        
                        # If we have a date from RSS/ScrapFly, parse it if needed
                        if published_date and isinstance(published_date, str):
                            parsed_date = parse_date_string(published_date)
                            if parsed_date:
                                published_date = parsed_date
                        
                        if published_date:
                            logger.info(f"📅 Using published date for clip: {published_date}")
                        else:
                            logger.warning(f"⚠️ No published date found for video: {video_info['title']}")
                        
                        video_result = {
                            'url': video_info['url'],
                            'content': metadata['content_text'],
                            'content_type': 'video_metadata',
                            'title': metadata.get('title', video_info['title']),
                            'channel_name': metadata.get('channel_name', ''),
                            'view_count': metadata.get('view_count', '0'),
                            'published_date': published_date
                        }
                        successful_videos.append(video_result)
                        continue
                    
                    # Only try transcript as fallback if metadata failed
                    if cancel_check and cancel_check():
                        raise Exception("Job cancelled by user")
                    transcript = get_transcript(video_id, video_url=video_info['url'])
                    if transcript:
                        logger.info(f"✅ ScrapFly + transcript success: {video_info['title']}")
                        video_result = {
                            'url': video_info['url'],
                            'content': transcript,
                            'content_type': 'video',
                            'title': video_info['title'],
                            'published_date': video_info.get('published') or video_info.get('published_date')
                        }
                        successful_videos.append(video_result)
                
                # Return the best match based on title relevance
                if successful_videos:
                    logger.info(f"Successfully processed {len(successful_videos)} out of {len(channel_videos)} videos")
                    
                    # Score each video based on model match in title
                    from src.utils.model_variations import generate_model_variations
                    model_variations = generate_model_variations(make, model)
                    
                    best_video = None
                    best_score = -1
                    
                    for video in successful_videos:
                        title_lower = video['title'].lower()
                        score = 0
                        
                        # Check for exact model match first (highest priority)
                        if model.lower() in title_lower:
                            score = 100
                        else:
                            # Check model variations
                            for variation in model_variations:
                                if variation in title_lower:
                                    # Longer variations get higher scores (more specific)
                                    score = max(score, len(variation))
                        
                        logger.info(f"Video '{video['title']}' scored: {score}")
                        
                        if score > best_score:
                            best_score = score
                            best_video = video
                    
                    if best_video:
                        logger.info(f"🎯 Selected best matching video with score {best_score}: {best_video['title']}")
                        return best_video
                    else:
                        # If no good match found, return the first one
                        logger.info(f"No high-scoring match found, returning first video: {successful_videos[0]['title']}")
                        return successful_videos[0]
            else:
                logger.info(f"ScrapFly found no relevant videos for {make} {model} in channel")
                
        except Exception as e:
            logger.warning(f"ScrapFly channel search failed: {e}")
        
        # Only return None if both RSS and ScrapFly failed
        logger.info(f"❌ No relevant videos found for {make} {model} in the specified channel {channel_id}")
        logger.info(f"🔒 Staying within specified channel - not searching other YouTube channels")
        
        return None
        
    except Exception as e:
        logger.error(f"Error processing YouTube URL {url}: {e}")
        return None

def process_web_url(url: str, loan: Dict[str, Any], cancel_check: Optional[callable] = None) -> Optional[Dict[str, Any]]:
    """
    Process a web URL to extract article content with date filtering.
    Implements graceful degradation: 90 days -> 180 days if nothing found.
    
    Args:
        url: Web article URL
        loan: Loan data dictionary
        
    Returns:
        Dictionary with article content or None if not found
    """
    try:
        if cancel_check and cancel_check():
            raise Exception("Job cancelled by user")
        # Redirect MotorTrend automobilemag URLs to car-reviews
        if 'motortrend.com/automobilemag' in url:
            original_url = url
            url = url.replace('/automobilemag', '/car-reviews')
            logger.info(f"🔄 Redirecting MotorTrend URL: {original_url} -> {url}")
            
        # Redirect Tightwad Garage to blog section where articles are located
        if 'tightwadgarage.com' in url and '/blog' not in url:
            original_url = url
            # Ensure URL ends with /blog
            if url.endswith('/'):
                url = url + 'blog'
            else:
                url = url + '/blog'
            logger.info(f"🔄 Redirecting Tightwad Garage URL: {original_url} -> {url}")
        
        # Get make and model for finding relevant content
        make = loan.get('make', '')
        model = loan.get('model', '')
        search_model = loan.get('search_model', model)  # Use hierarchical search model
        
        logger.info(f"Using hierarchical search model: '{search_model}' (base: '{model}', make: '{make}')")
        
        # Get person name for caching if available
        person_name = loan.get('to', loan.get('affiliation', ''))
        
        # ENABLED DATE FILTERING: Check if article was published after loan start date
        # Articles published BEFORE loan start date should be rejected
        logger.info(f"🔒 Date filtering ENABLED - checking article publish date vs loan start date")
        
        # Get person name for caching if available
        start_date = loan.get('start_date')
        
        # Use the new enhanced crawler with 5-tier escalation and hierarchical search
        if cancel_check and cancel_check():
            raise Exception("Job cancelled by user")
        result = crawler_manager.crawl_url(
            url=url,
            make=make,
            model=search_model,  # Use the hierarchical search model
            person_name=person_name
        )
        
        if not result['success']:
            error_msg = result.get('error', 'Unknown error')
            logger.warning(f"Error crawling {url}: {error_msg} (Method: {result.get('tier_used', 'Unknown')})")
            return None
            
        if not result.get('content'):
            logger.warning(f"No content retrieved from {url}")
            return None
        
        # Extract publication date for both logging and saving to results
        if cancel_check and cancel_check():
            raise Exception("Job cancelled by user")
        html_content = result.get('content', '')
        final_url = result.get('url', url)
        published_date = None
        
        # Try to extract the publication date from the content
        if html_content:
            published_date = extract_date_from_html(html_content, final_url)
            
        # CRITICAL: Check if article was published BEFORE loan start date
        if published_date and start_date:
            # Safety check: ensure start_date is a datetime object
            if isinstance(start_date, str):
                parsed_start_date = parse_start_date(start_date)
                if parsed_start_date:
                    start_date = parsed_start_date
                else:
                    logger.warning(f"Could not parse start_date string: {start_date}")
                    start_date = None
            
            if start_date and isinstance(start_date, datetime):
                # SIMPLE RULE: Article date MUST be >= loan start date
                if published_date < start_date:
                    days_before = (start_date - published_date).days
                    logger.warning(f"📅 ❌ REJECTED: Article from {published_date.strftime('%Y-%m-%d')} is {days_before} days BEFORE loan start {start_date.strftime('%Y-%m-%d')}")
                    logger.warning(f"❌ ABSOLUTE RULE: No article before loan start date can be valid")
                    return None
                else:
                    days_after = (published_date - start_date).days
                    logger.info(f"📅 ✅ VALID: Article from {published_date.strftime('%Y-%m-%d')} is {days_after} days after loan start")
            else:
                logger.info(f"📅 Content published: {published_date.strftime('%Y-%m-%d')} (start date unavailable for comparison)")
        elif published_date:
            logger.info(f"📅 Content published: {published_date.strftime('%Y-%m-%d')} (no start date to compare)")
        else:
            logger.warning(f"📅 ⚠️ Content found: publication date could not be determined")
            # When we have a loan start date but can't extract article date = Mark for manual review
            if start_date:
                logger.warning(f"⚠️ WARNING: Cannot verify article date vs loan start date {start_date.strftime('%Y-%m-%d') if isinstance(start_date, datetime) else start_date}")
                logger.warning(f"📝 MANUAL REVIEW NEEDED: Publication date missing - reviewer must verify article is after loan placement")
                # Continue processing but flag for manual date entry
                published_date = None  # Will need manual entry in dashboard
            else:
                logger.info(f"📅 Allowing content (no start date provided for validation)")
            
        logger.info(f"✅ Successfully crawled content - date validation passed")
            
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
            'cached': cached,
            'published_date': published_date,  # Add the extracted publication date
            'date_missing': published_date is None,  # Flag for missing date
            'needs_manual_date': published_date is None and start_date is not None,  # Needs manual date entry
            # Add attribution information for UI display
            'attribution_strength': result.get('attribution_strength', 'unknown'),
            'byline_author': result.get('actual_byline')  # Map actual_byline to byline_author for database
        }
        
    except Exception as e:
        logger.error(f"Error processing web URL {url}: {e}")
        return None

def process_tiktok_url(url: str, loan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a TikTok URL to extract video content.
    
    Args:
        url: TikTok video or channel URL
        loan: Loan data dictionary
        
    Returns:
        Dictionary with clip data or None if not found
    """
    make = loan.get('make', '')
    model = loan.get('model', '')
    start_date = loan.get('start_date')
    
    logger.info(f"Processing TikTok URL: {url}")
    
    # Check if it's a video URL or channel URL
    if '/video/' in url or 'vm.tiktok.com' in url:
        # Direct video URL
        video_data = process_tiktok_video(url)
        
        if video_data:
            # Check relevance using the scoring system
            from src.utils.tiktok_content_scorer import score_tiktok_relevance
            relevance_score = score_tiktok_relevance(video_data, make, model)
            
            if relevance_score['total_score'] >= 35:
                return {
                    'url': url,
                    'clip_url': url,
                    'content': video_data.get('transcript') or video_data.get('description', ''),
                    'extracted_content': video_data.get('transcript') or video_data.get('description', ''),
                    'content_type': 'tiktok_video',
                    'creator': video_data.get('creator', ''),
                    'creator_handle': video_data.get('creator_handle', ''),
                    'publish_date': video_data.get('published_date'),
                    'duration': video_data.get('duration', 0),
                    'views': video_data.get('views', 0),
                    'relevance_score': relevance_score['total_score'],
                    'sentiment_content': video_data.get('transcript') or video_data.get('description', ''),
                    'vehicle_make': make,
                    'vehicle_model': model
                }
    else:
        # Channel URL - search for vehicle mentions
        video_data = search_tiktok_channel(url, make, model, start_date, days_forward=90)
        
        if video_data:
            return {
                'url': video_data.get('url'),
                'clip_url': video_data.get('url'),
                'content': video_data.get('transcript') or video_data.get('description', ''),
                'extracted_content': video_data.get('transcript') or video_data.get('description', ''),
                'content_type': 'tiktok_video',
                'creator': video_data.get('creator', ''),
                'creator_handle': video_data.get('creator_handle', ''),
                'publish_date': video_data.get('published_date'),
                'duration': video_data.get('duration', 0),
                'views': video_data.get('views', 0),
                'relevance_score': video_data.get('relevance_score', {}).get('total_score', 0),
                'sentiment_content': video_data.get('transcript') or video_data.get('description', ''),
                'vehicle_make': make,
                'vehicle_model': model
            }
    
    return None

def process_instagram_url(url: str, loan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process an Instagram URL to extract post/reel content.
    
    Args:
        url: Instagram post/reel or profile URL
        loan: Loan data dictionary
        
    Returns:
        Dictionary with clip data or None if not found
    """
    make = loan.get('make', '')
    model = loan.get('model', '')
    start_date = loan.get('start_date')
    
    logger.info(f"Processing Instagram URL: {url}")
    
    # Check if it's a post/reel URL or profile URL
    if '/reel/' in url or '/p/' in url:
        # Direct post/reel URL
        post_data = process_instagram_post(url)
        
        if post_data:
            # Check relevance using the scoring system
            from src.utils.tiktok_content_scorer import score_tiktok_relevance
            relevance_score = score_tiktok_relevance(post_data, make, model)
            
            if relevance_score['total_score'] >= 35:
                return {
                    'url': url,
                    'clip_url': url,
                    'content': post_data.get('transcript') or post_data.get('caption', ''),
                    'extracted_content': post_data.get('transcript') or post_data.get('caption', ''),
                    'content_type': 'instagram_reel' if post_data.get('is_video') else 'instagram_post',
                    'creator': post_data.get('creator', ''),
                    'creator_handle': post_data.get('creator_handle', ''),
                    'publish_date': post_data.get('published_date'),
                    'duration': post_data.get('duration', 0),
                    'views': post_data.get('views', 0),
                    'relevance_score': relevance_score['total_score'],
                    'sentiment_content': post_data.get('transcript') or post_data.get('caption', ''),
                    'vehicle_make': make,
                    'vehicle_model': model
                }
    else:
        # Profile URL - search for vehicle mentions
        post_data = search_instagram_profile(url, make, model, start_date, days_forward=90)
        
        if post_data:
            return {
                'url': post_data.get('url'),
                'clip_url': post_data.get('url'),
                'content': post_data.get('transcript') or post_data.get('caption', ''),
                'extracted_content': post_data.get('transcript') or post_data.get('caption', ''),
                'content_type': 'instagram_reel' if post_data.get('is_video') else 'instagram_post',
                'creator': post_data.get('creator', ''),
                'creator_handle': post_data.get('creator_handle', ''),
                'publish_date': post_data.get('published_date'),
                'duration': post_data.get('duration', 0),
                'views': post_data.get('views', 0),
                'relevance_score': post_data.get('relevance_score', {}).get('total_score', 0),
                'sentiment_content': post_data.get('transcript') or post_data.get('caption', ''),
                'vehicle_make': make,
                'vehicle_model': model
            }
    
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
    
    # NEW: Track all URL processing attempts for transparency
    url_tracking = []
    
    # Process each URL
    for url in loan.get('urls', []):
        if not url:
            continue
            
        logger.info(f"Processing URL: {url}")
        
        # NEW: Initialize tracking for this URL attempt
        url_attempt = {
            'original_url': url,
            'success': False,
            'reason': 'Unknown',
            'actual_url': url,
            'relevance_score': 0,
            'content_type': 'unknown',
            'processing_method': 'unknown'
        }
        
        # Determine URL type and process accordingly
        if 'youtube.com' in url or 'youtu.be' in url:
            url_attempt['content_type'] = 'youtube'
            url_attempt['processing_method'] = 'YouTube API'
            clip_data = process_youtube_url(url, loan)
        elif 'tiktok.com' in url or 'vm.tiktok.com' in url:
            url_attempt['content_type'] = 'tiktok'
            url_attempt['processing_method'] = 'TikTok API'
            clip_data = process_tiktok_url(url, loan)
        elif 'instagram.com' in url:
            url_attempt['content_type'] = 'instagram'
            url_attempt['processing_method'] = 'Instagram API'
            clip_data = process_instagram_url(url, loan)
        else:
            url_attempt['content_type'] = 'web'
            url_attempt['processing_method'] = 'Web Crawler'
            clip_data = process_web_url(url, loan)
            
        if not clip_data or not clip_data.get('content'):
            url_attempt['reason'] = 'No content found or date filtered'
            url_tracking.append(url_attempt)
            logger.warning(f"No content found for URL: {url}")
            continue
            
        # Get the actual URL where content was found
        actual_url = clip_data.get('url', url)
        url_attempt['actual_url'] = actual_url
        logger.info(f"Analyzing content from URL: {actual_url}")
        analysis = analyze_clip(clip_data['content'], make, model, url=actual_url)
        
        # Check if analysis succeeded
        if analysis is None:
            url_attempt['reason'] = 'GPT analysis failed'
            url_tracking.append(url_attempt)
            logger.warning(f"GPT analysis failed for URL: {actual_url} - skipping this clip")
            continue
        
        # Check relevance
        relevance = analysis.get('relevance_score', 0)
        url_attempt['relevance_score'] = relevance
        
        if relevance > best_relevance:
            # NEW: Mark this URL as successful
            url_attempt['success'] = True
            url_attempt['reason'] = f'Best match (relevance: {relevance}/10)'
            
            # Add analysis to clip data
            clip_data.update(analysis)
            
            # Copy fields from loan to best_clip
            best_clip = {
                'WO #': work_order,
                'Activity_ID': loan.get('activity_id', ''),  # Add Activity_ID for approval workflow
                'Person_ID': loan.get('person_id', ''),  # Add Person_ID for smart outlet matching
                'Make': make,
                'Model': model,
                'Clip URL': actual_url,  # Use the actual URL where content was found (could be from RSS feed)
                # Add attribution information for transparency
                'Attribution_Strength': clip_data.get('attribution_strength', 'unknown'),
                'Actual_Byline': clip_data.get('actual_byline', ''),
                'Links': url,  # Original link from the input file
                'Relevance Score': relevance,
                'Sentiment': analysis.get('sentiment', 'neutral'),
                'Summary': analysis.get('summary', ''),
                'Brand Alignment': analysis.get('brand_alignment', False),
                'Processed Date': datetime.now().isoformat(),
                'Published Date': clip_data.get('published_date').isoformat() if clip_data.get('published_date') else None,
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
        else:
            # NEW: Mark as lower relevance but still processed
            url_attempt['success'] = True
            url_attempt['reason'] = f'Lower relevance (score: {relevance}/10)'
        
        # NEW: Add this URL attempt to tracking
        url_tracking.append(url_attempt)
        
        # Continue processing all URLs for comprehensive coverage
        # (removed early exit logic to capture all relevant sources)
        if relevance >= 8:
            logger.info(f"Found highly relevant clip (score {relevance}) for {make} {model} - continuing to process remaining URLs for complete coverage")
    
    # NEW: Add URL tracking data to the result
    if best_clip:
        # FIXED: Apply minimum relevance threshold to prevent 0/10 scores from being saved
        # Business requirement: Only relevant content should make it to Bulk Review
        if best_relevance <= 0:
            logger.warning(f"❌ Rejecting loan {work_order}: best relevance score {best_relevance}/10 does not meet minimum threshold (>0)")
            # Track rejection with detailed URL information
            url_details = ""
            if url_tracking:
                logger.info(f"📊 URL Summary for {work_order}: 0/{len(url_tracking)} URLs successful (relevance filter)")
                url_details_list = []
                for attempt in url_tracking:
                    logger.info(f"  ❌ {attempt['original_url']} → {attempt['reason']} (below relevance threshold)")
                    url_details_list.append(f"{attempt['original_url']}: {attempt['reason']}")
                url_details = "; ".join(url_details_list)
            
            add_rejected_record(loan, f"Low relevance score ({best_relevance}/10)", url_details)
            return None
            
        logger.info(f"Best clip for {work_order} has relevance {best_relevance}")
        # Add URL tracking summary to the result
        best_clip['URL_Tracking'] = url_tracking
        best_clip['URLs_Processed'] = len(url_tracking)
        best_clip['URLs_Successful'] = len([u for u in url_tracking if u['success']])
        
        # Log URL processing summary for transparency
        success_count = len([u for u in url_tracking if u['success']])
        logger.info(f"📊 URL Summary for {work_order}: {success_count}/{len(url_tracking)} URLs successful")
        for attempt in url_tracking:
            status = "✅" if attempt['success'] else "❌"
            logger.info(f"  {status} {attempt['original_url']} → {attempt['reason']}")
    else:
        logger.warning(f"No relevant clips found for {work_order}")
        # Track rejection with detailed URL information
        url_details = ""
        if url_tracking:
            logger.info(f"📊 URL Summary for {work_order}: 0/{len(url_tracking)} URLs successful")
            url_details_list = []
            for attempt in url_tracking:
                logger.info(f"  ❌ {attempt['original_url']} → {attempt['reason']}")
                url_details_list.append(f"{attempt['original_url']}: {attempt['reason']}")
            url_details = "; ".join(url_details_list)
        else:
            url_details = "No URLs to process"
        
        add_rejected_record(loan, "No relevant clips found", url_details)
        
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
                writer.writerow(['WO #', 'Activity_ID', 'Person_ID', 'Make', 'Model', 'To', 'Affiliation', 'Office', 'Clip URL', 'Links', 
                                'Relevance Score', 'Sentiment', 'Summary', 'Brand Alignment', 
                                'Processed Date', 'Published Date', 'Overall Score', 'Overall Sentiment', 'Recommendation',
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

def save_rejected_records(rejected_records: List[Dict[str, Any]], output_file: str) -> bool:
    """
    Save rejected records with detailed rejection reasons for transparency.
    
    Args:
        rejected_records: List of rejected record dictionaries
        output_file: Path to the rejected records CSV file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)
        
        # If no rejected records, create empty file with headers
        if not rejected_records:
            logger.info(f"No rejected records to save. Creating empty file: {output_file}")
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['WO #', 'Activity_ID', 'Make', 'Model', 'To', 'Affiliation', 'Office', 'Links', 'URLs_Processed', 'URLs_Successful',
                                'Rejection_Reason', 'URL_Details', 'Processed_Date', 'Loan_Start_Date'])
            return True
        
        # Convert to DataFrame for easier CSV handling
        df = pd.DataFrame(rejected_records)
        
        # Save to CSV
        df.to_csv(output_file, index=False)
        logger.info(f"Rejected records saved to {output_file}: {len(rejected_records)} records")
        return True
        
    except Exception as e:
        logger.error(f"Error saving rejected records to {output_file}: {e}")
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
        
        # Clear rejected records from previous run
        clear_rejected_records()
        
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
        
        # Save results and rejected records
        results_saved = save_results(results, output_file)
        
        # Save rejected records for transparency
        rejected_file = os.path.join(os.path.dirname(output_file), 'rejected_clips.csv')
        rejected_saved = save_rejected_records(REJECTED_RECORDS, rejected_file)
        
        if results_saved and rejected_saved:
            elapsed_time = time.time() - start_time
            message = (f"✅ Clip Tracking: Processed {len(loans)} loans, found {len(results)} clips, "
                      f"rejected {len(REJECTED_RECORDS)} records in {elapsed_time:.1f} seconds")
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

# ---------- CONCURRENT PROCESSING IMPLEMENTATION ----------
# Following ChatGPT's blueprint for safe concurrency wrapper

# Configuration
MAX_CONCURRENT = int(os.environ.get('MAX_CONCURRENT_LOANS', '5'))  # Start conservative

# Date validation is simple: Article date MUST be >= loan start date. Period.

async def process_loan_async(semaphore: asyncio.Semaphore, loan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Async wrapper around the existing process_loan function.
    
    This function preserves the exact same logic as process_loan()
    but runs it in a thread to enable concurrency.
    
    Args:
        semaphore: Async semaphore to control concurrency
        loan: Loan data dictionary
        
    Returns:
        Same as process_loan() - result dict or None
    """
    async with semaphore:
        # Run the existing process_loan function in a thread
        # This preserves ALL existing logic without any changes
        return await asyncio.to_thread(process_loan, loan)

async def process_loans_concurrent(loans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process multiple loans concurrently using ChatGPT's approach.
    
    This function runs multiple process_loan() calls in parallel
    without changing any of the internal logic.
    
    Args:
        loans: List of loan dictionaries
        
    Returns:
        List of results (same format as sequential processing)
    """
    if not loans:
        return []
    
    # Create semaphore to control concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    logger.info(f"Starting concurrent processing of {len(loans)} loans (max {MAX_CONCURRENT} concurrent)")
    
    # Create tasks for all loans
    tasks = [
        process_loan_async(semaphore, loan) 
        for loan in loans
    ]
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out None results and exceptions
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            loan = loans[i]
            work_order = loan.get('work_order', 'Unknown')
            logger.error(f"Error processing loan {work_order}: {result}")
        elif result is not None:
            final_results.append(result)
    
    logger.info(f"Concurrent processing completed: {len(final_results)} results from {len(loans)} loans")
    return final_results

def run_ingest_concurrent(
    input_file: Optional[str] = None, 
    output_file: Optional[str] = None,
    url: Optional[str] = None,
    limit: Optional[int] = None
) -> bool:
    """
    Main function to run the ingestion process concurrently.
    Can be initiated from either a local file or a URL.
    """
    start_time = time.time()
    logger.info("🚀 Starting concurrent ingestion process...")
    clear_rejected_records()  # Reset rejected records for this run
    
    try:
        # Determine the data source and load loans
        if url:
            loans = load_loans_data_from_url(url, limit=limit)
        elif input_file:
            loans = load_loans_data(input_file)
        else:
            logger.error("No input source provided. Must provide either `input_file` or `url`.")
            return False
        
        if not loans:
            logger.warning("No loans found to process.")
            # Save empty results and rejected files to clear out old data
            # This is important for the dashboard to reflect the empty state
            project_root = Path(__file__).parent.parent.parent
            results_file = os.path.join(project_root, "data", "loan_results.csv")
            rejected_file = os.path.join(project_root, "data", "rejected_clips.csv")
            save_results([], results_file)
            save_rejected_records([], rejected_file)
            return True

        # Process loans concurrently
        # This runs the asyncio event loop
        results = asyncio.run(process_loans_concurrent(loans))
        
        # Save results to CSV
        project_root = Path(__file__).parent.parent.parent
        if output_file is None:
            output_file = os.path.join(project_root, "data", "loan_results.csv")
        
        save_results(results, output_file)
        
        # Save rejected records
        rejected_file = os.path.join(project_root, "data", "rejected_clips.csv")
        save_rejected_records(REJECTED_RECORDS, rejected_file)
        
        duration = time.time() - start_time
        logger.info(f"✅ Concurrent ingestion process finished in {duration:.2f} seconds.")
        # send_slack_message(f"✅ Ingestion complete. Processed {len(loans)} loans in {duration:.2f}s.")
        return True

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ Ingestion process failed after {duration:.2f} seconds: {e}", exc_info=True)
        # send_slack_message(f"❌ Ingestion failed: {e}")
        return False

async def process_loans_concurrently(loans: List[Dict[str, Any]], total_loans: int) -> List[Dict[str, Any]]:
    """
    Process multiple loans concurrently using ChatGPT's approach.
    
    This function runs multiple process_loan() calls in parallel
    without changing any of the internal logic.
    
    Args:
        loans: List of loan dictionaries
        total_loans: Total number of loans for logging
        
    Returns:
        List of results (same format as sequential processing)
    """
    if not loans:
        return []
    
    # Create semaphore to control concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    logger.info(f"Starting concurrent processing of {len(loans)} loans (max {MAX_CONCURRENT} concurrent)")
    
    # Create tasks for all loans
    tasks = [
        process_loan_async(semaphore, loan) 
        for loan in loans
    ]
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out None results and exceptions
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            loan = loans[i]
            work_order = loan.get('work_order', 'Unknown')
            logger.error(f"Error processing loan {work_order}: {result}")
        elif result is not None:
            final_results.append(result)
    
    logger.info(f"Concurrent processing completed: {len(final_results)} results from {len(loans)} loans")
    return final_results

def run_ingest_concurrent_with_filters(
    filtered_loans: list,
    limit: int = 0
) -> bool:
    """
    Run the ingestion process with a pre-filtered list of loans.
    
    Args:
        filtered_loans: A list of loan dictionaries that have already been filtered.
        limit: Maximum number of records to process from the filtered list.
            
    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    logger.info("🚀 Starting filtered ingestion process...")
    clear_rejected_records()

    if not filtered_loans:
        logger.warning("No filtered loans provided to process.")
        return True

    # Apply limit if provided
    if limit > 0:
        logger.info(f"Limiting processing to {limit} records.")
        loans_to_process = filtered_loans[:limit]
    else:
        loans_to_process = filtered_loans

    total_to_process = len(loans_to_process)
    logger.info(f"Processing {total_to_process} loans after filtering.")
    
    if not loans_to_process:
        logger.warning("No loans to process after applying limit.")
        return True

    # Correctly run the async function from the sync function
    results = asyncio.run(process_loans_concurrently(loans_to_process, total_to_process))
    
    # Save results to CSV
    project_root = Path(__file__).parent.parent.parent
    output_file = os.path.join(project_root, "data", "loan_results.csv")
    save_results(results, output_file)
    
    # Save rejected records
    rejected_file = os.path.join(project_root, "data", "rejected_clips.csv")
    save_rejected_records(REJECTED_RECORDS, rejected_file)
    
    end_time = time.time()
    logger.info(f"✅ Filtered ingestion process finished in {end_time - start_time:.2f} seconds.")
    return True

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run clip tracking ingestion pipeline")
    parser.add_argument("--input", "-i", required=False, help="Path to input CSV/Excel file")
    parser.add_argument("--output", "-o", required=False, help="Path to output CSV file")
    parser.add_argument("--concurrent", action="store_true", help="Use concurrent processing")
    
    args = parser.parse_args()
    
    # Determine input file
    if args.input:
        input_file = args.input
    else:
        # When run directly without arguments, use the default fixtures
        project_root = Path(__file__).parent.parent.parent
        input_file = os.path.join(project_root, "data", "fixtures", "Loans_without_Clips.csv")
    
    # Run the appropriate ingestion function
    if args.concurrent:
        success = run_ingest_concurrent(input_file=args.input, output_file=args.output)
    else:
        success = run_ingest(input_file, args.output)
    
    # Exit with appropriate code
    exit(0 if success else 1) 