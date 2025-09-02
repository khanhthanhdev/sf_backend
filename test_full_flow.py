#!/usr/bin/env python3
"""
Test script to verify the complete video generation flow:
1. Frontend form submission -> Backend API
2. Backend job creation -> Video generation
3. Video completion -> Frontend video display

This script tests the integration between frontend and backend.
"""
import asyncio
import requests
import json
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"  # Adjust to your backend URL
FRONTEND_URL = "http://localhost:3000"  # Adjust to your frontend URL

# Test authentication token (you'll need to get this from Clerk)
AUTH_TOKEN = "your_clerk_session_token_here"

async def test_video_generation_flow():
    """Test the complete video generation flow."""
    print("🚀 Testing complete video generation flow...")
    
    # Step 1: Test video generation request (similar to frontend form submission)
    print("\n📝 Step 1: Creating video generation job...")
    
    video_config = {
        "configuration": {
            "topic": "Pythagorean Theorem",
            "context": "Explain the mathematical proof with visual demonstration for students",
            "model": "gemini/gemini-2.0-flash-thinking-exp-01-21",
            "quality": "medium",
            "use_rag": False,
            "enable_subtitles": True,
            "enable_thumbnails": True,
            "output_format": "mp4",
            "style_preferences": {
                "visual_style": "educational",
                "color_scheme": "vibrant",
                "mood": "educational"
            }
        },
        "priority": "normal"
    }
    
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        # Create video generation job
        response = requests.post(
            f"{API_BASE_URL}/api/v1/videos/generate",
            json=video_config,
            headers=headers
        )
        
        if response.status_code == 201:
            job_data = response.json()
            job_id = job_data["job_id"]
            print(f"✅ Job created successfully: {job_id}")
            print(f"   Status: {job_data['status']}")
            print(f"   Progress: {job_data['progress']['percentage']}%")
        else:
            print(f"❌ Failed to create job: {response.status_code}")
            print(f"   Response: {response.text}")
            return
        
        # Step 2: Monitor job progress
        print(f"\n🔄 Step 2: Monitoring job progress...")
        
        status = "queued"
        max_wait_time = 300  # 5 minutes max
        start_time = time.time()
        
        while status not in ["completed", "failed"] and (time.time() - start_time) < max_wait_time:
            # Check job status
            status_response = requests.get(
                f"{API_BASE_URL}/api/v1/videos/jobs/{job_id}/status",
                headers=headers
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                status = status_data["status"]
                progress = status_data.get("progress", {}).get("percentage", 0)
                current_stage = status_data.get("progress", {}).get("current_stage", "unknown")
                
                print(f"   Status: {status} | Progress: {progress:.1f}% | Stage: {current_stage}")
                
                if status in ["completed", "failed"]:
                    break
                
            time.sleep(3)  # Wait 3 seconds before next check
        
        # Step 3: Get video URL if completed
        if status == "completed":
            print(f"\n🎬 Step 3: Getting video URL...")
            
            video_url_response = requests.get(
                f"{API_BASE_URL}/api/v1/videos/jobs/{job_id}/video-url",
                headers=headers
            )
            
            if video_url_response.status_code == 200:
                video_data = video_url_response.json()
                print(f"✅ Video generation completed!")
                print(f"   Video URL: {video_data['video_url']}")
                print(f"   Download URL: {video_data['download_url']}")
                print(f"   Thumbnail URL: {video_data['thumbnail_url']}")
                print(f"   Duration: {video_data['metadata']['duration']} seconds")
                print(f"   File size: {video_data['metadata']['file_size']} bytes")
                print(f"   Quality: {video_data['metadata']['quality']}")
                
                # Step 4: Test video streaming
                print(f"\n📺 Step 4: Testing video streaming...")
                
                stream_response = requests.get(
                    f"{API_BASE_URL}/api/v1/videos/jobs/{job_id}/stream",
                    headers=headers,
                    stream=True
                )
                
                if stream_response.status_code == 200:
                    print(f"✅ Video streaming works!")
                    print(f"   Content type: {stream_response.headers.get('content-type')}")
                    print(f"   Content length: {stream_response.headers.get('content-length')}")
                else:
                    print(f"❌ Video streaming failed: {stream_response.status_code}")
                
                # Frontend integration info
                print(f"\n🌐 Frontend Integration:")
                print(f"   Create Video Page: {FRONTEND_URL}/videos/create")
                print(f"   Status Page: {FRONTEND_URL}/videos/status/{job_id}")
                print(f"   The frontend should now display the video with controls")
                
            else:
                print(f"❌ Failed to get video URL: {video_url_response.status_code}")
                print(f"   Response: {video_url_response.text}")
        
        elif status == "failed":
            print(f"❌ Video generation failed")
            
            # Get error details
            status_response = requests.get(
                f"{API_BASE_URL}/api/v1/videos/jobs/{job_id}/status",
                headers=headers
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                error = status_data.get("error")
                if error:
                    print(f"   Error: {error}")
        
        else:
            print(f"⏰ Job timed out or still processing after {max_wait_time} seconds")
            print(f"   Current status: {status}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def test_frontend_backend_integration():
    """Test basic connectivity between frontend and backend."""
    print("🔗 Testing frontend-backend integration...")
    
    # Test backend health
    try:
        health_response = requests.get(f"{API_BASE_URL}/health")
        if health_response.status_code == 200:
            print(f"✅ Backend is healthy: {API_BASE_URL}")
        else:
            print(f"❌ Backend health check failed: {health_response.status_code}")
    except requests.exceptions.RequestException:
        print(f"❌ Cannot connect to backend: {API_BASE_URL}")
    
    # Test frontend (basic check)
    try:
        frontend_response = requests.get(FRONTEND_URL, timeout=5)
        if frontend_response.status_code == 200:
            print(f"✅ Frontend is accessible: {FRONTEND_URL}")
        else:
            print(f"❌ Frontend check failed: {frontend_response.status_code}")
    except requests.exceptions.RequestException:
        print(f"❌ Cannot connect to frontend: {FRONTEND_URL}")

if __name__ == "__main__":
    print("=" * 60)
    print("🎬 T2M Video Generation Flow Test")
    print("=" * 60)
    
    # Test basic connectivity first
    test_frontend_backend_integration()
    
    # Note about authentication
    print(f"\n⚠️  IMPORTANT: Update AUTH_TOKEN in this script with a valid Clerk session token")
    print(f"   You can get this from your browser's developer tools when logged in")
    
    # Run the full flow test (uncomment when you have a valid token)
    # asyncio.run(test_video_generation_flow())
    
    print(f"\n📋 Manual Testing Steps:")
    print(f"1. Start the backend: cd t2m && python main.py")
    print(f"2. Start the frontend: cd sf_frontend && npm run dev")
    print(f"3. Open {FRONTEND_URL}/videos/create")
    print(f"4. Fill out the form with topic and context")
    print(f"5. Submit and monitor the status page")
    print(f"6. Watch for the video to appear when completed")
