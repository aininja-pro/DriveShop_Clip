"""
Improved authentication module with better session persistence.
This version handles browser refreshes properly.
"""

import streamlit as st
from supabase import create_client, Client
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from .simple_session_persistence import SimpleSessionPersistence

class ImprovedSupabaseAuth:
    def __init__(self):
        self.supabase: Client = create_client(
            os.environ.get("SUPABASE_URL", ""),
            os.environ.get("SUPABASE_ANON_KEY", "")
        )
        self.session_persistence = SimpleSessionPersistence()
        
        # Initialize session state if not already done
        if 'auth_initialized' not in st.session_state:
            st.session_state['auth_initialized'] = True
            st.session_state['authenticated'] = False
            st.session_state['user'] = None
            st.session_state['session'] = None
            st.session_state['login_time'] = None
            
            # Try to restore session on initialization
            self._restore_session()
    
    def login(self, email: str, password: str) -> tuple[bool, Optional[str]]:
        """Login user with email and password."""
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response and response.user and response.session:
                # Update session state
                st.session_state['authenticated'] = True
                st.session_state['user'] = response.user
                st.session_state['session'] = response.session
                st.session_state['login_time'] = datetime.now()
                
                # Persist session
                self.session_persistence.store_session(response.session)
                
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
        """Logout the current user."""
        try:
            # Sign out from Supabase
            self.supabase.auth.sign_out()
            
            # Clear session state
            st.session_state['authenticated'] = False
            st.session_state['user'] = None
            st.session_state['session'] = None
            st.session_state['login_time'] = None
            
            # Clear persisted session
            self.session_persistence.clear_session()
            
        except Exception as e:
            print(f"Logout error: {e}")
            # Still clear local state even if Supabase sign out fails
            st.session_state['authenticated'] = False
            st.session_state['user'] = None
            st.session_state['session'] = None
            self.session_persistence.clear_session()
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        # First check session state
        if st.session_state.get('authenticated', False):
            return True
            
        # Try to restore session if not in session state
        return self._restore_session()
    
    def get_current_user(self) -> Optional[Dict[Any, Any]]:
        """Get the current authenticated user."""
        return st.session_state.get('user', None)
    
    def refresh_session(self) -> bool:
        """Refresh the Supabase session using the refresh token."""
        try:
            # Get current session
            session = st.session_state.get('session')
            if not session:
                # Try to get from persisted session
                persisted = self.session_persistence.retrieve_session()
                if persisted:
                    session = {
                        'refresh_token': persisted.get('refresh_token')
                    }
            
            if session and session.get('refresh_token'):
                # Refresh the session
                response = self.supabase.auth.refresh_session(session['refresh_token'])
                
                if response and response.session:
                    # Update session state
                    st.session_state['session'] = response.session
                    st.session_state['user'] = response.user
                    st.session_state['authenticated'] = True
                    st.session_state['login_time'] = datetime.now()
                    
                    # Persist the refreshed session
                    self.session_persistence.store_session(response.session)
                    
                    return True
                    
            return False
            
        except Exception as e:
            print(f"Session refresh error: {e}")
            return False
    
    def check_and_refresh_session(self, session_timeout_hours: int = 48) -> bool:
        """
        Check if the session is still valid and refresh if needed.
        
        Args:
            session_timeout_hours: Number of hours before requiring a session refresh
            
        Returns:
            True if session is valid or successfully refreshed, False if user needs to log in again
        """
        # First, check if authenticated
        if not self.is_authenticated():
            return False
            
        # Check if we need to refresh based on time
        login_time = st.session_state.get('login_time')
        if login_time:
            time_since_login = datetime.now() - login_time
            if time_since_login > timedelta(hours=session_timeout_hours):
                # Try to refresh
                if not self.refresh_session():
                    self.logout()
                    return False
        
        # Also check if the session is still valid with Supabase
        try:
            user = self.supabase.auth.get_user()
            if not user or not user.user:
                # Session is invalid, try to refresh
                if not self.refresh_session():
                    self.logout()
                    return False
        except Exception as e:
            print(f"Session validation error: {e}")
            # Try to refresh
            if not self.refresh_session():
                self.logout()
                return False
                
        return True
    
    def _restore_session(self) -> bool:
        """
        Restore session from persisted storage or Supabase.
        This handles browser refreshes properly.
        """
        try:
            # First try to restore from persisted session
            persisted = self.session_persistence.retrieve_session()
            if persisted:
                access_token = persisted.get('access_token')
                refresh_token = persisted.get('refresh_token')
                
                if access_token and refresh_token:
                    try:
                        # Set the session in Supabase client
                        self.supabase.auth.set_session(access_token, refresh_token)
                        
                        # Verify the session is valid
                        user = self.supabase.auth.get_user()
                        if user and user.user:
                            # Get the current session details
                            session = self.supabase.auth.get_session()
                            if session and session.session:
                                # Update session state
                                st.session_state['authenticated'] = True
                                st.session_state['user'] = user.user
                                st.session_state['session'] = session.session
                                st.session_state['login_time'] = datetime.now()
                                
                                # Update persisted session with fresh data
                                self.session_persistence.store_session(session.session)
                                
                                return True
                    except Exception as e:
                        print(f"Failed to restore session from tokens: {e}")
                        # Try to refresh if access token is expired
                        if refresh_token:
                            try:
                                response = self.supabase.auth.refresh_session(refresh_token)
                                if response and response.session:
                                    # Update everything with new session
                                    st.session_state['authenticated'] = True
                                    st.session_state['user'] = response.user
                                    st.session_state['session'] = response.session
                                    st.session_state['login_time'] = datetime.now()
                                    
                                    # Persist the new session
                                    self.session_persistence.store_session(response.session)
                                    
                                    return True
                            except Exception as refresh_error:
                                print(f"Failed to refresh expired session: {refresh_error}")
            
            # If no persisted session or it failed, check with Supabase directly
            try:
                session = self.supabase.auth.get_session()
                if session and session.session:
                    user = self.supabase.auth.get_user()
                    if user and user.user:
                        # Valid session found
                        st.session_state['authenticated'] = True
                        st.session_state['user'] = user.user
                        st.session_state['session'] = session.session
                        st.session_state['login_time'] = datetime.now()
                        
                        # Persist it for next time
                        self.session_persistence.store_session(session.session)
                        
                        return True
            except Exception:
                pass
            
            return False
            
        except Exception as e:
            print(f"Session restoration error: {e}")
            return False
    
    def get_session(self) -> Optional[Dict[Any, Any]]:
        """Get the current session from Supabase."""
        try:
            session = self.supabase.auth.get_session()
            return session.session if session else None
        except Exception:
            return None