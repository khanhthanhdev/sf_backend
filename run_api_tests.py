#!/usr/bin/env python3
"""
Simple runner for T2M API tests with configuration file support
"""

import json
import sys
import os
from pathlib import Path
from test_api_endpoints import T2MAPITester

def load_config(config_file: str = "test_config.json") -> dict:
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Configuration file '{config_file}' not found")
        print("Please create a test_config.json file or use test_api_endpoints.py directly")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in configuration file: {e}")
        return None

def main():
    # Load configuration
    config = load_config()
    if not config:
        return 1
    
    api_config = config.get('api_config', {})
    base_url = api_config.get('base_url')
    token = api_config.get('token')
    
    if not base_url:
        print("❌ base_url not specified in configuration")
        return 1
    
    if not token or token == "your-bearer-token-here":
        print("⚠️  No valid token provided - only public endpoints will be tested")
        token = None
    
    print("🔧 Configuration loaded:")
    print(f"   Base URL: {base_url}")
    print(f"   Token: {'Provided' if token else 'Not provided'}")
    
    # Create and run tester
    tester = T2MAPITester(base_url, token)
    tester.run_all_tests()
    
    return 0

if __name__ == '__main__':
    exit(main())