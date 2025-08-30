"""
Test script for database integration.

This script tests the database connection, models, and basic operations
to verify the RDS integration is working correctly.
"""

import asyncio
import logging
from uuid import uuid4
from datetime import datetime

from .connection import ConnectionConfig, RDSConnectionManager, test_database_connectivity
from .migrations import run_migrations, check_database_status
from .pydantic_models import UserDB, JobDB, FileMetadataDB
from .queries import DatabaseQueries
from ..models.user import UserRole, UserStatus
from ..models.job import JobStatus, JobType, JobPriority

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_database_connection():
    """Test basic database connectivity."""
    logger.info("Testing database connectivity...")
    
    try:
        # Test connectivity without creating a full connection manager
        result = await test_database_connectivity()
        
        if result["connected"]:
            logger.info(f"✅ Database connection successful")
            logger.info(f"   Server version: {result['server_version']}")
            logger.info(f"   Database size: {result['database_size']}")
            logger.info(f"   Connection time: {result['connection_time']:.3f}s")
            return True
        else:
            logger.error(f"❌ Database connection failed: {result['error']}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return False


async def test_database_schema():
    """Test database schema and migrations."""
    logger.info("Testing database schema...")
    
    try:
        # Check database status
        status = check_database_status()
        
        if status["connected"]:
            logger.info(f"✅ Database schema check successful")
            logger.info(f"   Tables found: {list(status['tables'].keys())}")
            
            if status["missing_tables"]:
                logger.warning(f"   Missing tables: {status['missing_tables']}")
                logger.info("   Running migrations...")
                
                if run_migrations():
                    logger.info("✅ Migrations completed successfully")
                    return True
                else:
                    logger.error("❌ Migrations failed")
                    return False
            else:
                logger.info("✅ All required tables present")
                return True
        else:
            logger.error(f"❌ Database schema check failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Database schema test failed: {e}")
        return False


async def test_pydantic_models():
    """Test Pydantic model creation and validation."""
    logger.info("Testing Pydantic models...")
    
    try:
        # Test UserDB model
        user_data = UserDB(
            clerk_user_id="test_clerk_123",
            username="testuser",
            first_name="Test",
            last_name="User",
            primary_email="test@example.com",
            role=UserRole.USER,
            status=UserStatus.ACTIVE
        )
        
        logger.info(f"✅ UserDB model created: {user_data.id}")
        
        # Test JobDB model
        job_data = JobDB(
            user_id=user_data.id,
            job_type=JobType.VIDEO_GENERATION,
            priority=JobPriority.NORMAL,
            configuration={
                "topic": "Test Topic",
                "context": "Test context for video generation",
                "quality": "medium"
            },
            status=JobStatus.QUEUED
        )
        
        logger.info(f"✅ JobDB model created: {job_data.id}")
        
        # Test FileMetadataDB model
        file_data = FileMetadataDB(
            user_id=user_data.id,
            job_id=job_data.id,
            file_type="video",
            original_filename="test_video.mp4",
            stored_filename="stored_test_video.mp4",
            s3_bucket="test-bucket",
            s3_key="test/path/video.mp4",
            file_size=1024000,
            content_type="video/mp4"
        )
        
        logger.info(f"✅ FileMetadataDB model created: {file_data.id}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Pydantic models test failed: {e}")
        return False


async def test_database_operations():
    """Test database operations with real connection."""
    logger.info("Testing database operations...")
    
    try:
        # Create connection config (you'll need to set these environment variables)
        config = ConnectionConfig(
            host="localhost",  # Replace with your RDS endpoint
            port=5432,
            database="test_db",  # Replace with your database name
            username="test_user",  # Replace with your username
            password="test_password"  # Replace with your password
        )
        
        # Create connection manager
        manager = RDSConnectionManager(config)
        
        if not await manager.initialize():
            logger.error("❌ Failed to initialize connection manager")
            return False
        
        try:
            # Test basic query operations
            async with manager.get_session() as session:
                queries = DatabaseQueries(session)
                
                # Test user operations
                user_data = UserDB(
                    clerk_user_id=f"test_clerk_{uuid4()}",
                    username="testuser_db",
                    first_name="Test",
                    last_name="User",
                    primary_email="testdb@example.com",
                    role=UserRole.USER,
                    status=UserStatus.ACTIVE
                )
                
                created_user = await queries.create_user(user_data)
                logger.info(f"✅ Created user in database: {created_user.id}")
                
                # Test retrieving user
                retrieved_user = await queries.get_user_by_id(created_user.id)
                if retrieved_user:
                    logger.info(f"✅ Retrieved user from database: {retrieved_user.username}")
                else:
                    logger.error("❌ Failed to retrieve user from database")
                    return False
                
                # Test job operations
                job_data = JobDB(
                    user_id=created_user.id,
                    job_type=JobType.VIDEO_GENERATION,
                    priority=JobPriority.NORMAL,
                    configuration={
                        "topic": "Database Test Topic",
                        "context": "Testing database integration",
                        "quality": "medium"
                    },
                    status=JobStatus.QUEUED
                )
                
                created_job = await queries.create_job(job_data)
                logger.info(f"✅ Created job in database: {created_job.id}")
                
                # Test user stats
                stats = await queries.get_user_stats(created_user.id)
                logger.info(f"✅ Retrieved user stats: {stats}")
                
                logger.info("✅ All database operations completed successfully")
                return True
                
        finally:
            await manager.close()
            
    except Exception as e:
        logger.error(f"❌ Database operations test failed: {e}")
        return False


async def run_all_tests():
    """Run all database integration tests."""
    logger.info("🚀 Starting database integration tests...")
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Database Schema", test_database_schema),
        ("Pydantic Models", test_pydantic_models),
        # ("Database Operations", test_database_operations),  # Uncomment when you have DB credentials
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running {test_name} test...")
        try:
            results[test_name] = await test_func()
        except Exception as e:
            logger.error(f"❌ {test_name} test failed with exception: {e}")
            results[test_name] = False
    
    # Print summary
    logger.info("\n📊 Test Results Summary:")
    logger.info("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name:<25} {status}")
        if result:
            passed += 1
    
    logger.info("=" * 50)
    logger.info(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
        return True
    else:
        logger.error(f"💥 {total - passed} tests failed!")
        return False


if __name__ == "__main__":
    # Run tests
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)