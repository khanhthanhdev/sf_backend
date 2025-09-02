#!/usr/bin/env python3
"""
Test FFmpeg command generation and execution.
"""

import subprocess
import tempfile
import shutil
import os
from pathlib import Path
from datetime import datetime

def test_ffmpeg_command():
    """Test the exact FFmpeg command that's being generated."""
    
    print("=== Testing FFmpeg Command ===")
    
    # Mock job data
    class MockConfig:
        def __init__(self):
            self.topic = "Derivative"
            self.quality = "medium"  # Use string instead of enum
    
    class MockJob:
        def __init__(self):
            self.configuration = MockConfig()
    
    job = MockJob()
    job_id = "2ef09102-32eb-4bc0-8698-3ad554a1d059"
    
    # Check if ffmpeg is available
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        print("❌ FFmpeg not found in system PATH")
        return
    
    print(f"✅ FFmpeg found at: {ffmpeg_path}")
    
    # Create temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(temp_fd)
    temp_path = Path(temp_path)
    
    try:
        # Generate the same command as in the service
        duration = 30
        
        # Properly escape text for FFmpeg
        topic_safe = job.configuration.topic.replace("'", "").replace('"', '').replace('\\', '').replace(':', ' -')[:50]
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H-%M-%S")
        
        # Handle quality enum properly
        quality_str = str(job.configuration.quality)
        if hasattr(job.configuration.quality, 'value'):
            quality_str = job.configuration.quality.value
        elif '.' in quality_str:
            quality_str = quality_str.split('.')[-1].lower()
        
        # Create text content
        text_content = f"Demo Video|Topic: {topic_safe}|Generated: {current_time}|Job: {job_id[:8]}|Quality: {quality_str}"
        
        print(f"Text content: {text_content}")
        
        # FFmpeg command
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
        
        print(f"\nFFmpeg command:")
        print(' '.join(cmd))
        
        print(f"\nRunning FFmpeg...")
        
        # Run the command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        print(f"Return code: {result.returncode}")
        
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
        
        # Check result
        if result.returncode == 0:
            if temp_path.exists():
                file_size = temp_path.stat().st_size
                print(f"✅ Video created successfully!")
                print(f"   File: {temp_path}")
                print(f"   Size: {file_size} bytes")
                
                # Try to get video info
                ffprobe_path = shutil.which('ffprobe')
                if ffprobe_path:
                    try:
                        probe_cmd = [ffprobe_path, '-v', 'quiet', '-print_format', 'json', '-show_format', str(temp_path)]
                        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                        if probe_result.returncode == 0:
                            import json
                            probe_data = json.loads(probe_result.stdout)
                            if 'format' in probe_data:
                                duration = probe_data['format'].get('duration', 'unknown')
                                print(f"   Duration: {duration} seconds")
                    except Exception as e:
                        print(f"   Could not probe video: {e}")
            else:
                print("❌ Video file not created")
        else:
            print(f"❌ FFmpeg failed with return code {result.returncode}")
            
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg process timed out")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        if temp_path.exists():
            temp_path.unlink()
            print(f"🧹 Cleaned up: {temp_path}")

if __name__ == "__main__":
    test_ffmpeg_command()