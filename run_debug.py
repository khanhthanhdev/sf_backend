#!/usr/bin/env python3
"""
Run debug and comprehensive tests
"""

import subprocess
import sys

def run_debug():
    print("🔍 Running Authentication Debug")
    print("=" * 50)
    
    try:
        result = subprocess.run([sys.executable, "debug_auth.py"], 
                              capture_output=True, text=True, timeout=30)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode != 0:
            print(f"Debug script failed with code {result.returncode}")
        
    except subprocess.TimeoutExpired:
        print("Debug script timed out")
    except Exception as e:
        print(f"Error running debug script: {e}")
    
    print("\n" + "=" * 50)
    print("🎬 Running Comprehensive Test")
    print("=" * 50)
    
    try:
        result = subprocess.run([sys.executable, "test_api_comprehensive.py"], 
                              capture_output=True, text=True, timeout=60)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✅ All tests passed!")
        else:
            print(f"❌ Some tests failed (code {result.returncode})")
        
    except subprocess.TimeoutExpired:
        print("Test script timed out")
    except Exception as e:
        print(f"Error running test script: {e}")

if __name__ == '__main__':
    run_debug()