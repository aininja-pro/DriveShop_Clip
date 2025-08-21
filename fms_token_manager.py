#!/usr/bin/env python3
"""
FMS Token Manager - Manual token rotation and management script
"""

import os
import sys
from src.utils.fms_api import FMSAPIClient

def main():
    """Main token management interface."""
    if len(sys.argv) < 2:
        print("FMS Token Manager")
        print("Usage:")
        print("  python fms_token_manager.py current    - Show current token")
        print("  python fms_token_manager.py rotate     - Rotate token and show new one")
        print("  python fms_token_manager.py test       - Test current token connection")
        return
    
    command = sys.argv[1].lower()
    
    try:
        client = FMSAPIClient()
        environment = client.environment
        
        print(f"🔧 FMS Token Manager - Environment: {environment}")
        print("-" * 50)
        
        if command == "current":
            current_token = client.get_current_token()
            print(f"Current token: {current_token}")
            print(f"Environment: {environment}")
            print("\n💡 To update Render:")
            print(f"   Set FMS_API_TOKEN={current_token}")
            
        elif command == "rotate":
            print("🔄 Rotating token...")
            result = client.rotate_token()
            
            if result["success"]:
                new_token = result["new_token"]
                print(f"✅ Token rotation successful!")
                print(f"New token: {new_token}")
                print(f"Environment: {environment}")
                print("\n🚨 ACTION REQUIRED:")
                print(f"   Update Render environment variable:")
                print(f"   FMS_API_TOKEN={new_token}")
                print("\n📋 Steps to update Render:")
                print("   1. Go to Render dashboard")
                print("   2. Select your service")
                print("   3. Go to Environment tab")
                print(f"   4. Update FMS_API_TOKEN to: {new_token}")
                print("   5. Click 'Save Changes'")
            else:
                print(f"❌ Token rotation failed: {result['error']}")
                
        elif command == "test":
            print("🔍 Testing connection...")
            result = client.test_connection()
            
            if result["success"]:
                print(f"✅ Connection successful: {result['message']}")
            else:
                print(f"❌ Connection failed: {result['error']}")
                
        else:
            print(f"❌ Unknown command: {command}")
            print("Valid commands: current, rotate, test")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("\n💡 Make sure your environment variables are set:")
        print("   FMS_API_TOKEN")
        print("   FMS_API_STAGING_URL or FMS_API_PRODUCTION_URL")
        print("   FMS_API_ENVIRONMENT (optional, defaults to 'staging')")

if __name__ == "__main__":
    main()