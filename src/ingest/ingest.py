import os
import csv
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import time

# Import local modules
from src.utils.logger import setup_logger
from src.utils.notifications import send_slack_message
from src.utils.youtube_handler import get_channel_id, get_latest_videos, get_transcript, extract_video_id
from src.utils.escalation import crawling_strategy
from src.utils.crawler_manager import CrawlerManager
from src.analysis.gpt_analysis import analyze_clip

logger = setup_logger(__name__)

# Initialize the crawler manager (it will be reused for all URLs)
crawler_manager = CrawlerManager()

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
        
        # Check for model columns (might be named differently)
        model_column = None
        model_columns = ['Model', 'Model Short Name']
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
                'work_order': str(row['WO #']),
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
                # Handle multiple URLs in one cell (semicolon-separated)
                if isinstance(row[url_column], str) and ';' in row[url_column]:
                    for url in row[url_column].split(';'):
                        if url.strip() and not url.strip().startswith('https://fms.driveshop.com/'):
                            loan['urls'].append(url.strip())
                else:
                    url = str(row[url_column]).strip()
                    if url and not url.startswith('https://fms.driveshop.com/'):
                        loan['urls'].append(url)
            
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
        # First check if it's a direct video URL
        video_id = extract_video_id(url)
        
        if video_id:
            # Direct video URL - get transcript
            logger.info(f"Processing YouTube video: {url}")
            transcript = get_transcript(video_id)
            
            if transcript:
                return {
                    'url': url,
                    'content': transcript,
                    'content_type': 'video',
                    'title': f"YouTube Video {video_id}"  # Title not available from transcript API
                }
            else:
                logger.warning(f"No transcript available for video: {url}")
                return None
        
        # If not a direct video, try as a channel
        channel_id = get_channel_id(url)
        
        if not channel_id:
            logger.warning(f"Could not resolve YouTube channel ID from: {url}")
            return None
        
        # Get latest videos from channel
        logger.info(f"Fetching latest videos for channel: {channel_id}")
        videos = get_latest_videos(channel_id)
        
        if not videos:
            logger.warning(f"No videos found for channel: {channel_id}")
            return None
        
        # Try to find a relevant video by checking titles
        make = loan.get('make', '').lower()
        model = loan.get('model', '').lower()
        
        for video in videos:
            video_title = video.get('title', '').lower()
            
            # Check if title mentions the vehicle
            if make in video_title and model in video_title:
                logger.info(f"Found relevant video by title: {video['title']}")
                video_id = video['video_id']
                transcript = get_transcript(video_id)
                
                if transcript:
                    return {
                        'url': video['url'],
                        'content': transcript,
                        'content_type': 'video',
                        'title': video['title']
                    }
        
        # If no relevant video found by title, check transcripts
        for video in videos:
            video_id = video['video_id']
            transcript = get_transcript(video_id)
            
            if not transcript:
                continue
                
            # Check if transcript mentions the vehicle
            if make in transcript.lower() and model in transcript.lower():
                logger.info(f"Found relevant video by transcript content: {video['title']}")
                return {
                    'url': video['url'],
                    'content': transcript,
                    'content_type': 'video',
                    'title': video['title']
                }
        
        logger.info(f"No relevant videos found for {make} {model} in channel {channel_id}")
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
        # Use the crawler manager with automatic escalation
        logger.info(f"Processing web URL: {url}")
        
        # Get make and model for finding relevant content
        make = loan.get('make', '')
        model = loan.get('model', '')
        
        # Increase wait time to 15 seconds for JS-heavy sites and pass make/model
        content, title, error, actual_url = crawler_manager.crawl(
            url, 
            wait_time=15,
            vehicle_make=make,
            vehicle_model=model
        )
        
        if error:
            logger.warning(f"Error crawling {url}: {error}")
            return None
            
        if not content:
            logger.warning(f"No content retrieved from {url}")
            return None
            
        # Use the actual URL where content was found (might be different from input URL)
        if not actual_url:
            actual_url = url
            
        logger.info(f"Using content from URL: {actual_url}")
            
        # Return the processed content
        return {
            'url': actual_url,  # Use the actual URL where content was found
            'original_url': url,  # Keep the original URL for reference
            'content': content,
            'content_type': 'article',
            'title': title or url
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
            
        # Analyze the clip - pass the URL for proper content extraction
        clip_url = clip_data.get('url', url)
        logger.info(f"Analyzing content from URL: {clip_url}")
        analysis = analyze_clip(clip_data['content'], make, model, url=clip_url)
        
        # Check relevance
        relevance = analysis.get('relevance_score', 0)
        
        if relevance > best_relevance:
            # Add analysis to clip data
            clip_data.update(analysis)
            
            # Copy fields from loan to best_clip
            best_clip = {
                'WO #': work_order,
                'Model': model,
                'Clip URL': clip_data['url'],  # Use the actual URL where content was found
                'Links': url,  # Original link from the input file
                'Relevance Score': relevance,
                'Sentiment': analysis.get('sentiment', 'neutral'),
                'Summary': analysis.get('summary', ''),
                'Brand Alignment': analysis.get('brand_alignment', False),
                'Processed Date': datetime.now().isoformat()
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
                                'Processed Date'])
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
            send_slack_message(f"❌ Clip Tracking: Failed to load loans data from {input_file}")
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
            send_slack_message(message)
            return True
        else:
            send_slack_message(f"❌ Clip Tracking: Failed to save results to {output_file}")
            return False
            
    except Exception as e:
        error_message = f"❌ Clip Tracking: Error during ingestion: {e}"
        logger.error(error_message)
        send_slack_message(error_message)
        return False
    finally:
        # Clean up resources
        crawler_manager.close()

if __name__ == "__main__":
    # When run directly, use the default fixtures
    project_root = Path(__file__).parent.parent.parent
    input_file = os.path.join(project_root, "data", "fixtures", "Loans_without_Clips.csv")
    run_ingest(input_file) 