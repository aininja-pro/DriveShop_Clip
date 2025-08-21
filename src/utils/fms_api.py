"""
FMS API client for sending approved clips to the FMS system.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
import requests
from datetime import datetime

# Set up more visible logging for FMS API
logger = logging.getLogger(__name__)
# Ensure FMS API logs are visible
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('FMS_API: %(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class FMSAPIClient:
    """Client for interacting with the FMS API."""
    
    def __init__(self):
        """Initialize the FMS API client with environment variables."""
        print("🔥 FMS_INIT: Starting FMS API client initialization...")
        
        self.token = os.getenv("FMS_API_TOKEN")
        self.environment = os.getenv("FMS_API_ENVIRONMENT", "staging")
        
        print(f"🔥 FMS_INIT: Environment: {self.environment}")
        print(f"🔥 FMS_INIT: Token present: {bool(self.token)}")
        
        if self.environment == "production":
            self.api_url = os.getenv("FMS_API_PRODUCTION_URL")
        else:
            self.api_url = os.getenv("FMS_API_STAGING_URL")
            
        print(f"🔥 FMS_INIT: API URL: {self.api_url}")
            
        if not self.token:
            print("🔥 FMS_INIT: ERROR - No token found!")
            raise ValueError("FMS_API_TOKEN environment variable not set")
        if not self.api_url:
            print(f"🔥 FMS_INIT: ERROR - No API URL for {self.environment}!")
            raise ValueError(f"FMS API URL not configured for {self.environment} environment")
            
        print("🔥 FMS_INIT: Initialization complete!")
            
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
        print(f"🔥 FMS_PAYLOAD: Prepared payload with {len(clips)} clips")
        
        try:
            print(f"🚀 FMS_API: Sending {len(clips)} clips to FMS API ({self.environment})")
            print(f"🚀 FMS_API: API URL: {self.api_url}")
            print(f"🚀 FMS_API: Sample clip data: {json.dumps(clips[0] if clips else {}, indent=2)}")
            
            logger.info(f"Sending {len(clips)} clips to FMS API ({self.environment})")
            logger.info(f"API URL: {self.api_url}")
            logger.info(f"Sample clip data: {json.dumps(clips[0] if clips else {}, indent=2)}")
            logger.debug(f"Full payload: {json.dumps(payload, indent=2, default=str)}")
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            # Log response details (both print and logger for visibility)
            print(f"🔄 FMS_API: Response Status: {response.status_code}")
            print(f"🔄 FMS_API: Response Text: {response.text[:500]}...")  # First 500 chars
            
            logger.info(f"FMS API Response Status: {response.status_code}")
            logger.info(f"FMS API Response: {response.text}")
            
            if response.status_code == 200 or response.status_code == 201:
                print(f"✅ FMS_API: SUCCESS - Status {response.status_code}")
                # Parse the actual response to get accurate counts
                response_data = {}
                actual_sent_count = len(clips)  # Default assumption
                
                try:
                    if response.text:
                        response_data = response.json()
                        # Check if FMS API returns specific success info
                        if isinstance(response_data, dict):
                            # Look for various possible response formats
                            if 'successful_count' in response_data:
                                actual_sent_count = response_data['successful_count']
                            elif 'processed' in response_data:
                                actual_sent_count = response_data['processed']
                            elif 'clips_received' in response_data:
                                actual_sent_count = response_data['clips_received']
                            elif 'success_count' in response_data:
                                actual_sent_count = response_data['success_count']
                            # If response contains individual clip results
                            elif 'results' in response_data and isinstance(response_data['results'], list):
                                successful_clips = [r for r in response_data['results'] if r.get('success', False)]
                                actual_sent_count = len(successful_clips)
                except Exception as e:
                    logger.warning(f"Could not parse FMS response JSON: {e}")
                    # Keep default assumption
                
                print(f"✅ FMS_API: Processed {actual_sent_count} of {len(clips)} clips successfully")
                logger.info(f"FMS API response: {actual_sent_count} of {len(clips)} clips processed successfully")
                
                return {
                    "success": True,
                    "message": f"FMS API processed {actual_sent_count} of {len(clips)} clips",
                    "sent_count": actual_sent_count,
                    "requested_count": len(clips),
                    "response_status": response.status_code,
                    "response_data": response_data,
                    "all_clips_sent": actual_sent_count == len(clips)
                }
            else:
                error_msg = f"FMS API returned status {response.status_code}"
                if response.text:
                    error_msg += f": {response.text}"
                print(f"❌ FMS_API: ERROR - {error_msg}")
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
            print(f"🔥 FMS_TIMEOUT: {error_msg}")
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "sent_count": 0
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"FMS API request failed: {str(e)}"
            print(f"🔥 FMS_REQUEST_ERROR: {error_msg}")
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "sent_count": 0
            }
        except Exception as e:
            error_msg = f"Unexpected error sending to FMS API: {str(e)}"
            print(f"🔥 FMS_UNEXPECTED_ERROR: {error_msg}")
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
        
    def get_current_token(self) -> str:
        """
        Get the current token (useful for manual environment updates).
        
        Returns:
            Current token string
        """
        return self.token
        
    def rotate_token(self) -> Dict[str, Any]:
        """
        Rotate the FMS API token using the new rotate-token endpoint.
        
        Returns:
            Dict with rotation results including new token
        """
        try:
            if self.environment == "production":
                rotate_url = os.getenv("FMS_API_PRODUCTION_URL", "").replace("/clips", "/rotate-token")
            else:
                rotate_url = os.getenv("FMS_API_STAGING_URL", "").replace("/clips", "/rotate-token")
            
            if not rotate_url or "/rotate-token" not in rotate_url:
                return {
                    "success": False,
                    "error": "Could not determine rotate-token endpoint URL"
                }
            
            print(f"🔄 FMS_TOKEN_ROTATION: Requesting new token from {rotate_url}")
            logger.info(f"Rotating FMS token using endpoint: {rotate_url}")
            
            response = requests.post(
                rotate_url,
                headers=self.headers,
                timeout=30
            )
            
            print(f"🔄 FMS_TOKEN_ROTATION: Response Status: {response.status_code}")
            logger.info(f"Token rotation response status: {response.status_code}")
            
            if response.status_code == 200:
                new_token = response.headers.get("Token")
                if new_token:
                    print(f"✅ FMS_TOKEN_ROTATION: New token received")
                    logger.info("Token rotation successful - new token received")
                    
                    # Update the instance token
                    self.token = new_token
                    self.headers["Authorization"] = f"Token {new_token}"
                    
                    # Log token rotation for manual environment updates
                    print(f"🔑 NEW_TOKEN_FOR_ENV: {new_token}")
                    print(f"🔑 UPDATE_RENDER: Set FMS_API_TOKEN={new_token} in Render environment variables")
                    logger.critical(f"TOKEN_ROTATION: New token for {self.environment}: {new_token}")
                    logger.critical(f"ACTION_REQUIRED: Update Render environment variable FMS_API_TOKEN={new_token}")
                    
                    return {
                        "success": True,
                        "message": "Token rotated successfully",
                        "new_token": new_token,
                        "environment": self.environment,
                        "action_required": f"Update Render environment: FMS_API_TOKEN={new_token}"
                    }
                else:
                    error_msg = "Token rotation succeeded but no new token in response header"
                    print(f"❌ FMS_TOKEN_ROTATION: {error_msg}")
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "response_headers": dict(response.headers)
                    }
            else:
                error_msg = f"Token rotation failed with status {response.status_code}: {response.text}"
                print(f"❌ FMS_TOKEN_ROTATION: {error_msg}")
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "response_status": response.status_code
                }
                
        except Exception as e:
            error_msg = f"Token rotation failed: {str(e)}"
            print(f"❌ FMS_TOKEN_ROTATION: {error_msg}")
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
    
    def send_clips_with_retry(self, clips: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
        """
        Send clips to FMS API with automatic token rotation retry on auth failure.
        
        Args:
            clips: List of clip dictionaries in FMS format
            dry_run: If True, validate data without sending to API
            
        Returns:
            Dict with results including success status and any errors
        """
        # First attempt
        result = self.send_clips(clips, dry_run)
        
        # If auth failed (401), try rotating token and retry once
        if not result["success"] and result.get("response_status") == 401:
            print("🔄 FMS_AUTO_RETRY: Auth failed, attempting token rotation...")
            logger.info("Authentication failed, attempting automatic token rotation")
            
            rotation_result = self.rotate_token()
            if rotation_result["success"]:
                print("🔄 FMS_AUTO_RETRY: Token rotated, retrying clip submission...")
                logger.info("Token rotation successful, retrying clip submission")
                
                # Retry with new token
                retry_result = self.send_clips(clips, dry_run)
                if retry_result["success"]:
                    retry_result["token_rotated"] = True
                    retry_result["new_token"] = rotation_result["new_token"]
                    retry_result["action_required"] = rotation_result["action_required"]
                return retry_result
            else:
                print("❌ FMS_AUTO_RETRY: Token rotation failed")
                logger.error("Automatic token rotation failed")
                result["token_rotation_attempted"] = True
                result["token_rotation_error"] = rotation_result["error"]
        
        return result

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