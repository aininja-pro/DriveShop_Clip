"""
Database-integrated ingestion pipeline.
This version stores clips to Supabase instead of CSV files and implements smart retry logic.
GPT analysis is skipped during ingestion to save costs - it will be run later in batches.
"""

import os
import asyncio
import time
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import re

# Import existing modules
from src.utils.logger import setup_logger
from src.utils.database import get_database
from src.ingest.ingest import (
    load_loans_data, 
    load_loans_data_from_url, 
    process_youtube_url, 
    process_web_url,
    parse_start_date,
    MAX_CONCURRENT
)
from src.analysis.gpt_analysis import analyze_clip_relevance_only
import json

logger = setup_logger(__name__)

def load_person_outlets_mapping():
    """Load Person_ID to Media Outlets mapping from JSON file"""
    try:
        project_root = Path(__file__).parent.parent.parent
        mapping_file = os.path.join(project_root, "data", "person_outlets_mapping.json")
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r') as f:
                mapping = json.load(f)
            logger.info(f"✅ Loaded Person_ID mapping with {len(mapping)} unique Person_IDs")
            return mapping
        else:
            logger.warning("⚠️ Person_ID mapping file not found - outlet validation disabled")
            return {}
    except Exception as e:
        logger.error(f"❌ Error loading Person_ID mapping: {e}")
        return {}

def is_url_from_authorized_outlet(url: str, person_id: str, outlets_mapping: dict) -> tuple[bool, str]:
    """
    Check if a URL belongs to an authorized outlet for the given person.
    
    Returns:
        tuple: (is_authorized, outlet_name or reason for rejection)
    """
    if not outlets_mapping:
        logger.warning("⚠️ No outlets mapping loaded - cannot validate URLs")
        return True, "No outlet validation available"
    
    if not person_id:
        logger.warning("⚠️ No person_id in loan data - skipping outlet validation")
        return True, "No person_id provided"
    
    person_id_str = str(person_id)
    if person_id_str not in outlets_mapping:
        logger.warning(f"⚠️ Person_ID {person_id} not found in outlets mapping - allowing URL")
        return True, "Person not in mapping"
    
    # Extract domain from URL
    try:
        parsed = urlparse(url)
        url_domain = parsed.netloc.lower()
        # Remove www. prefix for comparison
        url_domain = url_domain.replace('www.', '')
    except:
        return False, "Invalid URL format"
    
    # Get authorized outlets for this person
    person_data = outlets_mapping[person_id_str]
    authorized_outlets = person_data.get('outlets', [])
    
    # Check if URL matches any authorized outlet
    for outlet in authorized_outlets:
        outlet_url = outlet.get('outlet_url', '').lower()
        outlet_name = outlet.get('outlet_name', '')
        
        if outlet_url:
            # Extract domain from outlet URL
            try:
                parsed_outlet = urlparse(outlet_url)
                outlet_domain = parsed_outlet.netloc.lower().replace('www.', '')
                
                # Check if domains match
                if url_domain == outlet_domain or (url_domain.endswith('.' + outlet_domain) and 
                                                    url_domain[-(len(outlet_domain)+1)] == '.'):
                    return True, outlet_name
            except:
                continue
    
    # URL doesn't match any authorized outlet
    authorized_names = [o.get('outlet_name', 'Unknown') for o in authorized_outlets]
    logger.warning(f"❌ URL {url} is not from authorized outlets for Person_ID {person_id}")
    logger.warning(f"   Authorized outlets: {', '.join(authorized_names)}")
    return False, f"Not from authorized outlets: {', '.join(authorized_names)}"

def is_homepage_or_index_url(url: str) -> bool:
    """
    Check if URL is a homepage, index, or category page (not a specific article).
    We should NOT store these as clips.
    """
    parsed = urlparse(url.lower())
    path = parsed.path.strip('/')
    
    # Homepage indicators
    homepage_patterns = [
        '',  # Root domain
        'index.html',
        'index.php', 
        'home',
        'main',
        'category/car-reviews',
        'car-reviews',
        'reviews',
        'blog',
        'news',
        'articles',
        'page/1',
        'page/2',
        'page/3',
        'page/4',
        'page/5'
    ]
    
    for pattern in homepage_patterns:
        if path == pattern or path.endswith(f'/{pattern}'):
            return True
            
    # Category page patterns
    category_patterns = [
        '/category/',
        '/tag/',
        '/archives/',
        '/page/',
        '/reviews/',
        '/news/',
        '/blog/'
    ]
    
    for pattern in category_patterns:
        if pattern in path and not any(keyword in path for keyword in ['2024', '2025', 'review-', '-test-', '-drive-']):
            return True
    
    return False

def calculate_relevance_score(content: str, make: str, model: str, url: str) -> float:
    """
    Calculate pre-GPT relevance score (0.0 to 10.0) based on keyword matching.
    This helps filter out irrelevant content before expensive GPT analysis.
    """
    if not content or len(content) < 100:
        return 0.0
        
    content_lower = content.lower()
    make_lower = make.lower()
    model_lower = model.lower()
    
    score = 0.0
    
    # Core relevance scoring
    make_mentions = content_lower.count(make_lower)
    model_mentions = content_lower.count(model_lower)
    
    # Make mentions (max 3 points)
    score += min(make_mentions * 0.5, 3.0)
    
    # Model mentions (max 4 points)  
    score += min(model_mentions * 1.0, 4.0)
    
    # Combined mentions bonus (max 2 points)
    combined_patterns = [
        f"{make_lower} {model_lower}",
        f"{make_lower}-{model_lower}",
        f"{make_lower}{model_lower}"
    ]
    
    for pattern in combined_patterns:
        if pattern in content_lower:
            score += 2.0
            break
    
    # Review/test content bonus (max 1 point)
    review_keywords = ['review', 'test drive', 'first drive', 'road test', 'preview', 'impressions']
    for keyword in review_keywords:
        if keyword in content_lower:
            score += 0.2
    
    # Automotive content indicators (max 1 point)
    auto_keywords = ['mpg', 'horsepower', 'transmission', 'engine', 'interior', 'exterior', 'trunk', 'cargo']
    auto_count = sum(1 for keyword in auto_keywords if keyword in content_lower)
    score += min(auto_count * 0.1, 1.0)
    
    # Year indicators bonus (max 0.5 points)
    year_patterns = ['2024', '2025', '2023']
    for year in year_patterns:
        if year in content_lower:
            score += 0.5
            break
    
    return min(score, 10.0)

def process_loan_for_database(loan: Dict[str, Any], run_id: str, outlets_mapping: dict = None) -> Dict[str, Any]:
    """
    Process a single loan and store results to database instead of CSV.
    Includes URL validation and relevance scoring to prevent storing bad clips.
    """
    wo_number = str(loan.get('work_order', ''))
    make = loan.get('make', '')
    model = loan.get('model', '')
    model_short = loan.get('model_short', '')  # Get short model from dashboard
    contact = loan.get('to', '')
    person_id = loan.get('person_id', '')
    
    # Activity ID should already be in the loan data from load_loans_data_from_url
    activity_id = loan.get('activity_id', '')
    
    # CRITICAL FIX: Set search_model for hierarchical search (broad to specific)
    # Use short model if available (e.g., "Tacoma" instead of "Tacoma TRD Pro Double Cab")
    if model_short:
        loan['search_model'] = model_short
        logger.info(f"Using SHORT model for hierarchical search: '{model_short}' (full: '{model}')")
    else:
        loan['search_model'] = model
        logger.info(f"No short model available, using full model: '{model}'")
    
    logger.info(f"Processing loan {wo_number}: {make} {model} (database mode - no GPT)")
    
    urls = loan.get('urls', [])  # URLs are already parsed as a list
    
    successful_urls = 0
    clip_results = []
    
    # Collect results from all URLs to pick the best one
    all_results = []
    
    # Lazy import to avoid circulars; used for cancellation checks
    from src.utils.database import get_database as _get_db
    db_for_cancel = None
    try:
        db_for_cancel = _get_db()
    except Exception:
        db_for_cancel = None

    for url in urls:
        # Cooperative cancellation: check DB before each heavy URL processing
        try:
            if db_for_cancel and run_id:
                status_result = db_for_cancel.supabase.table('processing_runs').select('job_status').eq('id', run_id).single().execute()
                if status_result.data and status_result.data.get('job_status') == 'cancelled':
                    logger.info(f"Cancellation detected for run {run_id} before processing URL; aborting loan {wo_number}")
                    raise Exception("Job cancelled by user")
        except Exception:
            # If status check fails, continue; do not crash
            pass
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
        
        logger.info(f"Processing URL: {url}")
        
        # MEDIA OUTLET VALIDATION - Check if URL is from authorized outlet
        if outlets_mapping and person_id:
            is_authorized, outlet_info = is_url_from_authorized_outlet(url, person_id, outlets_mapping)
            if not is_authorized:
                logger.warning(f"⚠️ SKIPPING unauthorized outlet URL: {url}")
                logger.warning(f"   Reason: {outlet_info}")
                continue
            else:
                logger.info(f"✅ URL authorized: {outlet_info}")
        
        # DISABLED: Homepage filtering was blocking valid review URLs like carpro.com/resources/vehicle-reviews
        # if is_homepage_or_index_url(url):
        #     logger.warning(f"⚠️ SKIPPING homepage/index URL: {url}")
        #     continue
            
        # Process the URL based on platform
        try:
            # Helper to reuse in nested calls
            def _cancelled():
                try:
                    if db_for_cancel and run_id:
                        st = db_for_cancel.supabase.table('processing_runs').select('job_status').eq('id', run_id).single().execute()
                        return bool(st.data and st.data.get('job_status') == 'cancelled')
                except Exception:
                    return False
                return False

            if 'youtube.com' in url or 'youtu.be' in url:
                result = process_youtube_url(url, loan, cancel_check=_cancelled)
            elif 'tiktok.com' in url or 'vm.tiktok.com' in url:
                # Import the TikTok processing function
                from src.ingest.ingest import process_tiktok_url
                result = process_tiktok_url(url, loan)
            elif 'instagram.com' in url:
                # Import the Instagram processing function
                from src.ingest.ingest import process_instagram_url
                result = process_instagram_url(url, loan)
            else:
                result = process_web_url(url, loan, cancel_check=_cancelled)
            
            if result and (result.get('clip_url') or result.get('url')):
                all_results.append((url, result))
        except Exception as e:
            # Bubble up cancellation quickly
            if 'cancelled by user' in str(e).lower():
                raise
            logger.error(f"❌ Error processing URL {url}: {e}")
            # Continue processing other URLs even if this one fails
    
    # Process all collected results through GPT and pick the best one
    best_result = None
    best_score = -1
    
    for url, result in all_results:
            # Additional validation: Check if result URL is also a homepage
            result_url = result.get('clip_url') or result.get('url', '')
            if is_homepage_or_index_url(result_url):
                logger.warning(f"⚠️ REJECTING result - homepage URL returned: {result_url}")
                continue
            
            # Use GPT relevance-only analysis (like OLD system but without sentiment)
            content = result.get('extracted_content') or result.get('content', '')
            
            # CRITICAL FIX: Extract clean article text from HTML before GPT analysis
            # This ensures GPT analyzes article content, not HTML tags and navigation
            if content and not ('youtube.com' in url or 'youtu.be' in url):
                # Check if content is HTML and extract article text
                import re
                is_html = bool(re.search(r'<html|<body|<div|<p>', content))
                if is_html:
                    logger.info("Content appears to be HTML. Extracting clean article text...")
                    
                    # Import the content extractor
                    from src.utils.content_extractor import extract_article_content
                    
                    # Create expected topic from vehicle make and model for quality checking
                    expected_topic = f"{make} {model}"
                    extracted_content = extract_article_content(content, result_url, expected_topic)
                    
                    # Check if extraction was successful
                    if extracted_content and len(extracted_content.strip()) > 100:
                        logger.info(f"✅ Successfully extracted clean article text: {len(extracted_content)} characters")
                        content = extracted_content  # Use the clean extracted content for GPT analysis
                    else:
                        logger.warning("⚠️ Article extraction failed or returned minimal content. Using raw HTML.")
                        # Don't reject entirely - let GPT try with raw HTML as fallback
            
            # Extract title for both YouTube and web content
            content_title = None
            if 'youtube.com' in url or 'youtu.be' in url:
                # Extract title from the formatted YouTube content
                import re
                title_match = re.search(r'Video Title:\s*(.+?)(?:\n|$)', content)
                if title_match:
                    content_title = title_match.group(1).strip()
                    logger.info(f"📹 Extracted video title: '{content_title}'")
            else:
                # For web articles, use the title from the result
                content_title = result.get('title', '')
                if content_title and content_title != result_url:  # Don't use URL as title
                    logger.info(f"📰 Using article title: '{content_title}'")
            
            try:
                gpt_result = analyze_clip_relevance_only(content, make, model, video_title=content_title)
                relevance_score = gpt_result.get('relevance_score', 0) if gpt_result else 0
                
                # Only store if relevance score is reasonable (same threshold as OLD system)
                if relevance_score <= 0:
                    logger.warning(f"⚠️ REJECTING clip - GPT relevance score {relevance_score} <= 0")
                    logger.info(f"   URL: {result_url}")
                    logger.info(f"   Content preview: {content[:200]}...")
                    continue
            except Exception as e:
                logger.error(f"❌ GPT relevance analysis failed: {e}")
                # Fallback to simple scoring on GPT failure
                relevance_score = calculate_relevance_score(content, make, model, result_url)
                if relevance_score < 2.0:
                    logger.warning(f"⚠️ REJECTING clip - fallback relevance score {relevance_score:.1f} < 2.0")
                    continue
            
            logger.info(f"✅ Found clip for {wo_number} at {result_url} - content extracted ({len(content)} chars)")
            logger.info(f"📊 Relevance score: {relevance_score:.1f}/10.0")
            
            # Add relevance score to result and normalize field names
            result['relevance_score'] = relevance_score
            result['office'] = loan.get('office', '')
            result['person_id'] = person_id
            result['activity_id'] = activity_id
            
            # CRITICAL FIX: Normalize field names between OLD and NEW systems
            # OLD system expects 'clip_url', NEW system gets 'url' from process_web_url
            if not result.get('clip_url') and result.get('url'):
                result['clip_url'] = result['url']
            if not result.get('extracted_content') and result.get('content'):
                result['extracted_content'] = result['content']
            
            # Debug logging for date tracking
            if result.get('published_date'):
                logger.info(f"📅 Result has published_date: {result.get('published_date')}")
            else:
                logger.warning(f"⚠️ Result missing published_date for {result_url}")
                logger.info(f"Result keys: {list(result.keys())}")
            
            clip_results.append(result)
            successful_urls += 1
            # Continue processing all URLs to find the BEST clip
    
    # NEW: Select only the BEST clip per WO# (highest relevance score)
    if clip_results:
        # Sort by relevance score (highest first), then by processed date (most recent first)
        best_clip = max(clip_results, key=lambda clip: (
            clip.get('relevance_score', 0),
            clip.get('processed_date', '1970-01-01')
        ))
        
        logger.info(f"📊 Selected BEST clip for {wo_number}: relevance {best_clip.get('relevance_score', 0):.1f}/10")
        logger.info(f"📊 URL Summary for {wo_number}: {successful_urls}/{len(urls)} URLs found, keeping best clip")
        
        return {
            'wo_number': wo_number,
            'successful': True,
            'clips': [best_clip]  # Only return the best clip
        }
    else:
        logger.info(f"📊 URL Summary for {wo_number}: {successful_urls}/{len(urls)} URLs successful")
        
        return {
            'wo_number': wo_number,
            'successful': False,
            'clips': []
        }

async def process_loan_database_async(semaphore: asyncio.Semaphore, loan: Dict[str, Any], db, run_id: str, outlets_mapping: dict = None) -> bool:
    """
    Async wrapper for database-integrated loan processing with smart retry logic.
    STORES ALL LOAN ATTEMPTS (successful and failed) to database.
    
    Args:
        semaphore: Async semaphore to control concurrency
        loan: Loan data dictionary
        db: Database manager instance
        run_id: Processing run ID for tracking
        
    Returns:
        True if processed (success or failure), False if skipped
    """
    async with semaphore:
        wo_number = loan.get('work_order', '')
        
        # SMART RETRY LOGIC: Check if we should process this WO#
        should_process = db.should_retry_wo(wo_number)
        if not should_process:
            # Determine skip reason based on database state
            clips_result = db.supabase.table('clips').select('status').eq('wo_number', wo_number).execute()
            if clips_result.data:
                clip_status = clips_result.data[0].get('status', '')
                if clip_status in ['approved', 'pending_review', 'rejected']:
                    skip_reason = f'already_{clip_status}'
                elif clip_status in ['no_content_found', 'processing_failed']:
                    skip_reason = 'retry_cooldown'
                else:
                    skip_reason = 'unknown'
            else:
                skip_reason = 'unknown'
            
            # Record the skip event
            db.record_skip_event(wo_number, run_id, skip_reason)
            logger.info(f"⏭️ Skipping {wo_number} - {skip_reason}")
            return False
        
        # Process the loan (crawling + content extraction, no GPT)
        result = await asyncio.to_thread(process_loan_for_database, loan, run_id, outlets_mapping)
        
        if result and result.get('successful') and result.get('clips'):
            # SUCCESS: Store clips to database
            stored_clips = 0
            for clip_result in result['clips']:
                clip_data = {
                    'wo_number': result['wo_number'],
                    'processing_run_id': run_id,
                    'office': clip_result.get('office'),
                    'make': loan.get('make'),
                    'model': loan.get('model'),  # This is already the base model from ingest.py
                    'trim': loan.get('trim'),  # This already has the extracted trim from ingest.py
                    'contact': loan.get('to'),  # FIX: Get contact name from loan data, not clip_result
                    'person_id': clip_result.get('person_id'),
                    'activity_id': loan.get('activity_id'),  # FIX: Get Activity_ID from loan data, not clip_result
                    'clip_url': clip_result.get('clip_url'),
                    'extracted_content': clip_result.get('extracted_content'),
                    'published_date': clip_result.get('published_date').isoformat() if clip_result.get('published_date') and hasattr(clip_result.get('published_date'), 'isoformat') else clip_result.get('published_date'),
                    'attribution_strength': clip_result.get('attribution_strength'),
                    'byline_author': clip_result.get('byline_author'),
                    'tier_used': clip_result.get('processing_method', 'Unknown'),
                    'relevance_score': clip_result.get('relevance_score', 0.0),
                    'status': 'pending_review',  # No GPT analysis yet
                    'workflow_stage': 'found'
                }
                
                try:
                    success = db.store_clip(clip_data)
                    if success:
                        db.mark_wo_success(result['wo_number'], clip_result.get('clip_url'))
                        logger.info(f"✅ Stored clip for {result['wo_number']} in database")
                        stored_clips += 1
                    else:
                        logger.error(f"❌ Failed to store clip for {result['wo_number']}")
                        db.mark_wo_attempt(result['wo_number'], 'store_failed', 'Database storage failed')
                except Exception as e:
                    logger.error(f"❌ Failed to store clip: {e}")
                    db.mark_wo_attempt(result['wo_number'], 'store_failed', str(e))
            
            return stored_clips > 0
        else:
            # FAILURE: No clips found - STORE to database with failed status
            wo_number = result.get('wo_number') if result else loan.get('work_order', 'unknown')
            
            # ENHANCEMENT: Store original source URLs for transparency in View link
            original_urls = loan.get('urls', [])
            original_urls_text = '; '.join(original_urls) if original_urls else 'No URLs provided'
            
            # Store the failed attempt as a record with no_content_found status
            failed_loan_data = {
                'wo_number': wo_number,
                'processing_run_id': run_id,
                'office': loan.get('office'),
                'make': loan.get('make'),
                'model': loan.get('model'),
                'contact': loan.get('to'),
                'person_id': loan.get('person_id'),
                'activity_id': loan.get('activity_id'),  # Activity_ID is correctly sourced from loan data
                'tier_used': result.get('tier_used', 'Unknown') if result else 'Unknown',
                'workflow_stage': 'found',
                # NEW: Store original source URLs for View link
                'original_urls': original_urls_text,
                'urls_attempted': len(original_urls),
                'failure_reason': f"No content found from {len(original_urls)} URLs: {original_urls_text[:100]}..."
            }
            
            try:
                # Store as no_content_found status
                success = db.store_failed_attempt(failed_loan_data, 'no_content_found')
                if success:
                    logger.info(f"✅ Stored failed attempt for {wo_number} in database")
                else:
                    logger.error(f"❌ Failed to store failed attempt for {wo_number}")
            except Exception as e:
                logger.error(f"❌ Exception storing failed attempt: {e}")
                # Store as processing_failed if we can't even store the no_content_found
                try:
                    db.store_failed_attempt(failed_loan_data, 'processing_failed')
                except:
                    pass  # Last resort - don't let this break the pipeline
            
            return True  # Return True because we DID process it (even if no clips found)

async def process_loans_database_concurrent(
    loans: List[Dict[str, Any]], 
    db, 
    run_id: str, 
    outlets_mapping: dict = None,
    progress_callback: Optional[Callable] = None
) -> Dict[str, int]:
    """
    Process multiple loans concurrently with database storage and smart retry logic.
    
    Args:
        loans: List of loan dictionaries
        db: Database manager instance
        run_id: Processing run ID for tracking
        
    Returns:
        Dictionary with processing statistics
    """
    if not loans:
        return {'processed': 0, 'skipped': 0, 'successful': 0, 'failed': 0}
    
    # Create semaphore to control concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    logger.info(f"Starting database-integrated concurrent processing of {len(loans)} loans (max {MAX_CONCURRENT} concurrent)")
    
    # Create tasks for all loans
    tasks = [
        process_loan_database_async(semaphore, loan, db, run_id, outlets_mapping) 
        for loan in loans
    ]
    
    # Process tasks and track progress
    processed_count = 0
    skipped_count = 0
    error_count = 0
    total_loans = len(loans)
    
    # Process tasks as they complete for progress tracking
    results = []
    for i, task in enumerate(asyncio.as_completed(tasks)):
        try:
            # Cooperative cancellation: check job status before awaiting each task
            try:
                current_run = db.supabase.table('processing_runs').select('job_status').eq('id', run_id).single().execute()
                if current_run.data and current_run.data.get('job_status') == 'cancelled':
                    logger.info(f"Run {run_id} cancelled - stopping further processing")
                    break
            except Exception:
                # If we can't read status, continue but don't crash
                pass

            result = await task
            results.append(result)
            
            if result is True:
                processed_count += 1
            elif result is False:
                skipped_count += 1
                
            # Update progress callback every 2 records or at milestones for smoother updates
            completed = i + 1
            if progress_callback and (completed % 2 == 0 or completed == total_loans or completed == 1):
                progress_callback(completed, total_loans)
                
        except Exception as e:
            results.append(e)
            error_count += 1
            # Find which loan failed
            logger.error(f"Error processing loan: {e}")
    
    # Get success count from database (clips that were actually stored)
    clips_stored = db.get_pending_clips(run_id)
    successful_count = len(clips_stored)
    failed_count = processed_count - successful_count
    
    stats = {
        'processed': processed_count,
        'skipped': skipped_count, 
        'successful': successful_count,
        'failed': failed_count,
        'errors': error_count
    }
    
    logger.info(f"Database processing completed: {stats}")
    return stats

def run_ingest_database(
    input_file: Optional[str] = None,
    url: Optional[str] = None,
    limit: Optional[int] = None,
    run_name: Optional[str] = None
) -> bool:
    """
    Main function to run the database-integrated ingestion process.
    This version stores clips to Supabase and implements smart retry logic.
    
    Args:
        input_file: Path to input CSV/Excel file (optional)
        url: URL to loans data (optional)
        limit: Maximum number of loans to process (optional)
        run_name: Custom name for this processing run (optional)
        
    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    logger.info("🗄️ Starting DATABASE-INTEGRATED ingestion process...")
    
    try:
        # Initialize database connection
        db = get_database()
        
        # Create processing run
        if not run_name:
            run_name = f"Database_Run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        run_id = db.create_processing_run(run_name)
        logger.info(f"📊 Created processing run: {run_name} (ID: {run_id})")
        
        # Load loans data (same logic as original)
        if url:
            loans = load_loans_data_from_url(url, limit=limit)
        elif input_file:
            loans = load_loans_data(input_file)
        else:
            logger.error("No input source provided. Must provide either 'input_file' or 'url'.")
            return False
        
        if not loans:
            logger.warning("No loans found to process.")
            db.finish_processing_run(run_id, successful_finds=0, failed_attempts=0)
            return True
        
        logger.info(f"📥 Loaded {len(loans)} loans for database processing")
        
        # Load outlets mapping for media validation
        outlets_mapping = load_person_outlets_mapping()
        
        # Process loans with database storage and smart retry logic
        stats = asyncio.run(process_loans_database_concurrent(loans, db, run_id, outlets_mapping, None))
        
        # Update processing run with final statistics
        db.finish_processing_run(
            run_id, 
            successful_finds=stats['successful'], 
            failed_attempts=stats['failed']
        )
        
        duration = time.time() - start_time
        
        # Log comprehensive results
        logger.info(f"✅ Database ingestion completed in {duration:.2f} seconds:")
        logger.info(f"   📊 Total loans: {len(loans)}")
        logger.info(f"   ⏭️ Skipped (smart retry): {stats['skipped']}")
        logger.info(f"   🔄 Processed: {stats['processed']}")
        logger.info(f"   ✅ Clips found: {stats['successful']}")
        logger.info(f"   ❌ No clips found: {stats['failed']}")
        logger.info(f"   💰 GPT calls saved: {stats['processed']} (cost savings!)")
        
        # Calculate smart retry efficiency
        if len(loans) > 0:
            efficiency = (stats['skipped'] / len(loans)) * 100
            logger.info(f"   ⚡ Smart retry efficiency: {efficiency:.1f}% of work avoided")
        
        return True
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ Database ingestion failed after {duration:.2f} seconds: {e}", exc_info=True)
        return False

def run_ingest_database_with_filters(
    filtered_loans: List[Dict[str, Any]],
    limit: int = 0,
    run_name: Optional[str] = None,
    progress_callback: Optional[Callable] = None
) -> bool:
    """
    Run database ingestion with pre-filtered loans (from dashboard).
    
    Args:
        filtered_loans: Pre-filtered list of loan dictionaries
        limit: Maximum number of records to process
        run_name: Custom name for this processing run
        
    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    logger.info("🗄️ Starting FILTERED database ingestion...")
    
    if not filtered_loans:
        logger.warning("No filtered loans provided to process.")
        return True
    
    # Apply limit if provided
    if limit > 0:
        logger.info(f"Limiting processing to {limit} records.")
        loans_to_process = filtered_loans[:limit]
    else:
        loans_to_process = filtered_loans
    
    logger.info(f"Processing {len(loans_to_process)} loans after filtering.")
    
    try:
        # Initialize database connection
        db = get_database()
        
        # Create processing run
        if not run_name:
            run_name = f"Filtered_Run_{datetime.now().strftime('%Y%m%d_%H%M%S')} ({len(loans_to_process)} loans)"
        
        run_id = db.create_processing_run(run_name)
        
        # Load outlets mapping for media validation
        outlets_mapping = load_person_outlets_mapping()
        
        # Process loans
        stats = asyncio.run(process_loans_database_concurrent(
            loans_to_process, db, run_id, outlets_mapping, progress_callback
        ))
        
        # Update processing run
        db.finish_processing_run(
            run_id, 
            successful_finds=stats['successful'], 
            failed_attempts=stats['failed']
        )
        
        duration = time.time() - start_time
        logger.info(f"✅ Filtered database ingestion completed in {duration:.2f} seconds: {stats}")
        
        return True
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ Filtered database ingestion failed after {duration:.2f} seconds: {e}")
        return False

# Test function for development
def test_database_integration():
    """Test the database integration with a small dataset"""
    logger.info("🧪 Testing database integration...")
    
    # Use test fixture
    project_root = Path(__file__).parent.parent.parent
    test_file = os.path.join(project_root, "data", "fixtures", "Loans_without_Clips.csv")
    
    if not os.path.exists(test_file):
        logger.error(f"Test file not found: {test_file}")
        return False
    
    # Run with limit for testing
    success = run_ingest_database(
        input_file=test_file,
        limit=3,  # Test with just 3 records
        run_name="Test_Database_Integration"
    )
    
    if success:
        logger.info("✅ Database integration test PASSED!")
    else:
        logger.error("❌ Database integration test FAILED!")
    
    return success

if __name__ == "__main__":
    # Run test when called directly
    success = test_database_integration()
    exit(0 if success else 1) 