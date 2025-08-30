#!/usr/bin/env python3
"""
T2M Video Generation System

Main entry point for the text-to-video generation system with AWS S3 integration.
Supports both local-only and cloud-based video storage.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional
import argparse
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.video_orchestrator import VideoGenerationOrchestrator, VideoGenerationConfig
from core.storage_manager import StorageManager, StorageMode
from mllm_tools.gemini import GeminiWrapper  # Example - replace with your model

# Load environment variables
load_dotenv()


async def generate_video_local_only(topic: str, description: str, output_dir: str = "output"):
    """Generate video with local-only storage (development mode)."""
    print(f"🎬 Generating video locally: {topic}")
    
    # Initialize models (replace with your actual models)
    planner_model = GeminiWrapper(model_name="gemini-2.5-pro")
    scene_model = GeminiWrapper(model_name="gemini-2.5-pro")
    
    # Configure for local-only generation
    config = VideoGenerationConfig(
        planner_model=planner_model,
        scene_model=scene_model,
        storage_mode="local_only",
        enable_s3_upload=False,
        output_dir=output_dir,
        quality=os.getenv('VIDEO_QUALITY', 'medium'),
        use_rag=os.getenv('USE_RAG', 'false').lower() == 'true',
        use_context_learning=os.getenv('USE_CONTEXT_LEARNING', 'false').lower() == 'true'
    )
    
    # Create orchestrator
    orchestrator = VideoGenerationOrchestrator(config)
    
    # Generate video
    result = await orchestrator.generate_video(topic, description)
    
    if result.success:
        print(f"✅ Video generated successfully!")
        print(f"📁 Video path: {result.combined_video_path}")
        print(f"📊 Scenes: {result.metadata['total_scenes']} total, {result.metadata['successful_scenes']} successful")
        return result
    else:
        print(f"❌ Video generation failed: {result.error}")
        return None


async def generate_video_with_s3(topic: str, description: str, user_id: str, job_id: Optional[str] = None):
    """Generate video with AWS S3 storage (production mode)."""
    print(f"☁️ Generating video with S3 storage: {topic}")
    
    # Validate AWS configuration
    required_aws_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION']
    missing_vars = [var for var in required_aws_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing AWS configuration: {', '.join(missing_vars)}")
        print("Please check your .env file or environment variables")
        return None
    
    # Initialize models
    planner_model = GeminiWrapper(model_name="gemini-1.5-pro")
    scene_model = GeminiWrapper(model_name="gemini-1.5-pro")
    
    # Generate job ID if not provided
    if not job_id:
        import uuid
        job_id = str(uuid.uuid4())
    
    # Configure for S3 generation
    config = VideoGenerationConfig(
        planner_model=planner_model,
        scene_model=scene_model,
        user_id=user_id,
        job_id=job_id,
        storage_mode=os.getenv('VIDEO_STORAGE_MODE', 'local_and_s3'),
        enable_s3_upload=True,
        cleanup_local_files=os.getenv('CLEANUP_LOCAL_FILES', 'false').lower() == 'true',
        output_dir=os.getenv('OUTPUT_DIR', 'output'),
        quality=os.getenv('VIDEO_QUALITY', 'medium'),
        use_rag=os.getenv('USE_RAG', 'false').lower() == 'true',
        use_context_learning=os.getenv('USE_CONTEXT_LEARNING', 'false').lower() == 'true',
        use_visual_fix_code=os.getenv('USE_VISUAL_FIX_CODE', 'false').lower() == 'true'
    )
    
    # Add progress callback
    def progress_callback(stage: str, percentage: float, message: str):
        print(f"🔄 [{stage}] {percentage:.1f}% - {message}")
    
    config.progress_callback = progress_callback
    
    # Create orchestrator
    orchestrator = VideoGenerationOrchestrator(config)
    
    # Generate video
    result = await orchestrator.generate_video(topic, description)
    
    if result.success:
        print(f"✅ Video generated and uploaded successfully!")
        
        if result.combined_video_upload and result.combined_video_upload.success:
            print(f"☁️ S3 URL: {result.combined_video_upload.s3_url}")
            print(f"🎬 Streaming URL: {result.combined_video_upload.streaming_url}")
            if result.combined_video_upload.metadata.get('thumbnail_url'):
                print(f"🖼️ Thumbnail: {result.combined_video_upload.metadata['thumbnail_url']}")
        
        if result.combined_video_path:
            print(f"📁 Local path: {result.combined_video_path}")
        
        print(f"📊 Scenes: {result.metadata['total_scenes']} total, {result.metadata['successful_scenes']} successful")
        print(f"💾 Storage: {result.metadata['storage_mode']}")
        
        return result
    else:
        print(f"❌ Video generation failed: {result.error}")
        return None


def main():
    """Main entry point with command line interface."""
    parser = argparse.ArgumentParser(description='T2M Video Generation System')
    parser.add_argument('--topic', '-t', type=str, required=True, help='Video topic')
    parser.add_argument('--description', '-d', type=str, required=True, help='Video description')
    parser.add_argument('--mode', '-m', choices=['local', 's3'], default='local', 
                       help='Generation mode: local or s3')
    parser.add_argument('--user-id', '-u', type=str, help='User ID (required for S3 mode)')
    parser.add_argument('--job-id', '-j', type=str, help='Job ID (optional, auto-generated if not provided)')
    parser.add_argument('--output-dir', '-o', type=str, default='output', help='Output directory')
    
    args = parser.parse_args()
    
    async def run():
        # Validate arguments
        if args.mode == 's3' and not args.user_id:
            print("❌ User ID is required for S3 mode")
            return
        
        # Generate video
        if args.mode == 'local':
            result = await generate_video_local_only(
                topic=args.topic,
                description=args.description,
                output_dir=args.output_dir
            )
        else:  # s3 mode
            result = await generate_video_with_s3(
                topic=args.topic,
                description=args.description,
                user_id=args.user_id,
                job_id=args.job_id
            )
        
        if result:
            print(f"\n🎉 Video generation completed successfully!")
        else:
            print(f"\n💥 Video generation failed!")
            sys.exit(1)
    
    # Run async main
    asyncio.run(run())


if __name__ == "__main__":
    main()
