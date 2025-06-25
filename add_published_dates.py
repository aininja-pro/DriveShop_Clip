#!/usr/bin/env python3
"""
Script to add published dates to existing loan_results.csv
This extracts published dates from the URLs we already found without reprocessing everything.
"""

import csv
import sys
import os
from datetime import datetime
from src.utils.date_extractor import extract_date_from_html
from src.utils.enhanced_http import fetch_with_enhanced_http
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def extract_published_date_from_url(url, content_type='article'):
    """Extract published date from a URL"""
    try:
        if 'youtube.com' in url or 'youtu.be' in url:
            # For YouTube videos, we'd need to use the YouTube API
            # For now, return None - we can enhance this later
            logger.info(f"YouTube URL detected, skipping date extraction: {url}")
            return None
        
        # Make request to get the HTML content
        logger.info(f"Fetching content from: {url}")
        content = fetch_with_enhanced_http(url)
        
        if not content:
            logger.warning(f"No content retrieved from: {url}")
            return None
        
        # Extract date from HTML content
        published_date = extract_date_from_html(content, url)
        
        if published_date:
            logger.info(f"Found published date {published_date} for: {url}")
            return published_date.strftime('%Y-%m-%d')
        else:
            logger.warning(f"No published date found for: {url}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting date from {url}: {str(e)}")
        return None

def add_published_dates_to_csv(input_file='data/loan_results.csv', output_file='data/loan_results_with_dates.csv'):
    """Add published dates to existing loan results CSV"""
    
    if not os.path.exists(input_file):
        logger.error(f"Input file not found: {input_file}")
        return False
    
    processed_count = 0
    found_dates_count = 0
    
    try:
        # Read existing data
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            rows = list(reader)
            fieldnames = reader.fieldnames
        
        # Add Published Date column if not exists
        if 'Published Date' not in fieldnames:
            fieldnames.append('Published Date')
        
        logger.info(f"Processing {len(rows)} records...")
        
        # Process each row
        for i, row in enumerate(rows):
            clip_url = row.get('Clip URL', '').strip()
            
            if not clip_url or clip_url.startswith('http') == False:
                logger.info(f"Row {i+1}: No valid URL, skipping")
                row['Published Date'] = ''
                continue
            
            logger.info(f"Row {i+1}/{len(rows)}: Processing {clip_url}")
            
            # Extract published date
            published_date = extract_published_date_from_url(clip_url)
            row['Published Date'] = published_date or ''
            
            if published_date:
                found_dates_count += 1
                logger.info(f"✅ Found date: {published_date}")
            else:
                logger.info(f"❌ No date found")
            
            processed_count += 1
            
            # Save progress every 10 records
            if processed_count % 10 == 0:
                logger.info(f"Progress: {processed_count}/{len(rows)} processed, {found_dates_count} dates found")
        
        # Write updated data
        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        logger.info(f"✅ Complete! Processed {processed_count} records, found {found_dates_count} published dates")
        logger.info(f"Updated file saved as: {output_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        return False

if __name__ == "__main__":
    print("🗓️  Adding Published Dates to Existing Loan Results")
    print("=" * 50)
    
    # Run the processing
    success = add_published_dates_to_csv()
    
    if success:
        print("\n✅ Successfully added published dates!")
        print("📁 Check data/loan_results_with_dates.csv for the updated file")
        print("\n💡 To replace your original file:")
        print("   mv data/loan_results_with_dates.csv data/loan_results.csv")
    else:
        print("\n❌ Failed to add published dates")
        sys.exit(1) 