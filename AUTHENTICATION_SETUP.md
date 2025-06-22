# CreatorIQ Authentication Setup Guide

This guide explains how to set up authentication for the CreatorIQ GraphQL client to access live campaign data.

## 🎯 Overview

The CreatorIQ API requires authentication headers that are automatically sent by your browser when you're logged in. We need to capture these headers and use them in our GraphQL client.

## 📋 Step-by-Step Setup

### Step 1: Log into CreatorIQ

1. Open your browser and go to CreatorIQ
2. Log in with your credentials
3. Navigate to a campaign report (like the Audi campaign)
4. Make sure you can see the posts data loading

### Step 2: Capture Authentication Headers

1. **Open DevTools**:
   - Press `F12` or right-click → "Inspect"
   - Go to the **Network** tab

2. **Find GraphQL Request**:
   - Refresh the page or navigate to trigger API calls
   - Look for requests to `/api/reporting/graphql`
   - Click on one of these requests

3. **Copy Request Headers**:
   - In the request details, find the **Request Headers** section
   - Look for these specific headers:
     - `authorization: Bearer ...`
     - `cookie: sessionid=...; csrftoken=...; ...`
     - `x-csrf-token: ...` (if present)

### Step 3: Create .env File

Create a `.env` file in your project root with the captured values:

```bash
# CreatorIQ Authentication
CREATORIQ_AUTH_TOKEN=Bearer_your_token_here
CREATORIQ_COOKIE=your_full_cookie_string_here
CREATORIQ_CSRF_TOKEN=your_csrf_token_here
```

### Step 4: Example Values

Here's what your `.env` file should look like (with your actual values):

```bash
# Example - replace with your actual values
CREATORIQ_AUTH_TOKEN=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
CREATORIQ_COOKIE=sessionid=abc123def456; csrftoken=xyz789abc123; _ga=GA1.2.123456789.1234567890; other_cookies=value123
CREATORIQ_CSRF_TOKEN=abc123def456xyz789
```

## 🔍 Finding Headers in Different Browsers

### Chrome/Edge
1. F12 → Network tab
2. Filter by "Fetch/XHR" 
3. Look for `graphql` requests
4. Click request → Headers tab → Request Headers

### Firefox
1. F12 → Network tab
2. Filter by "XHR"
3. Look for `graphql` requests
4. Click request → Headers → Request Headers

### Safari
1. Develop menu → Show Web Inspector
2. Network tab
3. Look for `graphql` requests
4. Click request → Headers

## 🧪 Testing Authentication

Run the authentication test:

```bash
python -c "from src.creatoriq.auth_headers import test_auth_headers; test_auth_headers()"
```

Expected output:
```
✅ Auth Token: Bearer eyJhbGciOiJIUzI1...
✅ Cookie: 245 chars
✅ CSRF Token: abc123def4...
✅ Authentication test successful!
```

## 🚀 Using with GraphQL Client

Once authentication is set up, you can use the GraphQL client:

```python
from src.creatoriq.graphql_client import get_campaign_posts_sync

# Get all posts for campaign 695483
posts = get_campaign_posts_sync(695483, require_auth=True)
print(f"Retrieved {len(posts)} posts")
```

## 🔧 Troubleshooting

### "Authentication Not Configured" Error
- Make sure your `.env` file exists in the project root
- Check that variable names match exactly: `CREATORIQ_AUTH_TOKEN`, `CREATORIQ_COOKIE`, etc.
- Ensure there are no extra spaces or quotes around the values

### "401 Unauthorized" Error
- Your auth token may be expired - capture fresh headers
- Make sure you copied the complete `authorization` header including "Bearer "
- Verify you're logged into CreatorIQ in the same browser session

### "403 Forbidden" Error
- Your account may not have access to the specific campaign
- Try with a different campaign ID you have access to
- Check if your session cookies are complete

### Headers Not Found in DevTools
- Make sure you're on a page that loads posts data
- Try refreshing the page to trigger new API calls
- Look for requests to `app.creatoriq.com/api/reporting/graphql`

## 🔒 Security Notes

- **Never commit your `.env` file** - it contains sensitive credentials
- Add `.env` to your `.gitignore` file
- Rotate credentials periodically for security
- Use environment variables in production, not hardcoded values

## 📱 Token Expiration

CreatorIQ tokens typically expire after:
- **Session tokens**: 24-48 hours
- **Auth tokens**: 1-7 days (varies)

When tokens expire:
1. Log back into CreatorIQ
2. Capture fresh headers using the same process
3. Update your `.env` file
4. Restart your application

## 🎯 Production Deployment

For production environments:
- Use secure secret management (AWS Secrets Manager, Azure Key Vault, etc.)
- Set up automated token refresh if possible
- Monitor for authentication failures and alert on issues
- Use separate credentials for different environments (dev/staging/prod) 