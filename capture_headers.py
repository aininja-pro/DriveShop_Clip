#!/usr/bin/env python3
"""
Interactive tool to capture fresh CreatorIQ authentication headers
"""

import os
from pathlib import Path

def main():
    print("🔐 CreatorIQ Header Capture Tool")
    print("=" * 50)
    print()
    print("Since you're logged in as CEO, let's capture fresh headers!")
    print()
    print("📋 STEPS TO FOLLOW:")
    print("1. Keep your CreatorIQ tab open (https://app.creatoriq.com/#campaign/695483/posts_new/published)")
    print("2. Press F12 to open DevTools")
    print("3. Go to 'Network' tab")
    print("4. Refresh the page (Ctrl+R or Cmd+R)")
    print("5. Look for requests to '/api/reporting/graphql'")
    print("6. Click on one of those requests")
    print("7. Find the 'Request Headers' section")
    print("8. Copy the values for:")
    print("   - authorization: Bearer ...")
    print("   - cookie: sessionid=...")
    print("   - x-csrf-token: ... (if present)")
    print()
    
    # Get current .env content to show what we're replacing
    env_file = Path(".env")
    if env_file.exists():
        print("📄 Current .env file found")
    else:
        print("📄 Will create new .env file")
    print()
    
    # Collect new headers
    print("🔧 Please paste your fresh authentication headers:")
    print()
    
    # Auth Token
    print("1️⃣ AUTHORIZATION HEADER:")
    print("   Look for: authorization: Bearer ...")
    print("   Example: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...")
    auth_token = input("   Paste the full Bearer token: ").strip()
    
    if not auth_token.startswith("Bearer "):
        if auth_token.startswith("eyJ"):  # JWT tokens often start with eyJ
            auth_token = f"Bearer {auth_token}"
        else:
            print("   ⚠️  Adding 'Bearer ' prefix to your token")
            auth_token = f"Bearer {auth_token}"
    
    print()
    
    # Cookie
    print("2️⃣ COOKIE HEADER:")
    print("   Look for: cookie: sessionid=...; csrftoken=...; ...")
    print("   Example: sessionid=abc123; csrftoken=def456; _ga=GA1.2.123...")
    cookie = input("   Paste the full cookie string: ").strip()
    
    print()
    
    # CSRF Token (optional)
    print("3️⃣ CSRF TOKEN (optional):")
    print("   Look for: x-csrf-token: ...")
    print("   If you don't see this header, just press Enter to skip")
    csrf_token = input("   Paste CSRF token (or Enter to skip): ").strip()
    
    print()
    
    # Validate input
    if not auth_token or not cookie:
        print("❌ Missing required headers! Need both auth token and cookie.")
        return False
    
    # Create new .env content
    env_content = f"""# CreatorIQ Authentication (Updated {__import__('datetime').datetime.now()})
CREATORIQ_AUTH_TOKEN={auth_token}
CREATORIQ_COOKIE={cookie}
"""
    
    if csrf_token:
        env_content += f"CREATORIQ_CSRF_TOKEN={csrf_token}\n"
    
    # Add any existing non-CreatorIQ variables
    if env_file.exists():
        existing_content = env_file.read_text()
        other_vars = []
        for line in existing_content.split('\n'):
            if line.strip() and not line.startswith('#') and not line.startswith('CREATORIQ_'):
                other_vars.append(line)
        
        if other_vars:
            env_content += "\n# Other environment variables\n"
            env_content += "\n".join(other_vars) + "\n"
    
    # Write new .env file
    env_file.write_text(env_content)
    
    print("✅ Headers saved to .env file!")
    print()
    print(f"📄 Updated: {env_file.absolute()}")
    print(f"🔐 Auth Token: {auth_token[:30]}...")
    print(f"🍪 Cookie: {len(cookie)} characters")
    if csrf_token:
        print(f"🛡️  CSRF Token: {csrf_token[:20]}...")
    else:
        print("🛡️  CSRF Token: Not provided (optional)")
    
    print()
    print("🚀 Ready to test! Run: python test_live_api.py")
    
    return True

if __name__ == "__main__":
    main() 