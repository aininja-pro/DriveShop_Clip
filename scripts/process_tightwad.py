#!/usr/bin/env python3
"""
Special processing script for Tightwad Garage and other rate-limited sites.
Processes work orders one at a time with delays to avoid timeouts.
"""

import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest.ingest_database import run_ingest_database_with_filters
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def process_tightwad_safely(work_orders, delay_between_orders=10):
    """
    Process Tightwad Garage work orders with delays to avoid rate limiting.
    
    Args:
        work_orders: List of work order dictionaries
        delay_between_orders: Seconds to wait between processing each order
    """
    logger.info(f"🚗 Processing {len(work_orders)} Tightwad Garage work orders with {delay_between_orders}s delay")
    
    results = []
    for i, wo in enumerate(work_orders):
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing work order {i+1}/{len(work_orders)}: {wo.get('work_order')}")
        logger.info(f"Vehicle: {wo.get('make')} {wo.get('model')}")
        logger.info(f"{'='*60}\n")
        
        # Process single work order
        success = run_ingest_database_with_filters(
            [wo], 
            run_name=f"Tightwad_{wo.get('work_order')}"
        )
        
        results.append({
            'work_order': wo.get('work_order'),
            'success': success
        })
        
        # Wait before next order (except for last one)
        if i < len(work_orders) - 1:
            logger.info(f"⏱️ Waiting {delay_between_orders}s before next work order...")
            time.sleep(delay_between_orders)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("PROCESSING COMPLETE - SUMMARY:")
    successful = sum(1 for r in results if r['success'])
    logger.info(f"✅ Successful: {successful}/{len(work_orders)}")
    for r in results:
        status = "✅" if r['success'] else "❌"
        logger.info(f"  {status} {r['work_order']}")
    logger.info(f"{'='*60}\n")
    
    return results

if __name__ == "__main__":
    # Example usage
    test_work_orders = [
        {
            'work_order': '1750100055',
            'urls': ['https://tightwadgarage.com'],
            'make': 'Mazda',
            'model': 'CX-70',
            'activity_id': '12345'
        },
        # Add more work orders here
    ]
    
    results = process_tightwad_safely(test_work_orders, delay_between_orders=15)