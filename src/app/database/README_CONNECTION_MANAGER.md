# Enhanced RDS Connection Manager

## Overview

The enhanced `RDSConnectionManager` provides comprehensive async database connectivity for AWS RDS PostgreSQL with full Pydantic model integration. This implementation fulfills the requirements for task 2.2 of the AWS infrastructure setup.

## Features

### Core Functionality
- ✅ **Async PostgreSQL Connection**: Uses `asyncpg` for high-performance async database operations
- ✅ **Connection Pooling**: Configurable connection pool with health monitoring
- ✅ **Retry Logic**: Exponential backoff retry mechanism for failed operations
- ✅ **Health Checks**: Periodic health monitoring with automatic reconnection
- ✅ **Pydantic Integration**: Direct support for Pydantic model CRUD operations
- ✅ **Transaction Support**: ACID-compliant transaction management
- ✅ **Bulk Operations**: Efficient bulk insert/update operations
- ✅ **Error Handling**: Comprehensive error handling with detailed logging

### Requirements Compliance

#### Requirement 2.1: Connection Pooling
- ✅ Configurable connection pool (min/max connections)
- ✅ Connection timeout and recycling settings
- ✅ Pool statistics and monitoring

#### Requirement 2.2: ACID Compliance
- ✅ Transaction context managers
- ✅ Automatic rollback on errors
- ✅ Consistent data persistence

#### Requirement 2.4: Performance & Indexing
- ✅ Connection pooling for consistent performance
- ✅ Query performance monitoring
- ✅ Optimized bulk operations

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
├─────────────────────────────────────────────────────────────┤
│                 Pydantic Models                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │   UserDB    │ │   JobDB     │ │   FileMetadataDB        ││
│  └─────────────┘ └─────────────┘ └─────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│              Repository Pattern (Optional)                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │         PydanticModelRepository                         ││
│  └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│                RDSConnectionManager                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │ Connection  │ │   Health    │ │   Pydantic Model        ││
│  │   Pool      │ │   Monitor   │ │   Integration           ││
│  └─────────────┘ └─────────────┘ └─────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│                Database Drivers                             │
│  ┌─────────────┐ ┌─────────────────────────────────────────┐│
│  │   asyncpg   │ │         SQLAlchemy                      ││
│  │  (Direct)   │ │        (ORM Support)                    ││
│  └─────────────┘ └─────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│                   AWS RDS PostgreSQL                       │
└─────────────────────────────────────────────────────────────┘
```

## Usage Examples

### Basic Setup

```python
from src.app.database.connection import (
    RDSConnectionManager, 
    ConnectionConfig,
    initialize_database
)

# Initialize global connection manager
config = ConnectionConfig(
    host="your-rds-endpoint.amazonaws.com",
    port=5432,
    database="your_database",
    username="your_username",
    password="your_password",
    min_connections=5,
    max_connections=20
)

manager = await initialize_database(config)
```

### Pydantic Model Operations

```python
from src.app.database.pydantic_models import UserDB, JobDB

# Save a user
user = UserDB(
    clerk_user_id="user_123",
    email="user@example.com",
    username="testuser"
)

result = await manager.save_pydantic_model(
    user, 
    "users", 
    conflict_columns=["clerk_user_id"]  # Upsert on conflict
)

# Get a user
user = await manager.get_pydantic_model(
    UserDB, 
    "users", 
    "clerk_user_id = $1", 
    ["user_123"]
)

# Get multiple users
users = await manager.get_pydantic_models(
    UserDB,
    "users",
    "is_deleted = $1",
    [False],
    order_by="created_at DESC",
    limit=10
)

# Update a user
user.username = "updated_username"
success = await manager.update_pydantic_model(
    user,
    "users",
    "id = $1",
    [user.id]
)

# Delete a user (soft delete)
success = await manager.delete_pydantic_model(
    "users",
    "id = $1",
    [user.id],
    soft_delete=True
)
```

### Transaction Management

```python
# Complex operation with transaction
async with manager.transaction() as conn:
    # Create user
    user_result = await conn.fetchrow(
        "INSERT INTO users (clerk_user_id, email) VALUES ($1, $2) RETURNING *",
        "user_123", "user@example.com"
    )
    
    # Create related job
    job_result = await conn.fetchrow(
        "INSERT INTO jobs (user_id, status, configuration) VALUES ($1, $2, $3) RETURNING *",
        user_result['id'], "queued", '{"topic": "test"}'
    )
    
    # Both operations succeed or both fail
```

### Repository Pattern

```python
from src.app.database.connection import PydanticModelRepository

# Create repository
user_repo = PydanticModelRepository(manager, UserDB, "users")

# CRUD operations
user = await user_repo.create(user_data)
user = await user_repo.get_by_id(user_id)
users = await user_repo.get_where("status = $1", ["active"])
success = await user_repo.update_by_id(user_id, updated_user)
success = await user_repo.delete_by_id(user_id)

# Bulk operations
users = await user_repo.bulk_create(user_list)
count = await user_repo.count("is_deleted = $1", [False])
exists = await user_repo.exists("email = $1", ["test@example.com"])
```

### Health Monitoring

```python
# Check connection health
is_healthy = manager.is_healthy
is_initialized = manager.is_initialized

# Get detailed statistics
stats = await manager.get_pool_stats()
print(f"Active connections: {stats['asyncpg_pool']['size']}")
print(f"Total queries: {stats['stats']['total_queries']}")
print(f"Average query time: {stats['stats']['avg_query_time']:.3f}s")

# Manual health check
health_ok = await manager.health_check()
```

## Configuration Options

### ConnectionConfig Parameters

```python
config = ConnectionConfig(
    # Basic connection
    host="your-rds-endpoint.amazonaws.com",
    port=5432,
    database="your_database", 
    username="your_username",
    password="your_password",
    
    # Connection pool settings
    min_connections=5,          # Minimum pool size
    max_connections=20,         # Maximum pool size
    max_overflow=10,            # SQLAlchemy overflow
    pool_timeout=30,            # Connection timeout (seconds)
    pool_recycle=3600,          # Connection recycle time (seconds)
    
    # Retry settings
    max_retries=3,              # Maximum retry attempts
    retry_delay=1.0,            # Initial retry delay (seconds)
    retry_backoff=2.0,          # Backoff multiplier
    
    # Health check settings
    health_check_interval=30,   # Health check interval (seconds)
    connection_timeout=10       # Individual connection timeout
)
```

## Error Handling

The connection manager provides comprehensive error handling:

### Connection Errors
- Automatic retry with exponential backoff
- Connection pool recreation on failure
- Graceful degradation during outages

### Query Errors
- Transaction rollback on failure
- Detailed error logging with context
- Query performance tracking

### Health Check Failures
- Automatic reconnection attempts
- Health status reporting
- Background monitoring

## Performance Features

### Connection Pooling
- Configurable pool sizes for different environments
- Connection recycling to prevent stale connections
- Pool statistics for monitoring

### Query Optimization
- Prepared statement support through asyncpg
- Bulk operation methods for better throughput
- Query performance metrics collection

### Monitoring
- Real-time connection statistics
- Query performance tracking
- Health check monitoring

## Integration with FastAPI

```python
from fastapi import Depends
from src.app.database.connection import get_db_session, get_db_connection

# SQLAlchemy session dependency
@app.get("/users/{user_id}")
async def get_user(user_id: str, session: AsyncSession = Depends(get_db_session)):
    # Use SQLAlchemy ORM
    pass

# Direct asyncpg connection dependency  
@app.get("/stats")
async def get_stats(conn: Connection = Depends(get_db_connection)):
    # Use direct asyncpg for performance
    pass
```

## Testing

The implementation includes comprehensive tests:

```bash
# Run connection manager tests
python src/app/database/test_connection_manager.py

# Run simple validation tests
python test_connection_simple.py
```

## Migration from Redis

The enhanced connection manager supports migration from Redis-based storage:

1. **Dual Write Phase**: Write to both Redis and RDS
2. **Data Migration**: Transfer existing Redis data to RDS
3. **Validation Phase**: Verify data integrity
4. **Cutover Phase**: Switch to RDS-only operations

## Best Practices

### Connection Management
- Always use connection managers or dependency injection
- Close connections properly in finally blocks
- Monitor connection pool statistics

### Error Handling
- Implement proper retry logic for transient failures
- Log errors with sufficient context for debugging
- Use transactions for multi-step operations

### Performance
- Use bulk operations for multiple records
- Implement proper indexing on frequently queried columns
- Monitor query performance and optimize slow queries

### Security
- Use parameterized queries to prevent SQL injection
- Implement proper access controls
- Encrypt sensitive data at rest and in transit

## Troubleshooting

### Common Issues

1. **Connection Pool Exhaustion**
   - Increase `max_connections` in configuration
   - Check for connection leaks in application code
   - Monitor connection usage patterns

2. **Slow Query Performance**
   - Check database indexes
   - Analyze query execution plans
   - Consider connection pool tuning

3. **Health Check Failures**
   - Verify network connectivity to RDS
   - Check RDS instance status
   - Review security group settings

### Debugging

Enable detailed logging:
```python
import logging
logging.getLogger('src.app.database.connection').setLevel(logging.DEBUG)
```

Monitor connection statistics:
```python
stats = await manager.get_pool_stats()
logger.info(f"Connection stats: {stats}")
```

## Dependencies

Required packages (added to requirements.txt):
- `asyncpg>=0.29.0` - Async PostgreSQL driver
- `sqlalchemy[asyncio]>=2.0.0` - SQLAlchemy with async support
- `psycopg2-binary>=2.9.9` - PostgreSQL adapter (fallback)
- `pydantic>=2.5.0` - Data validation and serialization

## Conclusion

The enhanced RDSConnectionManager provides a robust, scalable, and feature-rich solution for AWS RDS PostgreSQL connectivity with full Pydantic model integration. It meets all requirements for connection pooling, retry logic, health checks, and ACID compliance while providing high-level abstractions for common database operations.