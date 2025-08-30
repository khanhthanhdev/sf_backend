#!/usr/bin/env python3
"""
Simple test script for video generation API

This script tests the complete video generation workflow:
1. Generate video job
2. Poll for job completion
3. Retrieve S3 URLs and metadata
4. Test file downloads
"""

import asyncio
import json
import time
import requests
from typing import Dict, Any, Optional
import argparse
from datetime import datetime


class VideoGenerationTester:
    def __init__(self, base_url: str, auth_token: str):
        """
        Initialize the tester with API base URL and authentication token
        
        Args:
            base_url: API base URL (e.g., "http://localhost:8000/api/v1")
            auth_token: Clerk authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'T2M-Test-Client/1.0'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def test_auth_status(self) -> bool:
        """Test authentication status"""
        print("🔐 Testing authentication...")
        try:
            response = self.session.get(f"{self.base_url}/auth/status")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Authentication successful: {data.get('user_id', 'Unknown user')}")
                return True
            else:
                print(f"❌ Authentication failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
    
    def generate_video(self, topic: str, description: str, quality: str = "medium") -> Optional[str]:
        """
        Create a video generation job
        
        Args:
            topic: Video topic
            description: Video description
            quality: Video quality (low, medium, high)
            
        Returns:
            Job ID if successful, None otherwise
        """
        print(f"🎬 Generating video for topic: '{topic}'...")
        
        payload = {
            "configuration": {
                "topic": topic,
                "context": description,  # API expects 'context' not 'description'
                "quality": quality,
                "use_rag": True,
                "enable_thumbnails": True
            },
            "priority": "normal"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/videos/generate",
                json=payload
            )
            
            if response.status_code == 201:
                data = response.json()
                job_id = data.get('job_id') or data.get('data', {}).get('job_id')
                if job_id:
                    print(f"✅ Video generation job created: {job_id}")
                    return job_id
                else:
                    print(f"❌ No job ID in response: {data}")
                    return None
            else:
                print(f"❌ Video generation failed: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Video generation error: {e}")
            return None
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status and details
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status data if successful, None otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/videos/jobs/{job_id}/status")
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', data)
            else:
                print(f"❌ Failed to get job status: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting job status: {e}")
            return None
    
    def poll_for_completion(self, job_id: str, max_wait_time: int = 600, poll_interval: int = 10) -> Optional[Dict[str, Any]]:
        """
        Poll job status until completion or timeout
        
        Args:
            job_id: Job identifier
            max_wait_time: Maximum wait time in seconds
            poll_interval: Polling interval in seconds
            
        Returns:
            Final job status if completed, None if failed/timeout
        """
        print(f"⏳ Polling job {job_id} for completion...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_data = self.get_job_status(job_id)
            
            if not status_data:
                print("❌ Failed to get job status")
                return None
            
            status = status_data.get('status')
            progress = status_data.get('progress', {})
            
            if isinstance(progress, dict):
                percentage = progress.get('percentage', 0)
                current_stage = progress.get('current_stage', 'unknown')
                print(f"📊 Status: {status} | Progress: {percentage:.1f}% | Stage: {current_stage}")
            else:
                print(f"📊 Status: {status} | Progress: {progress}%")
            
            if status == 'completed':
                print("✅ Job completed successfully!")
                return status_data
            elif status in ['failed', 'cancelled', 'error']:
                print(f"❌ Job {status}")
                if 'error' in status_data:
                    print(f"Error details: {status_data['error']}")
                return None
            
            time.sleep(poll_interval)
        
        print(f"⏰ Job polling timeout after {max_wait_time} seconds")
        return None
    
    def test_file_access(self, job_id: str, status_data: Dict[str, Any]) -> None:
        """
        Test access to generated files
        
        Args:
            job_id: Job identifier
            status_data: Job status data containing file URLs
        """
        print("📁 Testing file access...")
        
        # Test video download
        try:
            video_response = self.session.head(f"{self.base_url}/videos/jobs/{job_id}/download")
            if video_response.status_code in [200, 302]:
                print("✅ Video download endpoint accessible")
                if 'Location' in video_response.headers:
                    print(f"🔗 Redirects to S3: {video_response.headers['Location'][:100]}...")
            else:
                print(f"❌ Video download failed: {video_response.status_code}")
        except Exception as e:
            print(f"❌ Video download error: {e}")
        
        # Test video streaming
        try:
            stream_response = self.session.head(f"{self.base_url}/videos/jobs/{job_id}/stream")
            if stream_response.status_code in [200, 302]:
                print("✅ Video streaming endpoint accessible")
            else:
                print(f"❌ Video streaming failed: {stream_response.status_code}")
        except Exception as e:
            print(f"❌ Video streaming error: {e}")
        
        # Test thumbnail access
        for size in ['small', 'medium', 'large']:
            try:
                thumb_response = self.session.head(f"{self.base_url}/videos/jobs/{job_id}/thumbnail?size={size}")
                if thumb_response.status_code in [200, 302]:
                    print(f"✅ Thumbnail ({size}) accessible")
                else:
                    print(f"❌ Thumbnail ({size}) failed: {thumb_response.status_code}")
            except Exception as e:
                print(f"❌ Thumbnail ({size}) error: {e}")
        
        # Test scene files if available
        scene_files = status_data.get('scene_files', [])
        if scene_files:
            scene_number = scene_files[0].get('scene_number', 1)
            try:
                code_response = self.session.head(f"{self.base_url}/videos/jobs/{job_id}/scenes/{scene_number}/code")
                if code_response.status_code in [200, 302]:
                    print(f"✅ Scene {scene_number} code file accessible")
                else:
                    print(f"❌ Scene {scene_number} code file failed: {code_response.status_code}")
            except Exception as e:
                print(f"❌ Scene {scene_number} code file error: {e}")
    
    def print_s3_urls(self, status_data: Dict[str, Any]) -> None:
        """
        Print all S3 URLs from job status
        
        Args:
            status_data: Job status data containing S3 URLs
        """
        print("\n🔗 S3 URLs and File Information:")
        print("=" * 50)
        
        # Main video URLs
        video_urls = status_data.get('video_urls', {})
        if video_urls:
            print("📹 Video Files:")
            for url_type, url in video_urls.items():
                print(f"  {url_type}: {url}")
        
        # Thumbnail URLs
        thumbnails = status_data.get('thumbnails', [])
        if thumbnails:
            print("\n🖼️ Thumbnails:")
            for thumb in thumbnails:
                size = thumb.get('size', 'unknown')
                s3_url = thumb.get('s3_url', 'N/A')
                streaming_url = thumb.get('streaming_url', 'N/A')
                print(f"  {size}: {s3_url}")
                if streaming_url != 'N/A':
                    print(f"    Streaming: {streaming_url[:100]}...")
        
        # Scene files
        scene_files = status_data.get('scene_files', [])
        if scene_files:
            print("\n🎬 Scene Files:")
            for scene in scene_files:
                scene_num = scene.get('scene_number', 'unknown')
                video_s3 = scene.get('video_s3_url', 'N/A')
                code_s3 = scene.get('code_s3_url', 'N/A')
                print(f"  Scene {scene_num}:")
                print(f"    Video: {video_s3}")
                print(f"    Code: {code_s3}")
        
        # Metadata
        metadata = status_data.get('metadata', {})
        if metadata:
            print("\n📊 Metadata:")
            for key, value in metadata.items():
                print(f"  {key}: {value}")
    
    def run_complete_test(self, topic: str, description: str, quality: str = "medium") -> bool:
        """
        Run complete video generation test workflow
        
        Args:
            topic: Video topic
            description: Video description
            quality: Video quality
            
        Returns:
            True if test passed, False otherwise
        """
        print(f"🚀 Starting complete video generation test")
        print(f"Topic: {topic}")
        print(f"Description: {description}")
        print(f"Quality: {quality}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 60)
        
        # Test authentication
        if not self.test_auth_status():
            return False
        
        # Generate video
        job_id = self.generate_video(topic, description, quality)
        if not job_id:
            return False
        
        # Poll for completion
        status_data = self.poll_for_completion(job_id)
        if not status_data:
            return False
        
        # Print S3 URLs
        self.print_s3_urls(status_data)
        
        # Test file access
        self.test_file_access(job_id, status_data)
        
        print("\n✅ Complete test workflow finished successfully!")
        return True


def main():
    parser = argparse.ArgumentParser(description='Test T2M Video Generation API')
    parser.add_argument('--url', default='http://localhost:8000/api/v1', help='API base URL')
    parser.add_argument('--token', required=True, help='Authentication token')
    parser.add_argument('--topic', default='Mathematical Functions', help='Video topic')
    parser.add_argument('--description', default='Educational video explaining quadratic functions', help='Video description')
    parser.add_argument('--quality', default='medium', choices=['low', 'medium', 'high'], help='Video quality')
    
    args = parser.parse_args()
    
    # Create tester
    tester = VideoGenerationTester(args.url, args.token)
    
    # Run complete test
    success = tester.run_complete_test(args.topic, args.description, args.quality)
    
    exit(0 if success else 1)


if __name__ == "__main__":
    main()