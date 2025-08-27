#!/usr/bin/env python3
"""
Quick API Test - Just check if your API is running
"""

import requests
import sys

def quick_test(base_url):
    """Quick test to see if API is responding"""
    print(f"🔍 Quick API Test: {base_url}")
    print("-" * 40)
    
    # Test endpoints that should work
    endpoints = [
        ('/system/health', 'System Health'),
        ('/auth/health', 'Auth Health'),
        ('/auth/status', 'Auth Status'),
        ('/', 'Root (may require auth)')
    ]
    
    working_endpoints = 0
    
    for endpoint, name in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ {name}: Working (200)")
                working_endpoints += 1
            elif response.status_code == 401:
                print(f"🔐 {name}: Requires auth (401)")
                working_endpoints += 1  # Still counts as working
            else:
                print(f"⚠️  {name}: Status {response.status_code}")
        
        except requests.exceptions.ConnectionError:
            print(f"❌ {name}: Connection failed - API not running?")
        except requests.exceptions.Timeout:
            print(f"❌ {name}: Timeout")
        except Exception as e:
            print(f"❌ {name}: Error - {e}")
    
    print(f"\n📊 Result: {working_endpoints}/{len(endpoints)} endpoints responding")
    
    if working_endpoints >= 2:
        print("✅ API appears to be running!")
        print("\nNext steps:")
        print("1. Get your Clerk token: python get_token_simple.py")
        print("2. Test with token: python test_current_api.py <base_url> <token>")
        return True
    else:
        print("❌ API may not be running or accessible")
        print("\nTroubleshooting:")
        print("- Check if your FastAPI server is running")
        print("- Verify the URL is correct")
        print("- Check for firewall/network issues")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python quick_api_test.py <base_url>")
        print("Example: python quick_api_test.py http://localhost:8000/api/v1")
        return 1
    
    base_url = sys.argv[1].rstrip('/')
    success = quick_test(base_url)
    return 0 if success else 1

if __name__ == '__main__':
    exit(main())