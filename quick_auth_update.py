#!/usr/bin/env python3
"""
Quick update of CreatorIQ authentication with provided credentials
"""

from pathlib import Path
import datetime

def main():
    print("🔐 Updating CreatorIQ Authentication with CEO Credentials")
    print("=" * 60)
    print()
    
    # Fresh credentials from the user
    fresh_token = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJwaSI6MTk1LCJvcCI6MTk1LCJzaXEiOjEsIm4iOiJEZXJlayBEcmFrZSIsImwiOm51bGwsImUiOiJEZXJla0Bkcml2ZXNob3AuY29tIiwiYSI6bnVsbCwicG4iOiJEZXJla0Bkcml2ZXNob3AuY29tIiwiZ24iOiJEZXJlayIsImZuIjoiRHJha2UiLCJ6IjpudWxsLCJldiI6dHJ1ZSwic3AiOlszLDYsOSwxMCwxMSwxMiwyMF0sImRuIjpudWxsLCJzYSI6ZmFsc2UsImRzIjpbXSwic3ViIjoiMDB1MjM3c2V0bkJCbUdvckg2OTciLCJ1YSI6bnVsbCwiYXQiOjE3NTAwOTQ2MTIsImRkIjpudWxsLCJvZCI6bnVsbCwib2UiOm51bGwsImRpIjpudWxsLCJqdGkiOiI1MDU4ZTlhY2Q1YzEzZDhmOTI3NzZmOGUyYmUyMmVjMTFiMGFmM2UwIiwiaWF0IjoxNzUwMDk5NTAzLCJleHAiOjE3NTAxODU5MDMsIm9pIjpudWxsLCJjaSI6MTAwMDAzNzU5LCJkdiI6eyJpZCI6bnVsbCwibmFtZSI6bnVsbCwidHlwZSI6bnVsbCwiaGFzaCI6bnVsbH0sImFuIjpbMTk1XSwicCI6ImE6Nzp7czoxOlwiaVwiO2k6MTk1O3M6MjpcInNpXCI7aToxOTU7czoxOlwiblwiO3M6OTpcIkRyaXZlU2hvcFwiO3M6MTpcImRcIjtOO3M6MTpcInNcIjtzOjY6XCJBY3RpdmVcIjtzOjE6XCJoXCI7czoxODpcIjE5NV9kNjM2MWQ4ODk2YjAwOVwiO3M6MjpcImRuXCI7Tjt9IiwiaG0iOiJ7fSIsInQiOiIiLCJhYyI6IlVHRnlkRzVsY2pFNU5WOHhNREF3TURNM05UazZZelZrTTJSa01qTmlabVk1WVRGbE5qY3lOVFU0TlRVM09USTRaR1V5WW1RPSIsImNzcmZQcm90ZWN0aW9uIjp0cnVlfQ.ZKezWrZmuSKNVlQtpHVMxVHUjKwFuW-ZwsBWrJpWmjYSGWM93Z9c5LbKo7d5AQcigk96vPhG9P7QdYZd4MoyRIh5K3sEjAuYsE1VuzUv_3_kB_8_163o60PjdVOiAiV7wIdJDwTyYFSqh2aAB9xfdVydCssrUxJMyq26Hbzf5TUZ73tAYsBDGLXM0j-PvJHXzKj5WfSvdTXaXOmtSEsNXFZ_hgAC3Emt-WRbxQ83Gv-lYwqoS65mUyMEakpRU1vrXA13LU5rCKikhmy1WrGgBOmAM_FzwRGCo-Vc_h-2sHzLD_tiDsma7gKhdQK_iymhpP-ZHA1tvzEGbsdk3GnrVQGub-xdAh6e0dxxcOM50CVtvrAPxwFlCnnjoUu-g0f0yu0GhhZFPG7nwhamiM8s7uPq4eVjhH7nTDGe6TbFN8APPenr6pWgC_QGLqqGl4wp1f_v6j3Uln8B3BDSzRn5-cPumQoyydBVrUwQSRHMfxzG6bNGGLFuTKJavpVbp6U9dnFJEXMfwDOnN1osJa8NrZ38QMFHelwCw0AoMLhtEUMLznAswCqzGbVymh49A306y_gWa-9yDd9wKnP_xeSCAdTbMNNNbWlk5PA8ErruNaCUAHthGuaLSinPwebLgRXtCAoBudHp_9y2h2whbQ6XFn8dhKrAuGeDDE8tvSAK8k4"
    
    fresh_cookie = "_hjSessionUser_5266175=eyJpZCI6IjZhOWJiOTdmLWU4ZGItNTliMS1hNmU3LWUwMGVmYTcyZDNiYyIsImNyZWF0ZWQiOjE3NTAwOTQ1ODQ5MzAsImV4aXN0aW5nIjp0cnVlfQ==; _gid=GA1.2.1728956056.1750094588; jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJwaSI6MTk1LCJvcCI6MTk1LCJzaXEiOjEsIm4iOiJEZXJlayBEcmFrZSIsImwiOm51bGwsImUiOiJEZXJla0Bkcml2ZXNob3AuY29tIiwiYSI6bnVsbCwicG4iOiJEZXJla0Bkcml2ZXNob3AuY29tIiwiZ24iOiJEZXJlayIsImZuIjoiRHJha2UiLCJ6IjpudWxsLCJldiI6dHJ1ZSwic3AiOlszLDYsOSwxMCwxMSwxMiwyMF0sImRuIjpudWxsLCJzYSI6ZmFsc2UsImRzIjpbXSwic3ViIjoiMDB1MjM3c2V0bkJCbUdvckg2OTciLCJ1YSI6bnVsbCwiYXQiOjE3NTAwOTQ2MTIsImRkIjpudWxsLCJvZCI6bnVsbCwib2UiOm51bGwsImRpIjpudWxsLCJqdGkiOiI1MDU4ZTlhY2Q1YzEzZDhmOTI3NzZmOGUyYmUyMmVjMTFiMGFmM2UwIiwiaWF0IjoxNzUwMDk0NjE0LCJleHAiOjE3NTAxODEwMTQsIm9pIjpudWxsLCJjaSI6MTAwMDAzNzU5LCJkdiI6eyJpZCI6bnVsbCwibmFtZSI6bnVsbCwidHlwZSI6bnVsbCwiaGFzaCI6bnVsbH0sImFuIjpbMTk1XSwicCI6ImE6Nzp7czoxOlwiaVwiO2k6MTk1O3M6MjpcInNpXCI7aToxOTU7czoxOlwiblwiO3M6OTpcIkRyaXZlU2hvcFwiO3M6MTpcImRcIjtOO3M6MTpcInNcIjtzOjY6XCJBY3RpdmVcIjtzOjE6XCJoXCI7czoxODpcIjE5NV9kNjM2MWQ4ODk2YjAwOVwiO3M6MjpcImRuXCI7Tjt9IiwiaG0iOiJ7fSIsInQiOiIiLCJhYyI6IlVHRnlkRzVsY2pFNU5WOHhNREF3UZNM05UazZZelZrTTJSa01qTmlabVk1WVRGbE5qY3lOVFU0TlRVM09USTRaR1V5WW1RPSIsImNzcmZQcm90ZWN0aW9uIjp0cnVlfQ.ONrdb6S7dVBayYhwff9gkuKYrLhbFTfX1A_P8FihvFMG9HJoCGxXOK2mUiDbjxqqyLDtF2-7ZbuYduMZvGUK3xyo66Tu9x97L5S_6c5apNLW8jzJsHk1tHE4hY3KkrNZfRA9_h2Xh4151mau2F9doCPf_mHdTaJeLBSBNFDQTZGOWmXqloM8Befidr1IJ7KX5xCCLnwfIWKrtULOiLAO_MjYL-9FpoigeCtHS5q8Bj5PYuNdiH12anBDEPKnU6SP9WR1-S4w7Z5nyALE_GLMeAOyXDkb5uwwOVejPFzkBMA5Eh0bEiXeIhtu50kVQVsJL4nGhYaFBZGokOyigfx6NWj8KuqxOOC-0fQaveKzP2C-0WeqlQNIEaJtvDKpfd3fanfnrQVxaHKdxUX6cH80NEBV6fprTnT6REj11K7vRLe5Na1d5AKrlFfKOmbCuhOhR70qr_FIAUVIJxcEt547XIB5EO--Emu1MsgyxMSE4cDpRH6I7aIemnlmygN6ZUyxHvOjoBkZrKeAEW7wZu_sQx_2WsjkLE9YjFjVGyQ86YRYWvUifX5WeDBZB9bCDQSfaJNdo_vSAAbhj6WP5sCASVGnUXTP5afBUCRbxF5ljEF6mkUhQwQE83OApeFsRKeJ7twxlHgln8t0ZGfCvb8Tky0pjQYNLbHjHoCOrk7cqBw; __zlcmid=1SBnh8f3qi0c8X6; _ga_D86QLHK00N=GS2.1.s1750095841$o1$g1$t1750095847$j54$l0$h0; _gcl_au=1.1.874426470.1750095936; _ga_FK716NGXTQ=GS2.1.s1750095935$o1$g0$t1750095935$j60$l0$h0; _uetsid=b56c72004ad911f09444ff5f59b9f0c5; _uetvid=b56c9b904ad911f099a9a183f9ebeb0f; amp_e9074a=SwXV1hDfaOlmQJiJGSCu47...1itsthes9.1itsthk1m.1.4.5; _ga=GA1.2.257509494.1750094588; _gat=1; _ga_W66L6CXKH1=GS2.2.s1750099502$o2$g1$t1750100073$j60$l0$h0"
    
    print("✅ Fresh CEO Credentials Received!")
    print(f"👤 User: Derek Drake (CEO)")
    print(f"📧 Email: Derek@driveshop.com") 
    print(f"🔐 Token: {len(fresh_token)} characters")
    print(f"🍪 Cookie: {len(fresh_cookie)} characters")
    print()
    
    # Read existing .env to preserve other variables
    env_file = Path(".env")
    other_vars = []
    
    if env_file.exists():
        print("📄 Preserving existing environment variables...")
        existing_content = env_file.read_text()
        for line in existing_content.split('\n'):
            if line.strip() and not line.startswith('#') and not line.startswith('CREATORIQ_'):
                other_vars.append(line)
    
    # Create new .env content with fresh CEO credentials
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    env_content = f"""# CreatorIQ Authentication (Updated {timestamp})
# Fresh CEO credentials from Derek Drake's active session
CREATORIQ_AUTH_TOKEN={fresh_token}
CREATORIQ_COOKIE={fresh_cookie}
"""
    
    # Add any existing non-CreatorIQ variables
    if other_vars:
        env_content += "\n# Other environment variables\n"
        env_content += "\n".join(other_vars) + "\n"
    
    # Write new .env file
    env_file.write_text(env_content)
    
    print("✅ CEO Authentication Updated Successfully!")
    print()
    print(f"📄 File: {env_file.absolute()}")
    print(f"👤 Account: Derek Drake (CEO) - Full Access")
    print(f"🏢 Company: DriveShop")
    print(f"📊 Campaign: 695483 (Audi) - Should now work!")
    print(f"🔐 Fresh Session: Just captured from your browser")
    print()
    print("🚀 Ready to test with CEO privileges!")
    
    return True

if __name__ == "__main__":
    main() 