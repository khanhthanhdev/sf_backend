"""
Database package for AWS RDS integration.

This package contains database models, connection management,
migration utilities, and query methods for PostgreSQL integration.
"""

from .connection import (
    RDSConnectionManager, 
    ConnectionConfig,
    get_db_session, 
    get_db_connection,
    initialize_database,
    get_connection_manager,
    close_database,
    test_database_connectivity
)
from .models import Base, User, Job, FileMetadata, JobQueue
from .migrations import run_migrations, create_tables, check_database_status
from .pydantic_models import UserDB, JobDB, FileMetadataDB, JobQueueDB
from .queries import DatabaseQueries

__all__ = [
    # Connection management
    "RDSConnectionManager",
    "ConnectionConfig", 
    "get_db_session",
    "get_db_connection",
    "initialize_database",
    "get_connection_manager",
    "close_database",
    "test_database_connectivity",
    
    # Database models
    "Base",
    "User",
    "Job", 
    "FileMetadata",
    "JobQueue",
    
    # Pydantic models
    "UserDB",
    "JobDB",
    "FileMetadataDB", 
    "JobQueueDB",
    
    # Migrations
    "run_migrations",
    "create_tables",
    "check_database_status",
    
    # Queries
    "DatabaseQueries"
]