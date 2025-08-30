#!/usr/bin/env python3
"""
Run initial database schema migration.

This script creates the basic database schema with users, jobs, 
file_metadata, and job_queue tables.
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


async def run_initial_migration():
    """Run the initial database schema migration."""
    try:
        logger.info("Starting initial database schema migration...")
        
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
        
        # Read migration file
        migration_file = Path(__file__).parent.parent / "src/app/database/migrations/001_initial_schema.sql"
        
        if not migration_file.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_file}")
        
        migration_sql = migration_file.read_text()
        logger.info(f"Loaded migration from {migration_file}")
        
        # Check if migration already applied
        try:
            existing_migration = await db_manager.execute_query(
                "SELECT version FROM migration_log WHERE version = $1",
                {'version': 1}
            )
            
            if existing_migration:
                logger.info("Migration 001 already applied, skipping...")
                return
        except Exception:
            # migration_log table doesn't exist yet, continue with migration
            pass
        
        # Execute migration in transaction
        async with db_manager.transaction() as conn:
            # Execute the entire migration as one script
            try:
                logger.info("Executing migration script...")
                await conn.execute(migration_sql)
                logger.info("Migration script executed successfully")
            except Exception as e:
                logger.error(f"Failed to execute migration: {e}")
                raise
        
        logger.info("Initial schema migration completed successfully")
        
        # Verify tables were created
        tables_to_check = ['users', 'jobs', 'file_metadata', 'job_queue', 'migration_log']
        
        for table in tables_to_check:
            result = await db_manager.execute_query(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = $1
                )
                """,
                {'table_name': table}
            )
            
            if result and result[0]['exists']:
                logger.info(f"✓ Table {table} created successfully")
            else:
                logger.error(f"✗ Table {table} was not created")
        
        await db_manager.close()
        logger.info("Initial migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_initial_migration())