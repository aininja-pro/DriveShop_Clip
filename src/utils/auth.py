import streamlit as st
from supabase import create_client, Client
import os
from typing import Optional, Dict, Any

class SupabaseAuth:
    def __init__(self):
        self.supabase: Client = create_client(
            os.environ.get("SUPABASE_URL", ""),
            os.environ.get("SUPABASE_ANON_KEY", "")
        )
    
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