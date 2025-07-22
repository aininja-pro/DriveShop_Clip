# Authentication Session Timeout Configuration

## Overview
The DriveShop Clip Tracking Dashboard now supports configurable session timeouts for Supabase authentication. This allows you to control how long users stay logged in before needing to re-authenticate.

## Default Behavior
- Default session timeout: **24 hours**
- After the timeout period, the system will attempt to refresh the session automatically
- If refresh fails, users will be redirected to the login page

## Configuration

### 1. Environment Variable
Add or modify the `SESSION_TIMEOUT_HOURS` variable in your `.env` file:

```bash
# Session timeout in hours
SESSION_TIMEOUT_HOURS=48  # 2 days
```

Common timeout values:
- `24` - 1 day (default)
- `48` - 2 days
- `72` - 3 days
- `168` - 1 week
- `336` - 2 weeks
- `720` - 30 days

### 2. Supabase Dashboard Configuration
For the session refresh to work properly, you also need to configure JWT expiry in your Supabase project:

1. Go to your Supabase Dashboard
2. Navigate to **Settings** → **Auth**
3. Under **JWT Configuration**, adjust:
   - **JWT expiry limit**: Set this to match or exceed your `SESSION_TIMEOUT_HOURS`
   - **Refresh token expiry**: Should be longer than JWT expiry (e.g., 30 days)

### 3. Docker Deployment
When using Docker, pass the environment variable:

```bash
docker run -e SESSION_TIMEOUT_HOURS=48 ...
```

Or add to your `docker-compose.yml`:

```yaml
services:
  app:
    environment:
      - SESSION_TIMEOUT_HOURS=48
```

## How It Works

1. **Login**: When users log in, a timestamp is stored in the session
2. **Session Check**: On each page load, the system checks if the session has expired
3. **Auto-Refresh**: If within the timeout period, the session continues normally
4. **Refresh Attempt**: If expired, the system tries to refresh using the refresh token
5. **Re-login**: If refresh fails, users are redirected to login

## Security Considerations

- Longer session timeouts increase convenience but may reduce security
- For sensitive environments, use shorter timeouts (e.g., 8-12 hours)
- Supabase refresh tokens have their own expiry (typically 30 days)
- Sessions are stored client-side in Streamlit's session state

## Troubleshooting

### Users Getting Logged Out Too Quickly
1. Check your `.env` file has the correct `SESSION_TIMEOUT_HOURS` value
2. Verify Supabase JWT expiry settings match your configuration
3. Ensure the Docker container has the latest environment variables

### Session Refresh Failing
1. Check Supabase refresh token expiry settings
2. Verify network connectivity to Supabase
3. Check for any Supabase API rate limits

### Testing Different Timeouts
```bash
# For testing, you can use shorter timeouts
SESSION_TIMEOUT_HOURS=0.5  # 30 minutes
SESSION_TIMEOUT_HOURS=0.083  # 5 minutes
```

## Code Implementation
The session management is implemented in:
- `src/utils/auth.py` - Core authentication logic
- `src/dashboard/app.py` - Session checking on page load