# Database Connection Management Fixes

## Problem Identified

The error message:
```
The garbage collector is trying to clean up non-checked-in connection <AdaptedConnection <asyncpg.connection.Connection object at 0x71b760999990>>, which will be terminated. Please ensure that SQLAlchemy pooled connections are returned to the pool explicitly, either by calling ``close()`` or by using appropriate context managers to manage their lifecycle.
```

This indicates that database connections were not being properly closed, causing the garbage collector to forcibly clean them up.

## Root Causes

1. **Improper session cleanup in `get_session()` context manager**
   - The `finally` block was only closing sessions when `session.is_active` was False
   - Sessions should always be closed regardless of their state

2. **Mixed async API usage**
   - AWS Video Service was using asyncpg methods (`session.fetchval()`, `session.fetchrow()`, `session.fetch()`) on SQLAlchemy sessions
   - SQLAlchemy async sessions use different methods like `session.execute(text())` with named parameters

3. **Missing transaction management**
   - Some database operations weren't properly committing transactions
   - Sessions were left in inconsistent states

## Fixes Applied

### 1. Enhanced Session Context Manager (`src/app/database/connection.py`)

**Before:**
```python
finally:
    if session and not session.is_active:
        await session.close()
```

**After:**
```python
finally:
    # Always ensure session is properly closed
    if session:
        try:
            # Close the session regardless of its state
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing database session: {e}")
```

**Key improvements:**
- Sessions are now **always** closed in the finally block
- Added explicit transaction commit for successful operations
- Better error handling during rollback operations
- Proper session cleanup after connection errors

### 2. Fixed AWS Video Service Database Calls (`src/app/services/aws_video_service.py`)

**Before (asyncpg syntax):**
```python
row = await session.fetchrow(
    """SELECT * FROM file_metadata WHERE id = $1 AND user_id = $2""",
    video_id, user_id
)
```

**After (SQLAlchemy syntax):**
```python
result = await session.execute(
    text("""SELECT * FROM file_metadata WHERE id = :video_id AND user_id = :user_id"""),
    {"video_id": video_id, "user_id": user_id}
)
row = result.mappings().first()
```

**Changes made:**
- Replaced `session.fetchval()`, `session.fetchrow()`, `session.fetch()` with `session.execute(text())`
- Changed positional parameters (`$1`, `$2`) to named parameters (`:video_id`, `:user_id`)
- Added proper JSON serialization for metadata fields
- Added explicit `await session.commit()` calls

### 3. Improved Connection Pool Management

**Enhanced close() method:**
```python
async def close(self):
    """Close all connections and cleanup resources."""
    # Close SQLAlchemy engine first (it depends on the connection pool)
    if self.engine:
        try:
            await self.engine.dispose()  # Properly dispose of all connections
        except Exception as e:
            logger.warning(f"Error disposing SQLAlchemy engine: {e}")
        finally:
            self.engine = None
            self.async_session_factory = None
    
    # Close asyncpg pool
    if self.pool:
        try:
            await self.pool.close()  # Gracefully close all connections
        except Exception as e:
            logger.warning(f"Error closing AsyncPG pool: {e}")
        finally:
            self.pool = None
```

### 4. Better Transaction Management

**Added explicit commits in health checks:**
```python
async with self.get_session() as session:
    result = await session.execute(text("SELECT 1"))
    result.scalar()
    # Explicitly commit to ensure session is clean
    await session.commit()
```

## Testing the Fixes

### Run Connection Test
```bash
cd test_scripts
python test_video_generation.py --token=your_token_here --topic="Test Connection Management"
```

### Monitor Database Connections
```python
# In your application, check connection pool status
manager = get_connection_manager()
stats = await manager.get_pool_stats()
print(f"Active connections: {stats['sqlalchemy_pool']['checked_out']}")
print(f"Pool size: {stats['sqlalchemy_pool']['size']}")
```

### Expected Behavior After Fixes

1. **No more garbage collector warnings** about unclosed connections
2. **Proper connection pooling** with connections returned to the pool
3. **Clean session lifecycle** with explicit commits and rollbacks
4. **Better error handling** during connection issues
5. **Improved performance** due to proper connection reuse

## Best Practices for Future Development

1. **Always use context managers** for database sessions:
   ```python
   async with db_manager.get_session() as session:
       # Your database operations
       await session.commit()  # Explicit commit if needed
   ```

2. **Use SQLAlchemy syntax** consistently:
   ```python
   # Correct
   result = await session.execute(text("SELECT * FROM table WHERE id = :id"), {"id": value})
   
   # Wrong (asyncpg syntax)
   result = await session.fetchrow("SELECT * FROM table WHERE id = $1", value)
   ```

3. **Handle transactions explicitly**:
   ```python
   try:
       # Database operations
       await session.commit()
   except Exception:
       await session.rollback()
       raise
   ```

4. **Close resources properly** in production:
   ```python
   # In your application shutdown
   await close_database()
   ```

These fixes ensure that your T2M application properly manages database connections, preventing memory leaks and improving overall system stability.