import os
import json
import requests
from typing import Dict, Any, Optional
import time
from dotenv import load_dotenv
from pathlib import Path

# Get logger
from src.utils.logger import setup_logger
logger = setup_logger(__name__)

def load_slack_webhook():
    """Load Slack webhook URL from environment variables"""
    load_dotenv()
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL environment variable not found")
    
    return webhook_url

def send_slack_message(
    message: str, 
    webhook_url: Optional[str] = None, 
    max_retries: int = 3
) -> bool:
    """
    Send a notification message to Slack.
    
    Args:
        message: The message text to send
        webhook_url: Slack webhook URL (defaults to SLACK_WEBHOOK_URL env var)
        max_retries: Maximum number of retry attempts
        
    Returns:
        True if the message was sent successfully, False otherwise
    """
    # Skip sending if in development mode and no webhook is set
    if not webhook_url:
        webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
        
    if not webhook_url:
        logger.warning("No Slack webhook URL provided. Skipping notification.")
        return False
    
    payload = {
        "text": message
    }
    
    # Add emoji and better formatting if it's a status message
    if message.startswith('✅') or message.startswith('❌'):
        payload["blocks"] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]
    
    # Try sending with exponential backoff
    for attempt in range(max_retries):
        try:
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info("Slack notification sent successfully")
                return True
            else:
                logger.warning(f"Failed to send Slack notification. Status: {response.status_code}, Response: {response.text}")
                
                # Exponential backoff before retry
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            
            # Exponential backoff before retry
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
    
    # If we get here, all retries failed
    logger.error(f"Failed to send Slack notification after {max_retries} attempts")
    return False 