"""
FMS API client for sending approved clips to the FMS system.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class FMSAPIClient:
    """Client for interacting with the FMS API."""
    
    def __init__(self):
        """Initialize the FMS API client with environment variables."""
        self.token = os.getenv("FMS_API_TOKEN")
        self.environment = os.getenv("FMS_API_ENVIRONMENT", "staging")
        
        if self.environment == "production":
            self.api_url = os.getenv("FMS_API_PRODUCTION_URL")
        else:
            self.api_url = os.getenv("FMS_API_STAGING_URL")
            
        if not self.token:
            raise ValueError("FMS_API_TOKEN environment variable not set")
        if not self.api_url:
            raise ValueError(f"FMS API URL not configured for {self.environment} environment")
            
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
        
    def send_clips(self, clips: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
        """
        Send clips to the FMS API.
        
        Args:
            clips: List of clip dictionaries in FMS format
            dry_run: If True, validate data without sending to API
            
        Returns:
            Dict with results including success status and any errors
        """
        if not clips:
            return {
                "success": False,
                "error": "No clips provided",
                "sent_count": 0
            }
            
        # Validate clip data
        validation_errors = self._validate_clips(clips)
        if validation_errors:
            return {
                "success": False,
                "error": "Validation errors found",
                "validation_errors": validation_errors,
                "sent_count": 0
            }
            
        # If dry run, return success without sending
        if dry_run:
            logger.info(f"Dry run: Would send {len(clips)} clips to FMS API")
            return {
                "success": True,
                "message": f"Dry run successful. Would send {len(clips)} clips.",
                "sent_count": len(clips),
                "dry_run": True
            }
            
        # Prepare the payload
        payload = {"clips": clips}
        
        try:
            logger.info(f"Sending {len(clips)} clips to FMS API ({self.environment})")
            logger.debug(f"API URL: {self.api_url}")
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            # Log response details
            logger.info(f"FMS API Response Status: {response.status_code}")
            
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"Successfully sent {len(clips)} clips to FMS")
                return {
                    "success": True,
                    "message": f"Successfully sent {len(clips)} clips to FMS",
                    "sent_count": len(clips),
                    "response_status": response.status_code,
                    "response_data": response.json() if response.text else {}
                }
            else:
                error_msg = f"FMS API returned status {response.status_code}"
                if response.text:
                    error_msg += f": {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "sent_count": 0,
                    "response_status": response.status_code,
                    "response_data": response.text
                }
                
        except requests.exceptions.Timeout:
            error_msg = "FMS API request timed out"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "sent_count": 0
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"FMS API request failed: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "sent_count": 0
            }
        except Exception as e:
            error_msg = f"Unexpected error sending to FMS API: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "sent_count": 0
            }
            
    def _validate_clips(self, clips: List[Dict[str, Any]]) -> List[str]:
        """
        Validate clip data before sending to FMS.
        
        Args:
            clips: List of clip dictionaries
            
        Returns:
            List of validation error messages
        """
        errors = []
        required_fields = ["activity_id", "link"]
        
        for i, clip in enumerate(clips):
            # Check required fields
            for field in required_fields:
                if field not in clip or not clip[field]:
                    errors.append(f"Clip {i+1}: Missing required field '{field}'")
                    
            # Validate data types
            if "activity_id" in clip and not isinstance(clip["activity_id"], (str, int)):
                errors.append(f"Clip {i+1}: 'activity_id' must be a string or integer")
                
            if "link" in clip and not isinstance(clip["link"], str):
                errors.append(f"Clip {i+1}: 'link' must be a string")
                
            # Validate score fields (should be strings or integers)
            score_fields = ["overall_score", "relevance_score"]
            for field in score_fields:
                if field in clip and clip[field] is not None:
                    if not isinstance(clip[field], (str, int)):
                        errors.append(f"Clip {i+1}: '{field}' must be a string or integer")
                        
        return errors
        
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection to the FMS API.
        
        Returns:
            Dict with test results
        """
        try:
            logger.info(f"Testing FMS API connection ({self.environment})")
            
            # Try a simple GET request to the endpoint
            # If GET is not supported, we'll get a 405 which still proves connectivity
            response = requests.get(
                self.api_url,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 405:
                # Method not allowed is expected for a POST-only endpoint
                return {
                    "success": True,
                    "message": "FMS API connection successful (endpoint is POST-only)",
                    "environment": self.environment,
                    "api_url": self.api_url
                }
            elif response.status_code == 200:
                return {
                    "success": True,
                    "message": "FMS API connection successful",
                    "environment": self.environment,
                    "api_url": self.api_url
                }
            else:
                return {
                    "success": False,
                    "error": f"Unexpected status code: {response.status_code}",
                    "environment": self.environment,
                    "api_url": self.api_url
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection test failed: {str(e)}",
                "environment": self.environment,
                "api_url": self.api_url
            }