#!/usr/bin/env python3
"""
Test script for AWS Bedrock integration.
Run this to verify your Bedrock setup is working correctly.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_credentials():
    """Test if AWS credentials are properly set."""
    print("🔑 Testing AWS Credentials...")
    
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION_NAME']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these in your .env file or environment.")
        return False
    
    print("✅ All required AWS credentials found!")
    print(f"   Region: {os.getenv('AWS_REGION_NAME')}")
    print(f"   Access Key: {os.getenv('AWS_ACCESS_KEY_ID')[:8]}...")
    return True

def test_bedrock_import():
    """Test if BedrockWrapper can be imported."""
    print("\n📦 Testing Bedrock Import...")
    
    try:
        from mllm_tools.bedrock import BedrockWrapper
        print("✅ BedrockWrapper imported successfully!")
        return True
    except ImportError as e:
        print(f"❌ Failed to import BedrockWrapper: {e}")
        return False

def test_bedrock_connection():
    """Test basic Bedrock connection and model usage."""
    print("\n🔗 Testing Bedrock Connection...")
    
    try:
        from mllm_tools.bedrock import BedrockWrapper
        
        # Test with Claude 3.5 Sonnet (most reliable model)
        wrapper = BedrockWrapper(
            model_name="bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
            verbose=True
        )
        
        print("🧪 Testing simple completion...")
        response = wrapper.chat([
            {"role": "user", "content": "Say 'Hello from AWS Bedrock!' and nothing else."}
        ])
        
        print(f"✅ Bedrock Response: {response}")
        return True
        
    except Exception as e:
        print(f"❌ Bedrock connection failed: {e}")
        print("\nPossible issues:")
        print("1. Model access not granted in AWS Console")
        print("2. Invalid AWS credentials")
        print("3. Wrong AWS region")
        print("4. Network connectivity issues")
        return False

def test_factory_integration():
    """Test Bedrock integration with the video generation factory."""
    print("\n🏭 Testing Factory Integration...")
    
    try:
        from generate_video import ComponentFactory, VideoGenerationConfig
        
        config = VideoGenerationConfig(
            planner_model="bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
            verbose=True,
            use_langfuse=False
        )
        
        model = ComponentFactory.create_model(
            "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
            config
        )
        
        print("✅ Bedrock model created via ComponentFactory!")
        print(f"   Model type: {type(model).__name__}")
        return True
        
    except Exception as e:
        print(f"❌ Factory integration failed: {e}")
        return False

def test_available_models():
    """Test that Bedrock models are in allowed models list."""
    print("\n📋 Testing Available Models...")
    
    try:
        import json
        
        allowed_models_path = os.path.join(
            os.path.dirname(__file__), 
            'src', 'utils', 'allowed_models.json'
        )
        
        with open(allowed_models_path, 'r') as f:
            allowed_models = json.load(f)
        
        bedrock_models = [
            model for model in allowed_models['allowed_models'] 
            if model.startswith('bedrock/')
        ]
        
        print(f"✅ Found {len(bedrock_models)} Bedrock models in allowed list:")
        for model in bedrock_models[:5]:  # Show first 5
            print(f"   - {model}")
        
        if len(bedrock_models) > 5:
            print(f"   ... and {len(bedrock_models) - 5} more")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to check allowed models: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 AWS Bedrock Integration Test")
    print("=" * 50)
    
    tests = [
        test_credentials,
        test_bedrock_import,
        test_available_models,
        test_factory_integration,
        test_bedrock_connection,  # Most likely to fail, so run last
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except KeyboardInterrupt:
            print("\n🛑 Test interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error in {test.__name__}: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! AWS Bedrock is ready to use.")
        print("\nExample usage:")
        print("python generate_video.py --topic 'Quantum Computing' --model 'bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0'")
    else:
        print("⚠️  Some tests failed. Please check the AWS Bedrock setup guide.")
        print("📖 See: AWS_BEDROCK_SETUP.md")
        sys.exit(1)

if __name__ == "__main__":
    main()
