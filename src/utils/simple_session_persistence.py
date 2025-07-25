"""
Simpler session persistence using Streamlit's query parameters.
This is a more straightforward approach that doesn't require JavaScript.
"""

import streamlit as st
import json
import base64
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hmac
import hashlib
import os

class SimpleSessionPersistence:
    """Handle session persistence using URL query parameters."""
    
    def __init__(self):
        self.param_name = "auth_session"
        self.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key-change-this")
        
    def store_session(self, session_data: Dict[str, Any]) -> None:
        """Store session data in URL query parameters."""
        try:
            # Create session payload
            # Handle both dict and Session object formats
            if hasattr(session_data, 'access_token'):
                # It's a Session object
                payload = {
                    'access_token': getattr(session_data, 'access_token', ''),
                    'refresh_token': getattr(session_data, 'refresh_token', ''),
                    'expires_at': getattr(session_data, 'expires_at', 0),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                # It's a dict
                payload = {
                    'access_token': session_data.get('access_token', ''),
                    'refresh_token': session_data.get('refresh_token', ''),
                    'expires_at': session_data.get('expires_at', 0),
                    'timestamp': datetime.now().isoformat()
                }
            
            # Create signature for security
            payload_str = json.dumps(payload, sort_keys=True)
            signature = self._create_signature(payload_str)
            
            # Combine payload and signature
            signed_payload = {
                'data': payload_str,
                'signature': signature
            }
            
            # Encode for URL
            encoded = base64.urlsafe_b64encode(
                json.dumps(signed_payload).encode('utf-8')
            ).decode('utf-8')
            
            # Update query parameters
            st.query_params[self.param_name] = encoded
            
        except Exception as e:
            print(f"Error storing session: {e}")
    
    def retrieve_session(self) -> Optional[Dict[str, Any]]:
        """Retrieve session data from URL query parameters."""
        try:
            # Check if we have the session parameter
            if self.param_name not in st.query_params:
                return None
            
            # Decode the parameter
            encoded = st.query_params[self.param_name]
            signed_payload = json.loads(
                base64.urlsafe_b64decode(encoded.encode('utf-8')).decode('utf-8')
            )
            
            # Verify signature
            if not self._verify_signature(signed_payload['data'], signed_payload['signature']):
                print("Session signature verification failed")
                self.clear_session()
                return None
            
            # Parse payload
            payload = json.loads(signed_payload['data'])
            
            # Check timestamp (48 hours expiry)
            timestamp = datetime.fromisoformat(payload['timestamp'])
            if datetime.now() - timestamp > timedelta(hours=48):
                print("Session expired")
                self.clear_session()
                return None
            
            return payload
            
        except Exception as e:
            print(f"Error retrieving session: {e}")
            return None
    
    def clear_session(self) -> None:
        """Clear session from query parameters."""
        try:
            if self.param_name in st.query_params:
                del st.query_params[self.param_name]
        except Exception as e:
            print(f"Error clearing session: {e}")
    
    def _create_signature(self, data: str) -> str:
        """Create HMAC signature for data."""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _verify_signature(self, data: str, signature: str) -> bool:
        """Verify HMAC signature."""
        expected_signature = self._create_signature(data)
        return hmac.compare_digest(expected_signature, signature)