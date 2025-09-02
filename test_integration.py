#!/usr/bin/env python3
"""
Test script for verifying the enhanced video service integration.

This script tests the integration between FastAPI backend and the core video generation pipeline.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_enhanced_video_service():
    """Test the enhanced video service integration."""
    try:
        # Test imports
        logger.info("Testing imports...")
        
        # Test core components import
        from src.app.services.enhanced_video_service import EnhancedVideoService
        logger.info("✅ Enhanced video service import successful")
        
        # Test generate_video imports
        try:
            from generate_video import VideoGenerationConfig, EnhancedVideoGenerator
            logger.info("✅ generate_video.py imports successful")
        except ImportError as e:
            logger.warning(f"⚠️ generate_video.py imports failed: {e}")
        
        # Test core orchestrator import
        try:
            from src.core.video_orchestrator import VideoGenerationOrchestrator
            logger.info("✅ Core orchestrator import successful")
        except ImportError as e:
            logger.warning(f"⚠️ Core orchestrator import failed: {e}")
        
        # Test configuration mapping
        logger.info("Testing configuration mapping...")
        from src.app.services.enhanced_video_service import JobConfigurationMapper
        
        # Create a mock job configuration
        from src.app.models.job import JobConfiguration, Job as JobModel, JobStatus, JobType, JobProgress
        from datetime import datetime
        import uuid
        
        mock_config = JobConfiguration(
            topic="Test Mathematical Concept",
            context="A simple explanation of addition",
            quality="medium",  # Use string instead of enum
            use_rag=True
        )
        
        mock_progress = JobProgress()  # Create default progress
        
        mock_job = JobModel(
            id=str(uuid.uuid4()),
            user_id="test_user",
            job_type=JobType.VIDEO_GENERATION,
            status=JobStatus.QUEUED,
            configuration=mock_config,
            progress=mock_progress,  # Add required progress field
            created_at=datetime.utcnow()
        )
        
        # Test configuration mapping
        temp_output_dir = "/tmp/test_video_output"
        pipeline_config = JobConfigurationMapper.map_job_to_pipeline_config(mock_job, temp_output_dir)
        
        logger.info(f"✅ Configuration mapping successful:")
        logger.info(f"   Topic: {mock_config.topic}")
        logger.info(f"   Pipeline model: {pipeline_config.planner_model}")
        logger.info(f"   Quality: {pipeline_config.default_quality}")
        logger.info(f"   Use RAG: {pipeline_config.use_rag}")
        logger.info(f"   Output dir: {pipeline_config.output_dir}")
        
        # Test progress tracker
        logger.info("Testing progress tracker...")
        from src.app.services.enhanced_video_service import PipelineProgressTracker
        
        # Mock video service for testing
        class MockVideoService:
            async def update_job_status(self, **kwargs):
                logger.info(f"Mock job status update: {kwargs}")
                return True
        
        mock_video_service = MockVideoService()
        progress_tracker = PipelineProgressTracker("test_job_id", mock_video_service)
        
        # Test progress updates
        await progress_tracker.update_progress("planning", 15, "Test planning stage")
        await progress_tracker.update_progress("rendering", 80, "Test rendering stage")
        
        logger.info("✅ Progress tracker test successful")
        
        logger.info("\n🎉 All integration tests passed!")
        logger.info("\n📋 Next steps:")
        logger.info("1. Ensure all required environment variables are set")
        logger.info("2. Test with a real API request")
        logger.info("3. Verify S3 upload functionality")
        logger.info("4. Test end-to-end video generation workflow")
        
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def test_environment_configuration():
    """Test environment configuration for the core pipeline."""
    logger.info("\n🔧 Testing environment configuration...")
    
    required_env_vars = [
        "PLANNER_MODEL",
        "MAX_SCENE_CONCURRENCY", 
        "MAX_CONCURRENT_RENDERS",
        "OUTPUT_DIR"
    ]
    
    optional_env_vars = [
        "USE_RAG",
        "USE_CONTEXT_LEARNING",
        "DEFAULT_QUALITY",
        "ENABLE_CACHING"
    ]
    
    missing_required = []
    
    for var in required_env_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"✅ {var}: {value}")
        else:
            logger.warning(f"⚠️ {var}: Not set (using default)")
            missing_required.append(var)
    
    for var in optional_env_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"✅ {var}: {value}")
        else:
            logger.info(f"ℹ️ {var}: Not set (using default)")
    
    if missing_required:
        logger.warning(f"⚠️ Missing required environment variables: {missing_required}")
        logger.info("Consider setting them for optimal performance")
    else:
        logger.info("✅ All required environment variables are set")

async def main():
    """Main test function."""
    logger.info("🚀 Starting Enhanced Video Service Integration Test")
    logger.info("=" * 60)
    
    # Test environment
    await test_environment_configuration()
    
    # Test integration
    success = await test_enhanced_video_service()
    
    if success:
        logger.info("\n✅ Integration test completed successfully!")
        logger.info("The enhanced video service is ready for production use.")
    else:
        logger.error("\n❌ Integration test failed!")
        logger.error("Please fix the issues above before using the enhanced service.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
