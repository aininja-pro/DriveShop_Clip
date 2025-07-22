# Browser Refresh and Session Persistence

## The Issue
When you refresh the browser (F5 or Cmd+R), Streamlit clears its `session_state`, which logs you out. This is a known limitation of Streamlit's architecture.

## Why This Happens
- Streamlit's `session_state` is stored in memory on the server
- Browser refresh creates a new WebSocket connection
- Streamlit treats this as a new session, clearing the state

## Current Behavior
- **In-app refresh** (using Streamlit's rerun): Session persists ✅
- **Browser refresh** (F5/Cmd+R): Session is lost ❌

## Workarounds

### 1. Use the Built-in Refresh (Recommended)
Instead of browser refresh, use:
- The "Rerun" menu in Streamlit (top right menu → Rerun)
- Any button click or interaction that triggers `st.rerun()`
- The app's internal navigation

### 2. Bookmark the Dashboard
After logging in, bookmark the dashboard URL. This reduces the need for refresh.

### 3. Keep the Tab Open
The 48-hour session timeout means you can keep the tab open for 2 days without re-login.

## Permanent Solutions (Future Enhancement)

### Option 1: JWT in URL Parameters
Store a JWT token in URL query parameters, but this has security implications.

### Option 2: External Session Store
Use Redis or another session store, but this adds infrastructure complexity.

### Option 3: Cookie-Based Authentication
Implement proper cookie management, but Streamlit has limited cookie support.

### Option 4: Switch to a Traditional Web Framework
For production apps requiring true session persistence, consider:
- FastAPI + Frontend framework
- Django
- Flask

## For Now
The current implementation is suitable for the MVP. Users should:
1. Avoid browser refresh
2. Use the app's internal navigation
3. Keep the tab open (48-hour timeout is generous)

## Note for Production
If browser refresh becomes a critical issue for users, consider implementing one of the permanent solutions above, with JWT in URL parameters being the quickest to implement (though with security trade-offs).