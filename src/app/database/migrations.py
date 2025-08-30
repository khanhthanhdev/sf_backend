"""
Database migration utilities for AWS RDS PostgreSQL.

This module provides functions to create tables, run migrations,
and manage database schema changes.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
import asyncio
import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .models import Base
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Database migration manager for PostgreSQL."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_tables(self) -> bool:
        """Create all tables defined in SQLAlchemy models."""
        try:
            logger.info("Creating database tables...")
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            return False
    
    def drop_tables(self) -> bool:
        """Drop all tables (use with caution!)."""
        try:
            logger.warning("Dropping all database tables...")
            Base.metadata.drop_all(bind=self.engine)
            logger.info("Database tables dropped successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            return False
    
    def run_sql_migration(self, sql_script: str) -> bool:
        """Run a raw SQL migration script."""
        try:
            with self.engine.connect() as connection:
                # Split script into individual statements
                statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]
                
                for statement in statements:
                    logger.info(f"Executing: {statement[:100]}...")
                    connection.execute(text(statement))
                    connection.commit()
                
                logger.info("SQL migration completed successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to run SQL migration: {e}")
            return False
    
    def check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = :table_name
                    );
                """), {"table_name": table_name})
                return result.scalar()
        except Exception as e:
            logger.error(f"Failed to check table existence: {e}")
            return False
    
    def get_table_info(self) -> Dict[str, Any]:
        """Get information about existing tables."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("""
                    SELECT 
                        table_name,
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position;
                """))
                
                tables = {}
                for row in result:
                    table_name = row[0]
                    if table_name not in tables:
                        tables[table_name] = []
                    
                    tables[table_name].append({
                        'column_name': row[1],
                        'data_type': row[2],
                        'is_nullable': row[3],
                        'column_default': row[4]
                    })
                
                return tables
        except Exception as e:
            logger.error(f"Failed to get table info: {e}")
            return {}


# Migration scripts as constants
INITIAL_MIGRATION_SQL = """
-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    clerk_user_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    image_url TEXT,
    email_addresses JSONB NOT NULL DEFAULT '[]',
    phone_numbers JSONB NOT NULL DEFAULT '[]',
    primary_email VARCHAR(255),
    primary_phone VARCHAR(50),
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    phone_verified BOOLEAN NOT NULL DEFAULT FALSE,
    two_factor_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_sign_in_at TIMESTAMP WITH TIME ZONE,
    last_active_at TIMESTAMP WITH TIME ZONE,
    user_metadata JSONB NOT NULL DEFAULT '{}',
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Create jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    job_type VARCHAR(50) NOT NULL DEFAULT 'video_generation',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    configuration JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    progress_percentage DECIMAL(5,2) NOT NULL DEFAULT 0,
    current_stage VARCHAR(100),
    stages_completed JSONB NOT NULL DEFAULT '[]',
    estimated_completion TIMESTAMP WITH TIME ZONE,
    processing_time_seconds DECIMAL(10,2),
    error_info JSONB,
    metrics JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    batch_id UUID,
    parent_job_id UUID REFERENCES jobs(id),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Create file_metadata table
CREATE TABLE IF NOT EXISTS file_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    job_id UUID REFERENCES jobs(id),
    file_type VARCHAR(50) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    s3_bucket VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500) NOT NULL,
    s3_version_id VARCHAR(255),
    file_size BIGINT NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    checksum VARCHAR(64),
    file_metadata JSONB NOT NULL DEFAULT '{}',
    description TEXT,
    tags JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Create job_queue table
CREATE TABLE IF NOT EXISTS job_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL UNIQUE REFERENCES jobs(id),
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    queue_status VARCHAR(50) NOT NULL DEFAULT 'queued',
    worker_id VARCHAR(255),
    processing_node VARCHAR(255),
    queued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    processing_started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    queue_position INTEGER
);
"""

INDEXES_MIGRATION_SQL = """
-- Create indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_clerk_id ON users(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(primary_email);
CREATE INDEX IF NOT EXISTS idx_users_role_status ON users(role, status);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_deleted, status);

-- Create indexes for jobs table
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority);
CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON jobs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_deleted, status);
CREATE INDEX IF NOT EXISTS idx_jobs_queue_priority ON jobs(status, priority, created_at);

-- Create indexes for file_metadata table
CREATE INDEX IF NOT EXISTS idx_files_user_id ON file_metadata(user_id);
CREATE INDEX IF NOT EXISTS idx_files_job_id ON file_metadata(job_id);
CREATE INDEX IF NOT EXISTS idx_files_type ON file_metadata(file_type);
CREATE INDEX IF NOT EXISTS idx_files_s3_key ON file_metadata(s3_key);
CREATE INDEX IF NOT EXISTS idx_files_created_at ON file_metadata(created_at);
CREATE INDEX IF NOT EXISTS idx_files_user_type ON file_metadata(user_id, file_type);
CREATE INDEX IF NOT EXISTS idx_files_active ON file_metadata(is_deleted);

-- Create indexes for job_queue table
CREATE INDEX IF NOT EXISTS idx_queue_job_id ON job_queue(job_id);
CREATE INDEX IF NOT EXISTS idx_queue_status ON job_queue(queue_status);
CREATE INDEX IF NOT EXISTS idx_queue_priority ON job_queue(priority);
CREATE INDEX IF NOT EXISTS idx_queue_position ON job_queue(queue_position);
CREATE INDEX IF NOT EXISTS idx_queue_processing ON job_queue(queue_status, priority, queued_at);
CREATE INDEX IF NOT EXISTS idx_queue_retry ON job_queue(next_retry_at, retry_count);
"""

BATCH_METADATA_MIGRATION_SQL = """
-- Create batch_metadata table for batch job management
CREATE TABLE IF NOT EXISTS batch_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id UUID NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES users(id),
    total_jobs INTEGER NOT NULL DEFAULT 0,
    created_jobs INTEGER NOT NULL DEFAULT 0,
    failed_jobs INTEGER NOT NULL DEFAULT 0,
    batch_priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    job_ids JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for batch_metadata table
CREATE INDEX IF NOT EXISTS idx_batch_metadata_batch_id ON batch_metadata(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_metadata_user_id ON batch_metadata(user_id);
CREATE INDEX IF NOT EXISTS idx_batch_metadata_created_at ON batch_metadata(created_at);
CREATE INDEX IF NOT EXISTS idx_batch_metadata_priority ON batch_metadata(batch_priority);
CREATE INDEX IF NOT EXISTS idx_batch_metadata_active ON batch_metadata(is_deleted);
"""

TRIGGERS_MIGRATION_SQL = """
-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at 
    BEFORE UPDATE ON jobs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_file_metadata_updated_at 
    BEFORE UPDATE ON file_metadata 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_batch_metadata_updated_at 
    BEFORE UPDATE ON batch_metadata 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""


def run_migrations(database_url: str = None) -> bool:
    """Run all database migrations."""
    if not database_url:
        settings = get_settings()
        database_url = f"postgresql://{settings.rds_username}:{settings.rds_password}@{settings.rds_endpoint}/{settings.rds_database}"
    
    migrator = DatabaseMigrator(database_url)
    
    try:
        logger.info("Starting database migrations...")
        
        # Run initial table creation
        logger.info("Running initial migration...")
        if not migrator.run_sql_migration(INITIAL_MIGRATION_SQL):
            return False
        
        # Create indexes
        logger.info("Creating indexes...")
        if not migrator.run_sql_migration(INDEXES_MIGRATION_SQL):
            return False
        
        # Create batch metadata table
        logger.info("Creating batch metadata table...")
        if not migrator.run_sql_migration(BATCH_METADATA_MIGRATION_SQL):
            return False
        
        # Create triggers
        logger.info("Creating triggers...")
        if not migrator.run_sql_migration(TRIGGERS_MIGRATION_SQL):
            return False
        
        logger.info("All migrations completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def create_tables(database_url: str = None) -> bool:
    """Create tables using SQLAlchemy models."""
    if not database_url:
        settings = get_settings()
        database_url = f"postgresql://{settings.rds_username}:{settings.rds_password}@{settings.rds_endpoint}/{settings.rds_database}"
    
    migrator = DatabaseMigrator(database_url)
    return migrator.create_tables()


def check_database_status(database_url: str = None) -> Dict[str, Any]:
    """Check database status and table information."""
    if not database_url:
        settings = get_settings()
        database_url = f"postgresql://{settings.rds_username}:{settings.rds_password}@{settings.rds_endpoint}/{settings.rds_database}"
    
    migrator = DatabaseMigrator(database_url)
    
    status = {
        "connected": False,
        "tables": {},
        "required_tables": ["users", "jobs", "file_metadata", "job_queue", "batch_metadata"],
        "missing_tables": [],
        "ready": False
    }
    
    try:
        # Check table information
        tables = migrator.get_table_info()
        status["tables"] = tables
        status["connected"] = True
        
        # Check for missing tables
        existing_tables = set(tables.keys())
        required_tables = set(status["required_tables"])
        missing_tables = required_tables - existing_tables
        status["missing_tables"] = list(missing_tables)
        
        # Database is ready if all required tables exist
        status["ready"] = len(missing_tables) == 0
        
        logger.info(f"Database status check completed. Ready: {status['ready']}")
        
    except Exception as e:
        logger.error(f"Database status check failed: {e}")
        status["error"] = str(e)
    
    return status


async def async_run_migrations(database_url: str = None) -> bool:
    """Run migrations asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_migrations, database_url)


# Migration management functions

def reset_database(database_url: str = None, confirm: bool = False) -> bool:
    """Reset database by dropping and recreating all tables."""
    if not confirm:
        logger.warning("Database reset requires confirmation. Set confirm=True to proceed.")
        return False
    
    if not database_url:
        settings = get_settings()
        database_url = f"postgresql://{settings.rds_username}:{settings.rds_password}@{settings.rds_endpoint}/{settings.rds_database}"
    
    migrator = DatabaseMigrator(database_url)
    
    try:
        logger.warning("Resetting database - dropping all tables...")
        if not migrator.drop_tables():
            return False
        
        logger.info("Recreating tables...")
        if not migrator.create_tables():
            return False
        
        logger.info("Running additional migrations...")
        if not migrator.run_sql_migration(INDEXES_MIGRATION_SQL):
            return False
        
        if not migrator.run_sql_migration(TRIGGERS_MIGRATION_SQL):
            return False
        
        logger.info("Database reset completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        return False


def backup_database_schema(database_url: str = None) -> str:
    """Generate SQL script to recreate current database schema."""
    # This would use pg_dump or similar tool to create a backup
    # For now, return the migration scripts
    return f"""
-- Database Schema Backup
-- Generated at: {datetime.utcnow()}

{INITIAL_MIGRATION_SQL}

{INDEXES_MIGRATION_SQL}

{TRIGGERS_MIGRATION_SQL}
"""


if __name__ == "__main__":
    # Allow running migrations directly
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "migrate":
            success = run_migrations()
            sys.exit(0 if success else 1)
        elif command == "status":
            status = check_database_status()
            print(f"Database Status: {status}")
            sys.exit(0 if status["ready"] else 1)
        elif command == "reset":
            confirm = len(sys.argv) > 2 and sys.argv[2] == "--confirm"
            success = reset_database(confirm=confirm)
            sys.exit(0 if success else 1)
        else:
            print("Usage: python migrations.py [migrate|status|reset]")
            sys.exit(1)
    else:
        print("Usage: python migrations.py [migrate|status|reset]")
        sys.exit(1)