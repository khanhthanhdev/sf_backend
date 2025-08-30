#!/usr/bin/env python3
"""
Check database schema and existing tables.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.database.connection import RDSConnectionManager, ConnectionConfig
from src.config.aws_config import AWSConfigManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_schema():
    """Check existing database schema."""
    try:
        logger.info("Checking database schema...")
        
        # Load AWS configuration
        config = AWSConfigManager.load_config()
        
        # Create connection configuration
        connection_config = ConnectionConfig(
            host=config.rds_endpoint.split(':')[0],
            port=int(config.rds_endpoint.split(':')[1]) if ':' in config.rds_endpoint else 5432,
            database=config.rds_database,
            username=config.rds_username,
            password=config.rds_password
        )
        
        # Initialize connection manager
        db_manager = RDSConnectionManager(connection_config)
        success = await db_manager.initialize()
        
        if not success:
            raise RuntimeError("Failed to initialize database connection")
        
        logger.info("Database connection established")
        
        # Check existing tables
        tables = await db_manager.execute_query("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        logger.info("Existing tables:")
        for table in tables:
            logger.info(f"  - {table['table_name']}")
        
        # Check if users table exists
        users_exists = await db_manager.execute_query("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            )
        """)
        
        if users_exists and users_exists[0]['exists']:
            logger.info("✓ Users table exists")
            
            # Check users table structure
            columns = await db_manager.execute_query("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'users'
                ORDER BY ordinal_position
            """)
            
            logger.info("Users table columns:")
            for col in columns:
                logger.info(f"  - {col['column_name']}: {col['data_type']} ({'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'})")
        else:
            logger.warning("✗ Users table does not exist")
        
        await db_manager.close()
        
    except Exception as e:
        logger.error(f"Schema check failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(check_schema())