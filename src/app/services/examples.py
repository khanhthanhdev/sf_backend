"""
Example usage of the refactored service layer with SOLID principles.

This demonstrates how to use the dependency injection container
and the refactored services in API endpoints.
"""

import asyncio
import logging
from typing import Dict, Any

from ..core.container import (
    setup_service_container,
    initialize_container,
    get_video_generation_use_case,
    get_container,
    cleanup_container
)
from ..models.video import VideoMetadata
from ..models.user import ClerkUser
from ..models.job import VideoQuality
from ..schemas.requests import VideoGenerationRequest
from ..services.interfaces.base import ServiceResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_video_generation_workflow():
    """
    Example of complete video generation workflow using refactored services.
    """
    
    try:
        # 1. Setup dependency injection container
        logger.info("Setting up service container...")
        container = setup_service_container()
        
        # 2. Initialize all services
        logger.info("Initializing services...")
        await initialize_container()
        
        # 3. Create example user and request
        user = ClerkUser(
            clerk_user_id="user_123",
            username="example_user",
            email_addresses=["user@example.com"],
            subscription_tier="pro",
            created_at="2025-01-01T00:00:00Z"
        )
        
        request = VideoGenerationRequest(
            topic="How to build a REST API with FastAPI",
            context="A comprehensive tutorial covering API design, database integration, authentication, and deployment. Target audience is intermediate Python developers.",
            quality=VideoQuality.HIGH,
            model="gpt-4",
            use_rag=True,
            configuration={
                "custom_voice": True,
                "advanced_transitions": True
            }
        )
        
        # 4. Get use case service from container
        video_generation_use_case = get_video_generation_use_case()
        
        # 5. Execute video generation workflow
        logger.info("Starting video generation workflow...")
        result = await video_generation_use_case.generate_video(request, user)
        
        if result.success:
            job = result.data
            logger.info(f"Video generation started successfully!")
            logger.info(f"Job ID: {job.id}")
            logger.info(f"Status: {job.status}")
            logger.info(f"Priority: {job.priority}")
            logger.info(f"Estimated cost: {result.metadata.get('estimated_cost')} credits")
            
            # 6. Check status
            status_result = await video_generation_use_case.get_video_generation_status(
                job.id, user
            )
            
            if status_result.success:
                status_data = status_result.data
                logger.info(f"Job status: {status_data}")
            
        else:
            logger.error(f"Video generation failed: {result.error}")
            logger.error(f"Error code: {result.error_code}")
        
        # 7. Demonstrate service health checks
        logger.info("Checking service health...")
        
        # Get individual services for health checks
        video_service = container.resolve(
            container._registrations[type(video_generation_use_case.video_generation_service)].interface
        )
        
        health_result = await video_service.health_check()
        if health_result.success:
            logger.info(f"Service health: {health_result.data}")
        
    except Exception as e:
        logger.error(f"Error in example workflow: {e}")
        raise
        
    finally:
        # 8. Cleanup services
        logger.info("Cleaning up services...")
        await cleanup_container()


async def example_batch_video_generation():
    """
    Example of batch video generation using refactored services.
    """
    
    try:
        # Setup container
        container = setup_service_container()
        await initialize_container()
        
        # Create user
        user = ClerkUser(
            clerk_user_id="enterprise_user_456",
            username="enterprise_user", 
            email_addresses=["enterprise@example.com"],
            subscription_tier="enterprise",
            created_at="2025-01-01T00:00:00Z"
        )
        
        # Create multiple requests
        requests = [
            VideoGenerationRequest(
                topic=f"Tutorial {i+1}: Advanced Python Concepts",
                context=f"Part {i+1} of a comprehensive Python series covering advanced topics.",
                quality=VideoQuality.MEDIUM,
                use_rag=False
            )
            for i in range(3)
        ]
        
        # Get use case service
        video_generation_use_case = get_video_generation_use_case()
        
        # Execute batch generation
        logger.info("Starting batch video generation...")
        result = await video_generation_use_case.generate_batch_videos(requests, user)
        
        if result.success:
            jobs = result.data
            logger.info(f"Batch generation started successfully!")
            logger.info(f"Created {len(jobs)} jobs")
            logger.info(f"Total cost: {result.metadata.get('total_cost')} credits")
            
            for job in jobs:
                logger.info(f"  Job {job.id}: {job.status}")
        else:
            logger.error(f"Batch generation failed: {result.error}")
        
    except Exception as e:
        logger.error(f"Error in batch workflow: {e}")
        raise
        
    finally:
        await cleanup_container()


def example_service_registration_inspection():
    """
    Example showing how to inspect service registrations.
    """
    
    # Setup container
    container = setup_service_container()
    
    # Get registration information
    registration_info = container.get_registration_info()
    
    logger.info("Service Registration Summary:")
    logger.info("=" * 50)
    
    for service_name, info in registration_info.items():
        logger.info(f"Service: {service_name}")
        logger.info(f"  Implementation: {info['implementation']}")
        logger.info(f"  Lifetime: {info['lifetime']}")
        logger.info(f"  Has Instance: {info['has_instance']}")
        logger.info(f"  Singleton Created: {info['is_singleton_created']}")
        logger.info("-" * 30)


if __name__ == "__main__":
    """
    Run examples of the refactored service layer.
    """
    
    async def run_examples():
        logger.info("=== Service Layer Refactoring Examples ===")
        
        # Example 1: Service registration inspection
        logger.info("\n1. Service Registration Inspection")
        example_service_registration_inspection()
        
        # Example 2: Single video generation
        logger.info("\n2. Single Video Generation Workflow")
        await example_video_generation_workflow()
        
        # Example 3: Batch video generation
        logger.info("\n3. Batch Video Generation Workflow")
        await example_batch_video_generation()
        
        logger.info("\n=== Examples completed ===")
    
    # Run the examples
    asyncio.run(run_examples())
