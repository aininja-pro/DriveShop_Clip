import streamlit as st
from supabase import create_client, Client
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

class SupabaseAuth:
    def __init__(self):
        self.supabase: Client = create_client(
            os.environ.get("SUPABASE_URL", ""),
            os.environ.get("SUPABASE_ANON_KEY", "")
        )
        # Try to restore session on initialization
        self._restore_session()
    
    def login(self, email: str, password: str) -> tuple[bool, Optional[str]]:
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                st.session_state['authenticated'] = True
                st.session_state['user'] = response.user
                st.session_state['session'] = response.session
                # Store login timestamp for session management
                st.session_state['login_time'] = datetime.now()
                return True, None
            else:
                return False, "Invalid credentials"
                
        except Exception as e:
            error_message = str(e)
            if "Invalid login credentials" in error_message:
                return False, "Invalid email or password"
            else:
                return False, f"Login error: {error_message}"
    
    def logout(self):
        try:
            self.supabase.auth.sign_out()
            st.session_state['authenticated'] = False
            st.session_state['user'] = None
            st.session_state['session'] = None
        except Exception as e:
            print(f"Logout error: {e}")
    
    def is_authenticated(self) -> bool:
        return st.session_state.get('authenticated', False)
    
    def get_current_user(self) -> Optional[Dict[Any, Any]]:
        return st.session_state.get('user', None)
    
    def refresh_session(self) -> bool:
        """
        Refresh the Supabase session using the refresh token.
        Returns True if refresh was successful, False otherwise.
        """
        try:
            # First try to get session from session state
            if 'session' in st.session_state and st.session_state['session']:
                current_session = st.session_state['session']
                refresh_token = current_session.get('refresh_token')
            else:
                # Try to get session directly from Supabase
                session_response = self.supabase.auth.get_session()
                if not session_response or not session_response.session:
                    return False
                refresh_token = session_response.session.refresh_token
            
            if refresh_token:
                # Use the refresh token to get a new session
                response = self.supabase.auth.refresh_session(refresh_token)
                
                if response and response.session:
                    # Update the session in session state
                    st.session_state['session'] = response.session
                    st.session_state['user'] = response.user
                    st.session_state['authenticated'] = True
                    st.session_state['login_time'] = datetime.now()
                    return True
                    
            return False
        except Exception as e:
            print(f"Session refresh error: {e}")
            # Try to restore session as a fallback
            return self._restore_session()
    
    def check_and_refresh_session(self, session_timeout_hours: int = 24) -> bool:
        """
        Check if the session is still valid and refresh if needed.
        
        Args:
            session_timeout_hours: Number of hours before requiring a session refresh (default: 24)
            
        Returns:
            True if session is valid or successfully refreshed, False if user needs to log in again
        """
        # First, try to restore session if not authenticated (handles browser refresh)
        if not self.is_authenticated():
            if not self._restore_session():
                return False
            
        # Check if we have a login time
        login_time = st.session_state.get('login_time')
        if not login_time:
            # No login time recorded, assume session is valid
            st.session_state['login_time'] = datetime.now()
            return True
            
        # Check if session has exceeded the timeout
        time_since_login = datetime.now() - login_time
        if time_since_login > timedelta(hours=session_timeout_hours):
            # Try to refresh the session
            if self.refresh_session():
                return True
            else:
                # Refresh failed, user needs to log in again
                self.logout()
                return False
                
        return True
    
    def _restore_session(self) -> bool:
        """
        Restore session from Supabase's stored session (if available).
        This handles browser refreshes by checking if there's an active session.
        """
        try:
            # Try to get the current session from Supabase
            session_response = self.supabase.auth.get_session()
            
            if session_response and session_response.session:
                # Validate that the session is still valid
                user = self.supabase.auth.get_user()
                if user and user.user:
                    # Restore session to Streamlit state
                    st.session_state['authenticated'] = True
                    st.session_state['user'] = user.user
                    st.session_state['session'] = session_response.session
                    st.session_state['login_time'] = datetime.now()
                    return True
            
            return False
        except Exception as e:
            print(f"Session restoration error: {e}")
            return False
    
    def get_session(self) -> Optional[Dict[Any, Any]]:
        """Get the current session from Supabase."""
        try:
            session = self.supabase.auth.get_session()
            return session
        except Exception:
            return None