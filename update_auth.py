#!/usr/bin/env python3
"""
Update CreatorIQ authentication with fresh credentials
"""

from pathlib import Path

def main():
    print("🔐 Updating CreatorIQ Authentication")
    print("=" * 50)
    print()
    
    # The fresh Bearer token provided by the user
    fresh_token = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJwaSI6MTk1LCJvcCI6MTk1LCJzaXEiOjEsIm4iOiJEZXJlayBEcmFrZSIsImwiOm51bGwsImUiOiJEZXJla0Bkcml2ZXNob3AuY29tIiwiYSI6bnVsbCwicG4iOiJEZXJla0Bkcml2ZXNob3AuY29tIiwiZ24iOiJEZXJlayIsImZuIjoiRHJha2UiLCJ6IjpudWxsLCJldiI6dHJ1ZSwic3AiOlszLDYsOSwxMCwxMSwxMiwyMF0sImRuIjpudWxsLCJzYSI6ZmFsc2UsImRzIjpbXSwic3ViIjoiMDB1MjM3c2V0bkJCbUdvckg2OTciLCJ1YSI6bnVsbCwiYXQiOjE3NTAwOTQ2MTIsImRkIjpudWxsLCJvZCI6bnVsbCwib2UiOm51bGwsImRpIjpudWxsLCJqdGkiOiI1MDU4ZTlhY2Q1YzEzZDhmOTI3NzZmOGUyYmUyMmVjMTFiMGFmM2UwIiwiaWF0IjoxNzUwMDk5NTAzLCJleHAiOjE3NTAxODU5MDMsIm9pIjpudWxsLCJjaSI6MTAwMDAzNzU5LCJkdiI6eyJpZCI6bnVsbCwibmFtZSI6bnVsbCwidHlwZSI6bnVsbCwiaGFzaCI6bnVsbH0sImFuIjpbMTk1XSwicCI6ImE6Nzp7czoxOlwiaVwiO2k6MTk1O3M6MjpcInNpXCI7aToxOTU7czoxOlwiblwiO3M6OTpcIkRyaXZlU2hvcFwiO3M6MTpcImRcIjtOO3M6MTpcInNcIjtzOjY6XCJBY3RpdmVcIjtzOjE6XCJoXCI7czoxODpcIjE5NV9kNjM2MWQ4ODk2YjAwOVwiO3M6MjpcImRuXCI7Tjt9IiwiaG0iOiJ7fSIsInQiOiIiLCJhYyI6IlVHRnlkRzVsY2pFNU5WOHhNREF3TURNM05UazZZelZrTTJSa01qTmlabVk1WVRGbE5qY3lOVFU0TlRVM09USTRaR1V5WW1RPSIsImNzcmZQcm90ZWN0aW9uIjp0cnVlfQ.ZKezWrZmuSKNVlQtpHVMxVHUjKwFuW-ZwsBWrJpWmjYSGWM93Z9c5LbKo7d5AQcigk96vPhG9P7QdYZd4MoyRIh5K3sEjAuYsE1VuzUv_3_kB_8_163o60PjdVOiAiV7wIdJDwTyYFSqh2aAB9xfdVydCssrUxJMyq26Hbzf5TUZ73tAYsBDGLXM0j-PvJHXzKj5WfSvdTXaXOmtSEsNXFZ_hgAC3Emt-WRbxQ83Gv-lYwqoS65mUyMEakpRU1vrXA13LU5rCKikhmy1WrGgBOmAM_FzwRGCo-Vc_h-2sHzLD_tiDsma7gKhdQK_iymhpP-ZHA1tvzEGbsdk3GnrVQGub-xdAh6e0dxxcOM50CVtvrAPxwFlCnnjoUu-g0f0yu0GhhZFPG7nwhamiM8s7uPq4eVjhH7nTDGe6TbFN8APPenr6pWgC_QGLqqGl4wp1f_v6j3Uln8B3BDSzRn5-cPumQoyydBVrUwQSRHMfxzG6bNGGLFuTKJavpVbp6U9dnFJEXMfwDOnN1osJa8NrZ38QMFHelwCw0AoMLhtEUMLznAswCqzGbVymh49A306y_gWa-9yDd9wKnP_xeSCAdTbMNNNbWlk5PA8ErruNaCUAHthGuaLSinPwebLgRXtCAoBudHp_9y2h2whbQ6XFn8dhKrAuGeDDE8tvSAK8k4"
    
    print("✅ Fresh Bearer Token Received!")
    print(f"🔐 Token for: Derek Drake at DriveShop")
    print(f"📅 Expires: Token appears valid and fresh")
    print()
    
    # Now we need the cookie
    print("🍪 Now we need the COOKIE string from the same request:")
    print()
    print("In your browser DevTools (F12) → Network tab:")
    print("1. Find the same GraphQL request you got the Bearer token from")
    print("2. Look for the 'cookie:' header in Request Headers")
    print("3. Copy the ENTIRE cookie string (it will be long)")
    print()
    print("Example: sessionid=abc123; csrftoken=def456; _ga=GA1.2.123...")
    print()
    
    cookie = input("📋 Paste the full cookie string here: ").strip()
    
    if not cookie:
        print("❌ Cookie is required! Please copy the full cookie string.")
        return False
    
    print()
    
    # Optional CSRF token
    print("🛡️  CSRF Token (optional):")
    print("Look for 'x-csrf-token:' header (if you don't see it, just press Enter)")
    csrf_token = input("📋 Paste CSRF token (or Enter to skip): ").strip()
    
    print()
    
    # Read existing .env to preserve other variables
    env_file = Path(".env")
    other_vars = []
    
    if env_file.exists():
        existing_content = env_file.read_text()
        for line in existing_content.split('\n'):
            if line.strip() and not line.startswith('#') and not line.startswith('CREATORIQ_'):
                other_vars.append(line)
    
    # Create new .env content
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    env_content = f"""# CreatorIQ Authentication (Updated {timestamp})
# Fresh credentials from Derek Drake CEO session
CREATORIQ_AUTH_TOKEN={fresh_token}
CREATORIQ_COOKIE={cookie}
"""
    
    if csrf_token:
        env_content += f"CREATORIQ_CSRF_TOKEN={csrf_token}\n"
    
    # Add any existing non-CreatorIQ variables
    if other_vars:
        env_content += "\n# Other environment variables\n"
        env_content += "\n".join(other_vars) + "\n"
    
    # Write new .env file
    env_file.write_text(env_content)
    
    print("✅ Authentication Updated Successfully!")
    print()
    print(f"📄 File: {env_file.absolute()}")
    print(f"🔐 Token: Derek Drake CEO credentials")
    print(f"🍪 Cookie: {len(cookie)} characters")
    if csrf_token:
        print(f"🛡️  CSRF: {csrf_token[:20]}...")
    else:
        print("🛡️  CSRF: Not provided (should work without it)")
    
    print()
    print("🚀 Ready to test! Your CEO credentials should have full access.")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🧪 Run this to test: python test_live_api.py")
    else:
        print("\n❌ Setup incomplete. Please try again.") 