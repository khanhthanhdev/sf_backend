#!/usr/bin/env python3
"""
Run user service database migration.

This script applies the user service migration to create the necessary
tables for user sessions, permissions, and activity logging.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.database.connection import RDSConnectionManager, ConnectionConfig
from src.config.aws_config import AWSConfigManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migration():
    """Run the user service migration."""
    try:
        logger.info("Starting user service migration...")
        
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
        migration_file = Path(__file__).parent.parent / "src/app/database/migrations/006_user_service_tables.sql"
        
        if not migration_file.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_file}")
        
        migration_sql = migration_file.read_text()
        logger.info(f"Loaded migration from {migration_file}")
        
        # Create migration_log table if it doesn't exist
        await db_manager.execute_command("""
            CREATE TABLE IF NOT EXISTS migration_log (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if migration already applied
        existing_migration = await db_manager.execute_query(
            "SELECT version FROM migration_log WHERE version = $1",
            {'version': 6}
        )
        
        if existing_migration:
            logger.info("Migration 006 already applied, skipping...")
            return
        
        # Execute migration in transaction
        async with db_manager.transaction() as conn:
            # Execute the entire migration as one script
            try:
                logger.info("Executing user service migration script...")
                await conn.execute(migration_sql)
                logger.info("User service migration script executed successfully")
            except Exception as e:
                logger.error(f"Failed to execute migration: {e}")
                raise
        
        logger.info("User service migration completed successfully")
        
        # Verify tables were created
        tables_to_check = ['user_sessions', 'user_permissions', 'user_activity_log']
        
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
        
        # Test basic operations
        logger.info("Testing basic database operations...")
        
        from datetime import datetime, timedelta
        
        # Test user sessions table
        test_expires_at = datetime.utcnow() + timedelta(hours=1)
        await db_manager.execute_command(
            "INSERT INTO user_sessions (clerk_user_id, expires_at) VALUES ($1, $2)",
            {
                'clerk_user_id': 'test_user_migration',
                'expires_at': test_expires_at
            }
        )
        
        # Clean up test data
        await db_manager.execute_command(
            "DELETE FROM user_sessions WHERE clerk_user_id = $1",
            {'clerk_user_id': 'test_user_migration'}
        )
        
        logger.info("✓ Database operations test passed")
        
        await db_manager.close()
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_migration())