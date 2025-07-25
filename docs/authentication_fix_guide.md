# Authentication Session Persistence Fix Guide

## Problem Summary
Users were being logged out randomly despite having `SESSION_TIMEOUT_HOURS=48` configured. The main issues were:

1. **Session Loss on Browser Refresh**: Streamlit's `st.session_state` is cleared on every browser refresh
2. **Broken Session Restoration**: The `_restore_session()` method always returned `False`
3. **No Session Persistence**: No mechanism to persist sessions across page reloads
4. **Supabase Python SDK Limitation**: Unlike the JavaScript SDK, the Python SDK doesn't persist sessions

## Solutions Implemented

### 1. Fixed the Immediate Issue
Updated `src/utils/auth.py` to properly restore sessions from Supabase instead of always returning `False`.

### 2. Added Session Persistence Mechanisms

#### Option A: Cookie-Based Persistence (`session_persistence.py`)
- Stores session tokens in secure browser cookies
- Uses JavaScript to set/get cookies
- Persists for 48 hours
- More complex but works across all scenarios

#### Option B: Query Parameter Persistence (`simple_session_persistence.py`)
- Stores session in URL query parameters
- Uses HMAC signatures for security
- Simpler implementation
- Works well with Streamlit's architecture

### 3. Created Improved Auth Module (`auth_improved.py`)
- Comprehensive session management
- Automatic session restoration on page refresh
- Proper token refresh logic
- Fallback mechanisms for expired tokens

## How to Apply the Fix

### Quick Fix (Minimal Changes)
The quickest fix is already applied to `src/utils/auth.py`. This will significantly reduce logout issues.

### Recommended Fix (Better Persistence)
1. Replace the import in `src/dashboard/app.py`:
   ```python
   # Change from:
   from src.utils.auth import SupabaseAuth
   
   # To:
   from src.utils.auth_improved import ImprovedSupabaseAuth as SupabaseAuth
   ```

2. Add session secret to `.env`:
   ```
   SESSION_SECRET=your-secret-key-here-change-this
   ```

### Advanced Fix (For Production)
For production environments, consider:

1. **Server-Side Sessions**: Use Redis or a database to store sessions server-side
2. **Supabase Auth Helpers**: Use official Streamlit-Supabase connectors
3. **JWT Configuration**: Ensure Supabase JWT settings match your timeout requirements

## Additional Recommendations

### 1. Configure Supabase Project Settings
In your Supabase dashboard:
- Go to Authentication > Settings
- Set JWT expiry to at least 48 hours
- Set refresh token expiry to 30+ days

### 2. Handle Long-Running Operations
For operations that take 2+ hours:
```python
# Before starting long operation
auth.refresh_session()

# During operation (every 30 minutes)
if not auth.refresh_session():
    # Save progress and notify user
    st.error("Session expired. Please log in again.")
    st.stop()
```

### 3. Add Session Monitoring
```python
# Add to your dashboard
if auth.is_authenticated():
    session = auth.get_session()
    if session:
        expires_at = session.get('expires_at', 0)
        expires_in = expires_at - time.time()
        if expires_in < 3600:  # Less than 1 hour
            st.warning(f"Session expires in {expires_in // 60} minutes")
```

### 4. Environment Variables
Ensure these are set in your `.env`:
```
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-anon-key
SESSION_TIMEOUT_HOURS=48
SESSION_SECRET=your-secret-key
```

## Testing the Fix

1. **Test Browser Refresh**:
   - Log in to the dashboard
   - Refresh the browser (F5)
   - Should remain logged in

2. **Test Long Session**:
   - Log in and note the time
   - Keep the tab open for 2+ hours
   - Should remain logged in

3. **Test Token Refresh**:
   - Log in
   - Wait for access token to expire (usually 1 hour)
   - Perform an action
   - Should automatically refresh

## Troubleshooting

If users still experience logouts:

1. **Check Browser Console**: Look for JavaScript errors
2. **Check Python Logs**: Look for "Session restoration error" messages
3. **Verify Supabase Settings**: Ensure JWT settings are correct
4. **Clear Browser Data**: Sometimes old cookies cause issues
5. **Check Network**: Ensure stable connection to Supabase

## Long-Term Improvements

1. **Implement WebSocket Keep-Alive**: For real-time session monitoring
2. **Add Session Extension UI**: Let users extend sessions before expiry
3. **Background Token Refresh**: Refresh tokens automatically in background
4. **Session Analytics**: Track session durations and timeout patterns

## Additional Resources

- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth)
- [Streamlit Session State](https://docs.streamlit.io/library/api-reference/session-state)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)