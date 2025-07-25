"""
Session persistence utilities for maintaining authentication across browser refreshes.
Uses cookies to store session tokens securely.
"""

import streamlit as st
from streamlit.components.v1 import html
import json
import base64
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import os

class SessionPersistence:
    """Handle session persistence using browser storage."""
    
    def __init__(self):
        self.cookie_name = "driveshop_session"
        self.cookie_expiry_days = 2  # 48 hours
        
    def set_session_cookie(self, session_data: Dict[str, Any]) -> None:
        """Store session data in a secure cookie."""
        try:
            # Create a session identifier
            session_id = self._generate_session_id()
            
            # Store essential session data
            cookie_data = {
                'session_id': session_id,
                'access_token': session_data.get('access_token', ''),
                'refresh_token': session_data.get('refresh_token', ''),
                'expires_at': session_data.get('expires_at', 0),
                'user_id': session_data.get('user', {}).get('id', ''),
                'timestamp': datetime.now().isoformat()
            }
            
            # Encode the cookie data
            cookie_value = base64.b64encode(
                json.dumps(cookie_data).encode('utf-8')
            ).decode('utf-8')
            
            # Set cookie using JavaScript
            js_code = f"""
            <script>
                // Set secure cookie with appropriate flags
                const expiryDate = new Date();
                expiryDate.setDate(expiryDate.getDate() + {self.cookie_expiry_days});
                
                document.cookie = "{self.cookie_name}={cookie_value}; " +
                    "expires=" + expiryDate.toUTCString() + "; " +
                    "path=/; " +
                    "SameSite=Strict; " +
                    (window.location.protocol === 'https:' ? "Secure; " : "");
                    
                // Also store in sessionStorage for immediate access
                sessionStorage.setItem('{self.cookie_name}', '{cookie_value}');
            </script>
            """
            html(js_code, height=0)
            
            # Also store in Streamlit session state
            st.session_state['persisted_session'] = cookie_data
            
        except Exception as e:
            print(f"Error setting session cookie: {e}")
    
    def get_session_cookie(self) -> Optional[Dict[str, Any]]:
        """Retrieve session data from cookie."""
        try:
            # First check Streamlit session state
            if 'persisted_session' in st.session_state:
                return st.session_state['persisted_session']
            
            # Try to get from query params (set by JavaScript)
            if 'session_data' in st.query_params:
                encoded_data = st.query_params['session_data']
                decoded_data = json.loads(
                    base64.b64decode(encoded_data).decode('utf-8')
                )
                
                # Validate timestamp
                timestamp = datetime.fromisoformat(decoded_data.get('timestamp', ''))
                if datetime.now() - timestamp > timedelta(days=self.cookie_expiry_days):
                    return None
                
                return decoded_data
            
            # Use JavaScript to read cookie and pass it back
            js_code = f"""
            <script>
                function getCookie(name) {{
                    const value = `; ${{document.cookie}}`;
                    const parts = value.split(`; ${{name}}=`);
                    if (parts.length === 2) return parts.pop().split(';').shift();
                    return null;
                }}
                
                // Try cookie first, then sessionStorage
                let sessionData = getCookie('{self.cookie_name}');
                if (!sessionData) {{
                    sessionData = sessionStorage.getItem('{self.cookie_name}');
                }}
                
                if (sessionData) {{
                    // Redirect with session data in query params
                    const currentUrl = new URL(window.location.href);
                    currentUrl.searchParams.set('session_data', sessionData);
                    window.location.href = currentUrl.toString();
                }}
            </script>
            """
            html(js_code, height=0)
            
            return None
            
        except Exception as e:
            print(f"Error getting session cookie: {e}")
            return None
    
    def clear_session_cookie(self) -> None:
        """Clear the session cookie."""
        try:
            js_code = f"""
            <script>
                // Clear cookie
                document.cookie = "{self.cookie_name}=; " +
                    "expires=Thu, 01 Jan 1970 00:00:00 UTC; " +
                    "path=/; " +
                    "SameSite=Strict; " +
                    (window.location.protocol === 'https:' ? "Secure; " : "");
                
                // Clear sessionStorage
                sessionStorage.removeItem('{self.cookie_name}');
                
                // Clear query params
                const currentUrl = new URL(window.location.href);
                currentUrl.searchParams.delete('session_data');
                window.history.replaceState({{}}, '', currentUrl.toString());
            </script>
            """
            html(js_code, height=0)
            
            # Clear from session state
            if 'persisted_session' in st.session_state:
                del st.session_state['persisted_session']
                
        except Exception as e:
            print(f"Error clearing session cookie: {e}")
    
    def _generate_session_id(self) -> str:
        """Generate a unique session identifier."""
        data = f"{datetime.now().isoformat()}-{os.urandom(16).hex()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    def store_session_server_side(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """
        Store session data server-side (e.g., in Redis or database).
        This is more secure than client-side storage.
        """
        # TODO: Implement server-side session storage
        # For now, we're using client-side storage with cookies
        pass
    
    def retrieve_session_server_side(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data from server-side storage.
        """
        # TODO: Implement server-side session retrieval
        # For now, we're using client-side storage with cookies
        return None