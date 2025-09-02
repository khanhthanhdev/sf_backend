#!/usr/bin/env python3
"""
Debug script to check the environment for video generation pipeline.
Run this to diagnose issues with the full pipeline.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_environment():
    """Check the environment for video generation requirements."""
    
    print("=== Video Generation Environment Debug ===\n")
    
    # Check Python version
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Current working directory: {os.getcwd()}")
    print()
    
    # Check for generate_video.py
    print("=== Checking for generate_video.py ===")
    current_file = os.path.abspath(__file__)
    possible_roots = [
        os.path.dirname(current_file),  # Same directory as this script
        os.path.dirname(os.path.dirname(current_file)),  # Parent directory
        os.getcwd(),  # Current working directory
        os.path.dirname(os.getcwd()),  # Parent of working directory
    ]
    
    generate_video_found = False
    for root in possible_roots:
        generate_video_path = os.path.join(root, 'generate_video.py')
        if os.path.exists(generate_video_path):
            print(f"✅ Found generate_video.py at: {generate_video_path}")
            generate_video_found = True
            
            # Try to import it
            sys.path.insert(0, root)
            try:
                import generate_video
                print(f"✅ Successfully imported generate_video from {root}")
                
                # Check for required classes
                if hasattr(generate_video, 'EnhancedVideoGenerator'):
                    print("✅ EnhancedVideoGenerator class found")
                else:
                    print("❌ EnhancedVideoGenerator class not found")
                    
                if hasattr(generate_video, 'VideoGenerationConfig'):
                    print("✅ VideoGenerationConfig class found")
                else:
                    print("❌ VideoGenerationConfig class not found")
                    
            except Exception as e:
                print(f"❌ Failed to import generate_video: {e}")
            break
        else:
            print(f"❌ Not found at: {generate_video_path}")
    
    if not generate_video_found:
        print("❌ generate_video.py not found in any expected location")
    
    print()
    
    # Check for model wrapper dependencies
    print("=== Checking Model Wrapper Dependencies ===")
    
    wrappers = [
        ('mllm_tools.litellm', 'LiteLLMWrapper'),
        ('mllm_tools.openrouter', 'OpenRouterWrapper'),
        ('mllm_tools.gemini', 'GeminiWrapper'),
    ]
    
    available_wrappers = []
    for module_name, class_name in wrappers:
        try:
            module = __import__(module_name, fromlist=[class_name])
            wrapper_class = getattr(module, class_name)
            print(f"✅ {class_name} available from {module_name}")
            available_wrappers.append(class_name)
        except ImportError as e:
            print(f"❌ {class_name} not available: {e}")
        except AttributeError as e:
            print(f"❌ {class_name} not found in {module_name}: {e}")
    
    if available_wrappers:
        print(f"✅ Available model wrappers: {available_wrappers}")
    else:
        print("❌ No model wrappers available")
    
    print()
    
    # Check for FFmpeg
    print("=== Checking FFmpeg ===")
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        print(f"✅ FFmpeg found at: {ffmpeg_path}")
        
        # Check FFmpeg version
        try:
            result = subprocess.run([ffmpeg_path, '-version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                print(f"✅ FFmpeg version: {version_line}")
            else:
                print(f"❌ FFmpeg version check failed: {result.stderr}")
        except Exception as e:
            print(f"❌ Failed to check FFmpeg version: {e}")
    else:
        print("❌ FFmpeg not found in PATH")
    
    print()
    
    # Check for OpenCV
    print("=== Checking OpenCV ===")
    try:
        import cv2
        print(f"✅ OpenCV available, version: {cv2.__version__}")
    except ImportError as e:
        print(f"❌ OpenCV not available: {e}")
    
    print()
    
    # Check output directory
    print("=== Checking Output Directory ===")
    output_dir = os.getenv('OUTPUT_DIR', 'output')
    print(f"Output directory (OUTPUT_DIR): {output_dir}")
    
    if os.path.exists(output_dir):
        print(f"✅ Output directory exists: {os.path.abspath(output_dir)}")
        if os.access(output_dir, os.W_OK):
            print("✅ Output directory is writable")
        else:
            print("❌ Output directory is not writable")
    else:
        print(f"❌ Output directory does not exist: {os.path.abspath(output_dir)}")
        try:
            os.makedirs(output_dir, exist_ok=True)
            print(f"✅ Created output directory: {os.path.abspath(output_dir)}")
        except Exception as e:
            print(f"❌ Failed to create output directory: {e}")
    
    print()
    
    # Check environment variables
    print("=== Environment Variables ===")
    env_vars = [
        'OPENAI_API_KEY',
        'GEMINI_API_KEY',
        'OPENROUTER_API_KEY',
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask API keys for security
            if 'API_KEY' in var:
                masked_value = value[:8] + '...' + value[-4:] if len(value) > 12 else '***'
                print(f"✅ {var}: {masked_value}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: Not set")
    
    print()
    
    # Summary
    print("=== Summary ===")
    issues = []
    
    if not generate_video_found:
        issues.append("generate_video.py not found")
    
    if not available_wrappers:
        issues.append("No model wrappers available")
    
    if not ffmpeg_path:
        issues.append("FFmpeg not available")
    
    if not os.path.exists(output_dir) or not os.access(output_dir, os.W_OK):
        issues.append("Output directory issues")
    
    if issues:
        print("❌ Issues found:")
        for issue in issues:
            print(f"   - {issue}")
        print("\nRecommendations:")
        if not generate_video_found:
            print("   - Ensure generate_video.py is in the project root")
        if not available_wrappers:
            print("   - Install mllm_tools: pip install mllm_tools")
        if not ffmpeg_path:
            print("   - Install FFmpeg: apt-get install ffmpeg (Ubuntu) or brew install ffmpeg (macOS)")
        if not os.path.exists(output_dir):
            print("   - Create output directory or set OUTPUT_DIR environment variable")
    else:
        print("✅ All checks passed! Environment should be ready for video generation.")

if __name__ == "__main__":
    check_environment()