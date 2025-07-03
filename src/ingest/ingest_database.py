"""
Database-integrated ingestion pipeline.
This version stores clips to Supabase instead of CSV files and implements smart retry logic.
GPT analysis is skipped during ingestion to save costs - it will be run later in batches.
"""

import os
import asyncio
import time
from typing import List, Dict, Any, Optional
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

logger = setup_logger(__name__)

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

def process_loan_for_database(loan: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    """
    Process a single loan and store results to database instead of CSV.
    Includes URL validation and relevance scoring to prevent storing bad clips.
    """
    wo_number = str(loan.get('work_order', ''))
    make = loan.get('make', '')
    model = loan.get('model', '')
    contact = loan.get('to', '')
    person_id = loan.get('person_id', '')
    
    # Activity ID should already be in the loan data from load_loans_data_from_url
    activity_id = loan.get('activity_id', '')
    
    logger.info(f"Processing loan {wo_number}: {make} {model} (database mode - no GPT)")
    
    urls = loan.get('urls', [])  # URLs are already parsed as a list
    
    successful_urls = 0
    clip_results = []
    
    for url in urls:
        logger.info(f"Processing URL: {url}")
        
        # Skip if this is obviously a homepage/index URL
        if is_homepage_or_index_url(url):
            logger.warning(f"⚠️ SKIPPING homepage/index URL: {url}")
            continue
            
        # Process the URL (YouTube or Web) - using correct function signatures
        if 'youtube.com' in url or 'youtu.be' in url:
            result = process_youtube_url(url, loan)
        else:
            result = process_web_url(url, loan)
        
        if result and result.get('clip_url'):
            # Additional validation: Check if result URL is also a homepage
            result_url = result.get('clip_url', '')
            if is_homepage_or_index_url(result_url):
                logger.warning(f"⚠️ REJECTING result - homepage URL returned: {result_url}")
                continue
            
            # Calculate relevance score before storing
            content = result.get('extracted_content', '')
            relevance_score = calculate_relevance_score(content, make, model, result_url)
            
            # Only store if relevance score is reasonable
            MIN_RELEVANCE_THRESHOLD = 2.0  # At least some vehicle mentions
            if relevance_score < MIN_RELEVANCE_THRESHOLD:
                logger.warning(f"⚠️ REJECTING clip - low relevance score {relevance_score:.1f} < {MIN_RELEVANCE_THRESHOLD}")
                logger.info(f"   URL: {result_url}")
                logger.info(f"   Content preview: {content[:200]}...")
                continue
            
            logger.info(f"✅ Found clip for {wo_number} at {result_url} - content extracted ({len(content)} chars)")
            logger.info(f"📊 Relevance score: {relevance_score:.1f}/10.0")
            
            # Add relevance score to result
            result['relevance_score'] = relevance_score
            result['office'] = loan.get('office', '')
            result['person_id'] = person_id
            result['activity_id'] = activity_id
            
            clip_results.append(result)
            successful_urls += 1
            break  # Only store first successful clip per loan
    
    logger.info(f"📊 URL Summary for {wo_number}: {successful_urls}/{len(urls)} URLs successful")
    
    return {
        'wo_number': wo_number,
        'successful': successful_urls > 0,
        'clips': clip_results
    }

async def process_loan_database_async(semaphore: asyncio.Semaphore, loan: Dict[str, Any], db, run_id: str) -> bool:
    """
    Async wrapper for database-integrated loan processing with smart retry logic.
    
    Args:
        semaphore: Async semaphore to control concurrency
        loan: Loan data dictionary
        db: Database manager instance
        run_id: Processing run ID for tracking
        
    Returns:
        True if processed (success or failure), False if skipped
    """
    async with semaphore:
        wo_number = loan.get('WO #', '')
        
        # SMART RETRY LOGIC: Check if we should process this WO#
        if not db.should_retry_wo(wo_number):
            logger.info(f"⏭️ Skipping {wo_number} - smart retry logic (recently attempted)")
            return False
        
        # Process the loan (crawling + content extraction, no GPT)
        result = await asyncio.to_thread(process_loan_for_database, loan, run_id)
        
        if result and result.get('successful') and result.get('clips'):
            # SUCCESS: Store clips to database
            stored_clips = 0
            for clip_result in result['clips']:
                clip_data = {
                    'wo_number': result['wo_number'],
                    'processing_run_id': run_id,
                    'office': clip_result.get('office'),
                    'make': loan.get('make'),
                    'model': loan.get('model'),
                    'contact': clip_result.get('contact'),
                    'person_id': clip_result.get('person_id'),
                    'activity_id': clip_result.get('activity_id'),
                    'clip_url': clip_result.get('clip_url'),
                    'extracted_content': clip_result.get('extracted_content'),
                    'published_date': clip_result.get('published_date').isoformat() if clip_result.get('published_date') else None,
                    'attribution_strength': clip_result.get('attribution_strength'),
                    'byline_author': clip_result.get('byline_author'),
                    'tier_used': clip_result.get('processing_method', 'Unknown'),
                    'relevance_score': clip_result.get('relevance_score', 0.0),
                    'status': 'pending_review'  # No GPT analysis yet
                }
                
                try:
                    clip_id = db.store_clip(clip_data)
                    db.mark_wo_as_successful(result['wo_number'])
                    db.mark_wo_attempt(result['wo_number'], 'success', None)
                    logger.info(f"✅ Stored clip for {result['wo_number']} in database")
                    stored_clips += 1
                except Exception as e:
                    logger.error(f"❌ Failed to store clip: {e}")
                    db.mark_wo_attempt(result['wo_number'], 'store_failed', str(e))
            
            return stored_clips > 0
        else:
            # FAILURE: No clips found, record for smart retry
            wo_number = result.get('wo_number') if result else loan.get('work_order', 'unknown')
            db.mark_wo_attempt(wo_number, 'no_content', 'No valid clips found after filtering')
            logger.info(f"🚫 No clips found for {wo_number} - recorded for smart retry")
            return False

async def process_loans_database_concurrent(loans: List[Dict[str, Any]], db, run_id: str) -> Dict[str, int]:
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
        process_loan_database_async(semaphore, loan, db, run_id) 
        for loan in loans
    ]
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Count results
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            loan = loans[i]
            work_order = loan.get('work_order', 'Unknown')
            logger.error(f"Error processing loan {work_order}: {result}")
            error_count += 1
        elif result is True:
            processed_count += 1
        elif result is False:
            skipped_count += 1
    
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
        
        # Process loans with database storage and smart retry logic
        stats = asyncio.run(process_loans_database_concurrent(loans, db, run_id))
        
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
    run_name: Optional[str] = None
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
        
        # Process loans
        stats = asyncio.run(process_loans_database_concurrent(loans_to_process, db, run_id))
        
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