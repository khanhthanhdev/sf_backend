#!/usr/bin/env python3
"""
Simple runner for video generation API tests
"""

import json
import sys
import os
from test_video_generation import VideoGenerationTester

def load_config(config_file: str = "video_test_config.json") -> dict:
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Configuration file '{config_file}' not found")
        print("Please create a video_test_config.json file or use test_video_generation.py directly")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in configuration file: {e}")
        return None

def main():
    # Load configuration
    config = load_config()
    if not config:
        return 1
    
    api_config = config.get('api', {})
    base_url = api_config.get('base_url')
    token = api_config.get('token')
    
    if not base_url:
        print("❌ base_url not specified in configuration")
        return 1
    
    if not token or token == "your-bearer-token-here":
        print("❌ Valid authentication token is required for video generation testing")
        return 1
    
    print("🎬 Video Generation Test Configuration:")
    print(f"   Base URL: {base_url}")
    print(f"   Token: {'*' * (len(token) - 4) + token[-4:]}")
    
    # Get test settings
    test_settings = config.get('test_settings', {})
    monitor_progress = test_settings.get('monitor_progress', True)
    
    # Create and run tester
    tester = VideoGenerationTester(base_url, token)
    tester.run_comprehensive_test(monitor_progress)
    
    return 0

if __name__ == '__main__':
    exit(main())