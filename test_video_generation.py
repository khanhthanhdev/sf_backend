#!/usr/bin/env python3
"""
Test script for video generation pipeline.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_demo_video_creation():
    """Test the demo video creation functionality."""
    
    print("=== Testing Demo Video Creation ===")
    
    # Mock job configuration
    class MockJobConfig:
        def __init__(self):
            self.topic = "Test Topic: Mathematics & Physics"
            self.context = "This is a test context for video generation"
            self.quality = "medium"
    
    class MockJob:
        def __init__(self):
            self.configuration = MockJobConfig()
            self.user_id = "test_user_123"
    
    job = MockJob()
    job_id = "test_job_123"
    
    # Test video creation logic (extracted from the fixed code)
    temp_path = None
    video_created_successfully = False
    
    try:
        import subprocess
        import shutil
        from datetime import datetime
        
        # Create temporary file for video
        temp_fd, temp_path = tempfile.mkstemp(suffix=".mp4")
        os.close(temp_fd)  # Close the file descriptor, we'll use the path
        temp_path = Path(temp_path)
        
        print(f"Created temporary file: {temp_path}")
        
        # Check if ffmpeg is available
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            print(f"FFmpeg found at: {ffmpeg_path}")
            
            # Create a simple video with text overlay
            duration = 5  # 5 second test video
            
            # Properly escape text for FFmpeg
            topic_safe = job.configuration.topic.replace("'", "").replace('"', '').replace('\\', '').replace(':', ' -')[:50]
            current_time = datetime.utcnow().strftime("%Y-%m-%d %H-%M-%S")
            
            # Create a simpler text overlay
            text_content = f"Demo Video|Topic: {topic_safe}|Generated: {current_time}|Job: {job_id[:8]}|Quality: {job.configuration.quality}"
            
            # FFmpeg command with properly escaped text
            cmd = [
                ffmpeg_path,
                '-f', 'lavfi',
                '-i', f'color=c=blue:size=1280x720:duration={duration}',
                '-vf', f'drawtext=text={text_content}:fontsize=24:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-y',
                str(temp_path)
            ]
            
            print(f"Running FFmpeg command...")
            print(f"Command: {' '.join(cmd)}")
            
            # Run FFmpeg command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Verify the video file was created and has content
                if temp_path.exists() and temp_path.stat().st_size > 1000:
                    file_size = temp_path.stat().st_size
                    print(f"✅ Created demo video with FFmpeg, size: {file_size} bytes")
                    video_created_successfully = True
                else:
                    print(f"❌ FFmpeg completed but video file is too small or missing")
            else:
                print(f"❌ FFmpeg failed with return code {result.returncode}")
                print(f"FFmpeg stderr: {result.stderr}")
                print(f"FFmpeg stdout: {result.stdout}")
        else:
            print("❌ FFmpeg not found in system PATH")
            
        # If FFmpeg failed, try OpenCV
        if not video_created_successfully:
            print("Trying OpenCV as fallback...")
            try:
                import cv2
                import numpy as np
                
                # Create a simple video using OpenCV
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                fps = 30
                duration = 5
                width, height = 1280, 720
                
                out = cv2.VideoWriter(str(temp_path), fourcc, fps, (width, height))
                
                # Create frames
                total_frames = fps * duration
                for frame_num in range(total_frames):
                    # Create blue background
                    frame = np.full((height, width, 3), (255, 0, 0), dtype=np.uint8)  # Blue in BGR
                    
                    # Add text
                    cv2.putText(frame, "Demo Video", (width//2 - 100, height//2 - 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
                    cv2.putText(frame, f"Topic: {job.configuration.topic[:30]}", (width//2 - 200, height//2), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    cv2.putText(frame, f"Job ID: {job_id[:16]}", (width//2 - 150, height//2 + 40), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    
                    out.write(frame)
                
                out.release()
                
                # Verify the video file was created
                if temp_path.exists() and temp_path.stat().st_size > 1000:
                    file_size = temp_path.stat().st_size
                    print(f"✅ Created demo video with OpenCV, size: {file_size} bytes")
                    video_created_successfully = True
                else:
                    print("❌ OpenCV video creation failed")
                    
            except ImportError:
                print("❌ OpenCV not available")
            except Exception as cv_error:
                print(f"❌ OpenCV video creation failed: {cv_error}")
        
        # If both failed, try minimal MP4
        if not video_created_successfully:
            print("Trying minimal MP4 as final fallback...")
            try:
                import base64
                
                # Minimal MP4 file (base64 encoded)
                minimal_mp4_b64 = """AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAAsdtZGF0AAACrgYF//+q3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzA5NSBiYWVlNDAwIC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyMSAtIGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTMgZGVibG9jaz0xOjA6MCBhbmFseXNlPTB4MzoweDExMyBtZT1oZXggc3VibWU9NyBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1peGVkX3JlZj0xIG1lX3JhbmdlPTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MSA4eDhkY3Q9MSBjcW09MCBkZWFkem9uZT0yMSwxMSBmYXN0X3Bza2lwPTEgY2hyb21hX3FwX29mZnNldD0tMiB0aHJlYWRzPTEgbG9va2FoZWFkX3RocmVhZHM9MSBzbGljZWRfdGhyZWFkcz0wIG5yPTAgZGVjaW1hdGU9MSBpbnRlcmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZyYW1lcz0zIGJfcHlyYW1pZD0yIGJfYWRhcHQ9MSBiX2JpYXM9MCBkaXJlY3Q9MSB3ZWlnaHRiPTEgb3Blbl9nb3A9MCB3ZWlnaHRwPTIga2V5aW50PTI1MCBrZXlpbnRfbWluPTI1IHNjZW5lY3V0PTQwIGludHJhX3JlZnJlc2g9MCByY19sb29rYWhlYWQ9NDAgcmM9Y3JmIG1idHJlZT0xIGNyZj0yMy4wIHFjb21wPTAuNjAgcXBtaW49MCBxcG1heD02OSBxcHN0ZXA9NCBpcF9yYXRpbz0xLjQwIGFxPTE6MS4wMACAAAABWWWIhAAz//727L4FNf2f0JcRLMXaSnA+KqSAgHc0wAAAAwAAAwAAFgn0I7DkqgAAAAlBmiRsQn/+tSqAAAAJQZ5CeIK/+tSqAAAACUGeYXiCv/rUqgAAAAlBnoN4gr/61KoAAAAJQZ6leIK/+tSqAAAACUGexXiCv/rUqgAAAAlBnwV4gr/61KoAAAAJQZ8neIK/+tSqAAAACUGfSXiCv/rUqgAAAAlBn2t4gr/61Ko="""
                
                # Decode and write the minimal MP4
                mp4_data = base64.b64decode(minimal_mp4_b64)
                with open(temp_path, 'wb') as f:
                    f.write(mp4_data)
                
                file_size = temp_path.stat().st_size
                print(f"✅ Created minimal MP4 file, size: {file_size} bytes")
                video_created_successfully = True
                
            except Exception as final_error:
                print(f"❌ All video creation methods failed: {final_error}")
        
        # Final verification
        if video_created_successfully and temp_path.exists():
            file_size = temp_path.stat().st_size
            print(f"\n✅ Final result: Video file created successfully")
            print(f"   Path: {temp_path}")
            print(f"   Size: {file_size} bytes")
            
            # Try to get video info if ffprobe is available
            ffprobe_path = shutil.which('ffprobe')
            if ffprobe_path:
                try:
                    probe_cmd = [ffprobe_path, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(temp_path)]
                    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                    if probe_result.returncode == 0:
                        import json
                        probe_data = json.loads(probe_result.stdout)
                        if 'format' in probe_data:
                            duration = probe_data['format'].get('duration', 'unknown')
                            print(f"   Duration: {duration} seconds")
                        if 'streams' in probe_data and probe_data['streams']:
                            stream = probe_data['streams'][0]
                            width = stream.get('width', 'unknown')
                            height = stream.get('height', 'unknown')
                            print(f"   Resolution: {width}x{height}")
                except Exception as e:
                    print(f"   Could not probe video info: {e}")
        else:
            print(f"\n❌ Failed to create video file")
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
                print(f"\n🧹 Cleaned up temporary file: {temp_path}")
            except Exception as e:
                print(f"⚠️ Failed to clean up temp file: {e}")

async def test_full_pipeline_import():
    """Test importing the full pipeline components."""
    
    print("\n=== Testing Full Pipeline Import ===")
    
    try:
        # Test the import path logic from the fixed code
        import os
        import sys
        
        current_file = os.path.abspath(__file__)
        possible_roots = [
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))),
            os.path.dirname(os.path.dirname(os.path.dirname(current_file))),
            os.path.dirname(os.path.dirname(current_file)),
            os.getcwd(),
            os.path.dirname(os.getcwd()),
        ]
        
        root_dir = None
        for potential_root in possible_roots:
            generate_video_path = os.path.join(potential_root, 'generate_video.py')
            if os.path.exists(generate_video_path):
                root_dir = potential_root
                print(f"✅ Found generate_video.py at: {generate_video_path}")
                break
        
        if not root_dir:
            print(f"❌ Could not find generate_video.py in any of these locations:")
            for path in possible_roots:
                print(f"   - {os.path.join(path, 'generate_video.py')}")
            return
        
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        
        # Try to import
        try:
            from generate_video import EnhancedVideoGenerator, VideoGenerationConfig
            print("✅ Successfully imported EnhancedVideoGenerator and VideoGenerationConfig")
            
            # Test model wrapper imports
            model_wrappers_available = []
            try:
                from mllm_tools.litellm import LiteLLMWrapper
                model_wrappers_available.append("LiteLLMWrapper")
                print("✅ LiteLLMWrapper available")
            except ImportError as e:
                print(f"❌ LiteLLMWrapper not available: {e}")
            
            try:
                from mllm_tools.openrouter import OpenRouterWrapper
                model_wrappers_available.append("OpenRouterWrapper")
                print("✅ OpenRouterWrapper available")
            except ImportError as e:
                print(f"❌ OpenRouterWrapper not available: {e}")
            
            try:
                from mllm_tools.gemini import GeminiWrapper
                model_wrappers_available.append("GeminiWrapper")
                print("✅ GeminiWrapper available")
            except ImportError as e:
                print(f"❌ GeminiWrapper not available: {e}")
            
            if model_wrappers_available:
                print(f"✅ Available model wrappers: {model_wrappers_available}")
                
                # Try to create a config (without actually initializing models)
                try:
                    config = VideoGenerationConfig(
                        planner_model='test-model',
                        output_dir='test_output',
                        verbose=True
                    )
                    print("✅ Successfully created VideoGenerationConfig")
                except Exception as e:
                    print(f"❌ Failed to create VideoGenerationConfig: {e}")
            else:
                print("❌ No model wrappers available - full pipeline will fail")
                
        except ImportError as e:
            print(f"❌ Failed to import generate_video components: {e}")
            
    except Exception as e:
        print(f"❌ Unexpected error during import test: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run all tests."""
    await test_demo_video_creation()
    await test_full_pipeline_import()
    
    print("\n=== Test Summary ===")
    print("Run this script to verify your video generation environment.")
    print("Also run 'python debug_environment.py' for a comprehensive environment check.")

if __name__ == "__main__":
    asyncio.run(main())