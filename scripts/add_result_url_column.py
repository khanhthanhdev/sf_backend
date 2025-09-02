#!/usr/bin/env python3
"""
Add result_url column to jobs table.

This script adds the missing result_url column to the jobs table to fix
the AttributeError in VideoService.
"""

import asyncio
import logging
import sys
from pathlib import Path
from sqlalchemy import text

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.database.connection import RDSConnectionManager, ConnectionConfig
from src.config.aws_config import AWSConfigManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_result_url_column():
    """Add result_url column to jobs table."""
    try:
        logger.info("Adding result_url column to jobs table...")
        
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
        
        # Add the result_url column
        async with db_manager.get_session() as session:
            # Check if column already exists
            check_sql = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' AND column_name = 'result_url'
            """)
            
            result = await session.execute(check_sql)
            existing_column = result.fetchone()
            
            if existing_column:
                logger.info("result_url column already exists")
                return True
            
            # Add the column
            add_column_sql = text("""
            ALTER TABLE jobs 
            ADD COLUMN result_url VARCHAR(500)
            """)
            
            await session.execute(add_column_sql)
            await session.commit()
            
            logger.info("Successfully added result_url column to jobs table")
            return True
            
    except Exception as e:
        logger.error(f"Failed to add result_url column: {e}")
        return False
    finally:
        if 'db_manager' in locals():
            await db_manager.close()


if __name__ == "__main__":
    asyncio.run(add_result_url_column())
