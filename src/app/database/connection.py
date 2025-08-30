"""
Async database connection manager for AWS RDS PostgreSQL.

This module provides connection pooling, retry logic, health checks,
and async database operations using asyncpg and SQLAlchemy.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List, AsyncGenerator, Union, Type, TypeVar
import time
from datetime import datetime, timedelta
import json

import asyncpg
from asyncpg import Pool, Connection
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from sqlalchemy.exc import DisconnectionError, OperationalError
from sqlalchemy import text, select, insert, update, delete
from pydantic import BaseModel

from ..core.config import get_settings

# Type variable for Pydantic models
T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


class ConnectionConfig(BaseModel):
    """Database connection configuration."""
    
    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    
    # Connection pool settings
    min_connections: int = 5
    max_connections: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600  # 1 hour
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    
    # Health check settings
    health_check_interval: int = 30  # seconds
    connection_timeout: int = 10
    
    @property
    def asyncpg_dsn(self) -> str:
        """Get asyncpg connection string."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def sqlalchemy_url(self) -> str:
        """Get SQLAlchemy async connection string."""
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class ConnectionStats(BaseModel):
    """Connection pool statistics."""
    
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    total_queries: int = 0
    failed_queries: int = 0
    avg_query_time: float = 0.0
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"


class RDSConnectionManager:
    """
    Async database connection manager for AWS RDS PostgreSQL.
    
    Provides connection pooling, retry logic, health checks, and
    async database operations with both asyncpg and SQLAlchemy support.
    """
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.pool: Optional[Pool] = None
        self.engine = None
        self.async_session_factory = None
        self.stats = ConnectionStats()
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_healthy = False
        self._last_health_check = None
        
        logger.info(f"Initializing RDS connection manager for {config.host}:{config.port}/{config.database}")
    
    async def initialize(self) -> bool:
        """Initialize connection pool and SQLAlchemy engine."""
        try:
            logger.info("Initializing database connections...")
            
            # Create asyncpg connection pool
            await self._create_asyncpg_pool()
            
            # Create SQLAlchemy async engine
            await self._create_sqlalchemy_engine()
            
            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            # Perform initial health check
            await self.health_check()
            
            logger.info("Database connection manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize database connections: {e}")
            await self.close()
            return False
    
    async def _create_asyncpg_pool(self):
        """Create asyncpg connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                dsn=self.config.asyncpg_dsn,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections,
                command_timeout=self.config.connection_timeout,
                server_settings={
                    'application_name': 't2m_app',
                    'timezone': 'UTC'
                }
            )
            logger.info(f"Created asyncpg pool with {self.config.min_connections}-{self.config.max_connections} connections")
            
        except Exception as e:
            logger.error(f"Failed to create asyncpg pool: {e}")
            raise
    
    async def _create_sqlalchemy_engine(self):
        """Create SQLAlchemy async engine."""
        try:
            self.engine = create_async_engine(
                self.config.sqlalchemy_url,
                pool_size=self.config.min_connections,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=True,
                echo=False  # Set to True for SQL debugging
            )
            
            self.async_session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info("Created SQLAlchemy async engine and session factory")
            
        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy engine: {e}")
            raise
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Connection, None]:
        """Get asyncpg connection from pool with retry logic."""
        connection = None
        retry_count = 0
        
        while retry_count <= self.config.max_retries:
            try:
                if not self.pool:
                    raise RuntimeError("Connection pool not initialized")
                
                connection = await self.pool.acquire()
                self.stats.active_connections += 1
                
                yield connection
                break
                
            except Exception as e:
                self.stats.failed_connections += 1
                
                if retry_count >= self.config.max_retries:
                    logger.error(f"Failed to get connection after {retry_count} retries: {e}")
                    raise
                
                retry_count += 1
                delay = self.config.retry_delay * (self.config.retry_backoff ** (retry_count - 1))
                logger.warning(f"Connection failed, retrying in {delay}s (attempt {retry_count}): {e}")
                await asyncio.sleep(delay)
                
            finally:
                if connection:
                    try:
                        await self.pool.release(connection)
                        self.stats.active_connections -= 1
                    except Exception as e:
                        logger.error(f"Failed to release connection: {e}")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get SQLAlchemy async session with retry logic."""
        session = None
        retry_count = 0
        
        while retry_count <= self.config.max_retries:
            try:
                if not self.async_session_factory:
                    raise RuntimeError("Session factory not initialized")
                
                session = self.async_session_factory()
                yield session
                
                # If we reach here, the session was used successfully
                if session and session.in_transaction():
                    await session.commit()
                break
                
            except (DisconnectionError, OperationalError) as e:
                self.stats.failed_connections += 1
                
                if session:
                    try:
                        await session.rollback()
                    except Exception:
                        pass  # Ignore rollback errors during connection issues
                    finally:
                        await session.close()
                        session = None
                
                if retry_count >= self.config.max_retries:
                    logger.error(f"Failed to get session after {retry_count} retries: {e}")
                    raise
                
                retry_count += 1
                delay = self.config.retry_delay * (self.config.retry_backoff ** (retry_count - 1))
                logger.warning(f"Session failed, retrying in {delay}s (attempt {retry_count}): {e}")
                await asyncio.sleep(delay)
                
                # Recreate engine on connection errors
                await self._recreate_engine()
                
            except Exception as e:
                # Handle any other exceptions
                if session:
                    try:
                        await session.rollback()
                    except Exception:
                        pass  # Ignore rollback errors
                    finally:
                        await session.close()
                        session = None
                raise
                
            finally:
                # Always ensure session is properly closed
                if session:
                    try:
                        # Close the session regardless of its state
                        await session.close()
                    except Exception as e:
                        logger.warning(f"Error closing database session: {e}")
    
    async def _recreate_engine(self):
        """Recreate SQLAlchemy engine after connection failure."""
        try:
            logger.info("Recreating SQLAlchemy engine after connection failure")
            
            if self.engine:
                await self.engine.dispose()
            
            await self._create_sqlalchemy_engine()
            
        except Exception as e:
            logger.error(f"Failed to recreate engine: {e}")
            raise
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a query using asyncpg and return results."""
        start_time = time.time()
        
        try:
            async with self.get_connection() as conn:
                if params:
                    result = await conn.fetch(query, *params.values())
                else:
                    result = await conn.fetch(query)
                
                # Convert to list of dictionaries
                rows = [dict(row) for row in result]
                
                self.stats.total_queries += 1
                query_time = time.time() - start_time
                self._update_avg_query_time(query_time)
                
                return rows
                
        except Exception as e:
            self.stats.failed_queries += 1
            logger.error(f"Query execution failed: {e}")
            raise
    
    async def execute_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Execute a command using asyncpg and return status."""
        start_time = time.time()
        
        try:
            async with self.get_connection() as conn:
                if params:
                    result = await conn.execute(command, *params.values())
                else:
                    result = await conn.execute(command)
                
                self.stats.total_queries += 1
                query_time = time.time() - start_time
                self._update_avg_query_time(query_time)
                
                return result
                
        except Exception as e:
            self.stats.failed_queries += 1
            logger.error(f"Command execution failed: {e}")
            raise
    
    # Pydantic model integration methods
    
    async def save_pydantic_model(self, model: BaseModel, table_name: str, 
                                 conflict_columns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Save a Pydantic model to the database with upsert capability.
        
        Args:
            model: Pydantic model instance to save
            table_name: Database table name
            conflict_columns: Columns to check for conflicts (for upsert)
            
        Returns:
            Dictionary with saved record data
        """
        start_time = time.time()
        
        try:
            # Convert Pydantic model to dictionary
            model_data = model.model_dump(exclude_none=True)
            
            # Handle datetime serialization
            for key, value in model_data.items():
                if isinstance(value, datetime):
                    model_data[key] = value.isoformat()
                elif isinstance(value, (dict, list)):
                    model_data[key] = json.dumps(value)
            
            async with self.get_connection() as conn:
                if conflict_columns:
                    # Upsert operation
                    columns = list(model_data.keys())
                    placeholders = [f"${i+1}" for i in range(len(columns))]
                    values = list(model_data.values())
                    
                    # Build conflict resolution
                    update_columns = [col for col in columns if col not in conflict_columns]
                    update_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
                    conflict_clause = ", ".join(conflict_columns)
                    
                    query = f"""
                        INSERT INTO {table_name} ({", ".join(columns)})
                        VALUES ({", ".join(placeholders)})
                        ON CONFLICT ({conflict_clause})
                        DO UPDATE SET {update_clause}
                        RETURNING *
                    """
                    
                    result = await conn.fetchrow(query, *values)
                else:
                    # Simple insert
                    columns = list(model_data.keys())
                    placeholders = [f"${i+1}" for i in range(len(columns))]
                    values = list(model_data.values())
                    
                    query = f"""
                        INSERT INTO {table_name} ({", ".join(columns)})
                        VALUES ({", ".join(placeholders)})
                        RETURNING *
                    """
                    
                    result = await conn.fetchrow(query, *values)
                
                self.stats.total_queries += 1
                query_time = time.time() - start_time
                self._update_avg_query_time(query_time)
                
                return dict(result) if result else {}
                
        except Exception as e:
            self.stats.failed_queries += 1
            logger.error(f"Failed to save Pydantic model to {table_name}: {e}")
            raise
    
    async def get_pydantic_model(self, model_class: Type[T], table_name: str, 
                                where_clause: str, params: Optional[List[Any]] = None) -> Optional[T]:
        """
        Retrieve a single Pydantic model from the database.
        
        Args:
            model_class: Pydantic model class
            table_name: Database table name
            where_clause: WHERE clause (without WHERE keyword)
            params: Query parameters
            
        Returns:
            Pydantic model instance or None
        """
        start_time = time.time()
        
        try:
            async with self.get_connection() as conn:
                query = f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT 1"
                
                if params:
                    result = await conn.fetchrow(query, *params)
                else:
                    result = await conn.fetchrow(query)
                
                self.stats.total_queries += 1
                query_time = time.time() - start_time
                self._update_avg_query_time(query_time)
                
                if result:
                    # Convert database row to dictionary and handle JSON fields
                    row_dict = dict(result)
                    
                    # Handle JSON deserialization for known JSON fields
                    json_fields = ['metadata', 'configuration', 'error_info', 'metrics', 
                                  'email_addresses', 'phone_numbers']
                    for field in json_fields:
                        if field in row_dict and row_dict[field] and isinstance(row_dict[field], str):
                            try:
                                row_dict[field] = json.loads(row_dict[field])
                            except (json.JSONDecodeError, TypeError):
                                pass  # Keep as string if not valid JSON
                    
                    return model_class.model_validate(row_dict)
                
                return None
                
        except Exception as e:
            self.stats.failed_queries += 1
            logger.error(f"Failed to get Pydantic model from {table_name}: {e}")
            raise
    
    async def get_pydantic_models(self, model_class: Type[T], table_name: str,
                                 where_clause: Optional[str] = None, params: Optional[List[Any]] = None,
                                 order_by: Optional[str] = None, limit: Optional[int] = None,
                                 offset: Optional[int] = None) -> List[T]:
        """
        Retrieve multiple Pydantic models from the database.
        
        Args:
            model_class: Pydantic model class
            table_name: Database table name
            where_clause: WHERE clause (without WHERE keyword)
            params: Query parameters
            order_by: ORDER BY clause (without ORDER BY keyword)
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of Pydantic model instances
        """
        start_time = time.time()
        
        try:
            async with self.get_connection() as conn:
                query = f"SELECT * FROM {table_name}"
                
                if where_clause:
                    query += f" WHERE {where_clause}"
                
                if order_by:
                    query += f" ORDER BY {order_by}"
                
                if limit:
                    query += f" LIMIT {limit}"
                
                if offset:
                    query += f" OFFSET {offset}"
                
                if params:
                    results = await conn.fetch(query, *params)
                else:
                    results = await conn.fetch(query)
                
                self.stats.total_queries += 1
                query_time = time.time() - start_time
                self._update_avg_query_time(query_time)
                
                models = []
                json_fields = ['metadata', 'configuration', 'error_info', 'metrics', 
                              'email_addresses', 'phone_numbers']
                
                for result in results:
                    row_dict = dict(result)
                    
                    # Handle JSON deserialization
                    for field in json_fields:
                        if field in row_dict and row_dict[field] and isinstance(row_dict[field], str):
                            try:
                                row_dict[field] = json.loads(row_dict[field])
                            except (json.JSONDecodeError, TypeError):
                                pass
                    
                    models.append(model_class.model_validate(row_dict))
                
                return models
                
        except Exception as e:
            self.stats.failed_queries += 1
            logger.error(f"Failed to get Pydantic models from {table_name}: {e}")
            raise
    
    async def update_pydantic_model(self, model: BaseModel, table_name: str,
                                   where_clause: str, params: Optional[List[Any]] = None) -> bool:
        """
        Update a Pydantic model in the database.
        
        Args:
            model: Pydantic model instance with updated data
            table_name: Database table name
            where_clause: WHERE clause (without WHERE keyword)
            params: WHERE clause parameters
            
        Returns:
            True if record was updated, False otherwise
        """
        start_time = time.time()
        
        try:
            # Convert Pydantic model to dictionary
            model_data = model.model_dump(exclude_none=True)
            
            # Handle datetime serialization
            for key, value in model_data.items():
                if isinstance(value, datetime):
                    model_data[key] = value.isoformat()
                elif isinstance(value, (dict, list)):
                    model_data[key] = json.dumps(value)
            
            # Always update the updated_at field
            model_data['updated_at'] = datetime.utcnow().isoformat()
            
            async with self.get_connection() as conn:
                # Build SET clause
                set_clauses = []
                update_values = []
                param_index = 1
                
                for key, value in model_data.items():
                    set_clauses.append(f"{key} = ${param_index}")
                    update_values.append(value)
                    param_index += 1
                
                # Add WHERE clause parameters
                if params:
                    update_values.extend(params)
                
                query = f"""
                    UPDATE {table_name}
                    SET {", ".join(set_clauses)}
                    WHERE {where_clause}
                """
                
                result = await conn.execute(query, *update_values)
                
                self.stats.total_queries += 1
                query_time = time.time() - start_time
                self._update_avg_query_time(query_time)
                
                # Check if any rows were affected
                return result.split()[-1] != '0'
                
        except Exception as e:
            self.stats.failed_queries += 1
            logger.error(f"Failed to update Pydantic model in {table_name}: {e}")
            raise
    
    async def delete_pydantic_model(self, table_name: str, where_clause: str, 
                                   params: Optional[List[Any]] = None, soft_delete: bool = True) -> bool:
        """
        Delete a Pydantic model from the database.
        
        Args:
            table_name: Database table name
            where_clause: WHERE clause (without WHERE keyword)
            params: WHERE clause parameters
            soft_delete: If True, performs soft delete by setting is_deleted=True
            
        Returns:
            True if record was deleted, False otherwise
        """
        start_time = time.time()
        
        try:
            async with self.get_connection() as conn:
                if soft_delete:
                    # Soft delete - update is_deleted and deleted_at
                    query = f"""
                        UPDATE {table_name}
                        SET is_deleted = TRUE, deleted_at = $1, updated_at = $1
                        WHERE {where_clause} AND is_deleted = FALSE
                    """
                    
                    delete_time = datetime.utcnow().isoformat()
                    query_params = [delete_time]
                    if params:
                        query_params.extend(params)
                    
                    result = await conn.execute(query, *query_params)
                else:
                    # Hard delete
                    query = f"DELETE FROM {table_name} WHERE {where_clause}"
                    
                    if params:
                        result = await conn.execute(query, *params)
                    else:
                        result = await conn.execute(query)
                
                self.stats.total_queries += 1
                query_time = time.time() - start_time
                self._update_avg_query_time(query_time)
                
                # Check if any rows were affected
                return result.split()[-1] != '0'
                
        except Exception as e:
            self.stats.failed_queries += 1
            logger.error(f"Failed to delete from {table_name}: {e}")
            raise
    
    @asynccontextmanager
    async def transaction(self):
        """
        Async context manager for database transactions.
        
        Provides ACID compliance for complex operations involving multiple queries.
        """
        async with self.get_connection() as conn:
            async with conn.transaction():
                yield conn
    
    async def bulk_save_pydantic_models(self, models: List[BaseModel], table_name: str,
                                       conflict_columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Bulk save multiple Pydantic models to the database.
        
        Args:
            models: List of Pydantic model instances
            table_name: Database table name
            conflict_columns: Columns to check for conflicts (for upsert)
            
        Returns:
            List of dictionaries with saved record data
        """
        if not models:
            return []
        
        start_time = time.time()
        results = []
        
        try:
            async with self.transaction() as conn:
                for model in models:
                    # Convert Pydantic model to dictionary
                    model_data = model.model_dump(exclude_none=True)
                    
                    # Handle datetime serialization
                    for key, value in model_data.items():
                        if isinstance(value, datetime):
                            model_data[key] = value.isoformat()
                        elif isinstance(value, (dict, list)):
                            model_data[key] = json.dumps(value)
                    
                    if conflict_columns:
                        # Upsert operation
                        columns = list(model_data.keys())
                        placeholders = [f"${i+1}" for i in range(len(columns))]
                        values = list(model_data.values())
                        
                        # Build conflict resolution
                        update_columns = [col for col in columns if col not in conflict_columns]
                        update_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
                        conflict_clause = ", ".join(conflict_columns)
                        
                        query = f"""
                            INSERT INTO {table_name} ({", ".join(columns)})
                            VALUES ({", ".join(placeholders)})
                            ON CONFLICT ({conflict_clause})
                            DO UPDATE SET {update_clause}
                            RETURNING *
                        """
                        
                        result = await conn.fetchrow(query, *values)
                    else:
                        # Simple insert
                        columns = list(model_data.keys())
                        placeholders = [f"${i+1}" for i in range(len(columns))]
                        values = list(model_data.values())
                        
                        query = f"""
                            INSERT INTO {table_name} ({", ".join(columns)})
                            VALUES ({", ".join(placeholders)})
                            RETURNING *
                        """
                        
                        result = await conn.fetchrow(query, *values)
                    
                    results.append(dict(result) if result else {})
                
                self.stats.total_queries += len(models)
                query_time = time.time() - start_time
                self._update_avg_query_time(query_time / len(models))
                
                return results
                
        except Exception as e:
            self.stats.failed_queries += len(models)
            logger.error(f"Failed to bulk save Pydantic models to {table_name}: {e}")
            raise
    
    def _update_avg_query_time(self, query_time: float):
        """Update average query time statistics."""
        if self.stats.total_queries == 1:
            self.stats.avg_query_time = query_time
        else:
            # Calculate running average
            total_time = self.stats.avg_query_time * (self.stats.total_queries - 1)
            self.stats.avg_query_time = (total_time + query_time) / self.stats.total_queries
    
    async def health_check(self) -> bool:
        """Perform database health check."""
        try:
            start_time = time.time()
            
            # Test asyncpg connection
            async with self.get_connection() as conn:
                await conn.fetchval("SELECT 1")
            
            # Test SQLAlchemy connection
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar()
                # Explicitly commit to ensure session is clean
                await session.commit()
            
            check_time = time.time() - start_time
            self._is_healthy = True
            self.stats.last_health_check = datetime.utcnow()
            self.stats.health_status = "healthy"
            
            logger.debug(f"Health check passed in {check_time:.3f}s")
            return True
            
        except Exception as e:
            self._is_healthy = False
            self.stats.health_status = f"unhealthy: {str(e)}"
            logger.error(f"Health check failed: {e}")
            return False
    
    async def _health_check_loop(self):
        """Background task for periodic health checks."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self.health_check()
                
            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
    
    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        pool_stats = {}
        
        if self.pool:
            pool_stats.update({
                "asyncpg_pool": {
                    "size": self.pool.get_size(),
                    "min_size": self.pool.get_min_size(),
                    "max_size": self.pool.get_max_size(),
                    "idle_connections": self.pool.get_idle_size(),
                }
            })
        
        if self.engine:
            pool = self.engine.pool
            pool_stats.update({
                "sqlalchemy_pool": {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalid": pool.invalid(),
                }
            })
        
        pool_stats.update({
            "stats": self.stats.model_dump(),
            "is_healthy": self._is_healthy,
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "database": self.config.database,
                "min_connections": self.config.min_connections,
                "max_connections": self.config.max_connections,
            }
        })
        
        return pool_stats
    
    async def close(self):
        """Close all connections and cleanup resources."""
        logger.info("Closing database connections...")
        
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Close SQLAlchemy engine first (it depends on the connection pool)
        if self.engine:
            try:
                # Dispose of all connections in the pool
                await self.engine.dispose()
                logger.info("SQLAlchemy engine disposed")
            except Exception as e:
                logger.warning(f"Error disposing SQLAlchemy engine: {e}")
            finally:
                self.engine = None
                self.async_session_factory = None
        
        # Close asyncpg pool
        if self.pool:
            try:
                # Gracefully close all connections
                await self.pool.close()
                logger.info("AsyncPG connection pool closed")
            except Exception as e:
                logger.warning(f"Error closing AsyncPG pool: {e}")
            finally:
                self.pool = None
        
        # Reset health status
        self._is_healthy = False
        self.stats.health_status = "closed"
        
        logger.info("Database connections closed successfully")
    
    @property
    def is_healthy(self) -> bool:
        """Check if the connection manager is healthy."""
        return self._is_healthy
    
    @property
    def is_initialized(self) -> bool:
        """Check if the connection manager is initialized."""
        return self.pool is not None and self.engine is not None


# Global connection manager instance
_connection_manager: Optional[RDSConnectionManager] = None


async def initialize_database(config: Optional[ConnectionConfig] = None) -> RDSConnectionManager:
    """Initialize global database connection manager."""
    global _connection_manager
    
    if not config:
        settings = get_settings()
        config = ConnectionConfig(
            host=settings.rds_endpoint.split(':')[0] if ':' in settings.rds_endpoint else settings.rds_endpoint,
            port=int(settings.rds_endpoint.split(':')[1]) if ':' in settings.rds_endpoint else 5432,
            database=settings.rds_database,
            username=settings.rds_username,
            password=settings.rds_password
        )
    
    _connection_manager = RDSConnectionManager(config)
    
    if await _connection_manager.initialize():
        logger.info("Global database connection manager initialized")
        return _connection_manager
    else:
        raise RuntimeError("Failed to initialize database connection manager")


def get_connection_manager() -> RDSConnectionManager:
    """Get the global connection manager instance."""
    if _connection_manager is None:
        raise RuntimeError("Database connection manager not initialized. Call initialize_database() first.")
    return _connection_manager


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency function to get database session for FastAPI."""
    manager = get_connection_manager()
    async with manager.get_session() as session:
        yield session


async def get_db_connection() -> AsyncGenerator[Connection, None]:
    """Dependency function to get asyncpg connection for FastAPI."""
    manager = get_connection_manager()
    async with manager.get_connection() as connection:
        yield connection


async def close_database():
    """Close global database connection manager."""
    global _connection_manager
    
    if _connection_manager:
        try:
            await _connection_manager.close()
            logger.info("Global database connection manager closed")
        except Exception as e:
            logger.error(f"Error closing database connection manager: {e}")
        finally:
            _connection_manager = None


# Utility functions for database operations

async def execute_with_retry(operation, *args, max_retries: int = 3, **kwargs):
    """Execute database operation with retry logic."""
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            return await operation(*args, **kwargs)
        except (DisconnectionError, OperationalError, asyncpg.PostgresError) as e:
            if retry_count >= max_retries:
                logger.error(f"Operation failed after {retry_count} retries: {e}")
                raise
            
            retry_count += 1
            delay = 1.0 * (2.0 ** (retry_count - 1))  # Exponential backoff
            logger.warning(f"Operation failed, retrying in {delay}s (attempt {retry_count}): {e}")
            await asyncio.sleep(delay)


async def test_database_connectivity(config: Optional[ConnectionConfig] = None) -> Dict[str, Any]:
    """Test database connectivity and return status information."""
    if not config:
        settings = get_settings()
        config = ConnectionConfig(
            host=settings.rds_endpoint.split(':')[0] if ':' in settings.rds_endpoint else settings.rds_endpoint,
            port=int(settings.rds_endpoint.split(':')[1]) if ':' in settings.rds_endpoint else 5432,
            database=settings.rds_database,
            username=settings.rds_username,
            password=settings.rds_password
        )
    
    result = {
        "connected": False,
        "error": None,
        "server_version": None,
        "database_size": None,
        "connection_time": None
    }
    
    start_time = time.time()
    
    try:
        # Test basic connectivity
        conn = await asyncpg.connect(
            dsn=config.asyncpg_dsn,
            timeout=config.connection_timeout
        )
        
        try:
            # Get server version
            result["server_version"] = await conn.fetchval("SELECT version()")
            
            # Get database size
            result["database_size"] = await conn.fetchval(
                "SELECT pg_size_pretty(pg_database_size($1))", config.database
            )
            
            result["connected"] = True
            result["connection_time"] = time.time() - start_time
            
        finally:
            await conn.close()
            
    except Exception as e:
        result["error"] = str(e)
        result["connection_time"] = time.time() - start_time
    
    return result


# Additional utility functions for Pydantic model operations

async def count_records(manager: RDSConnectionManager, table_name: str, 
                       where_clause: Optional[str] = None, params: Optional[List[Any]] = None) -> int:
    """
    Count records in a table with optional WHERE clause.
    
    Args:
        manager: RDSConnectionManager instance
        table_name: Database table name
        where_clause: WHERE clause (without WHERE keyword)
        params: Query parameters
        
    Returns:
        Number of records
    """
    query = f"SELECT COUNT(*) FROM {table_name}"
    
    if where_clause:
        query += f" WHERE {where_clause}"
    
    if params:
        result = await manager.execute_query(query, {"params": params})
    else:
        result = await manager.execute_query(query)
    
    return result[0]['count'] if result else 0


async def table_exists(manager: RDSConnectionManager, table_name: str) -> bool:
    """
    Check if a table exists in the database.
    
    Args:
        manager: RDSConnectionManager instance
        table_name: Table name to check
        
    Returns:
        True if table exists, False otherwise
    """
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = $1
        )
    """
    
    try:
        async with manager.get_connection() as conn:
            result = await conn.fetchval(query, table_name)
            return bool(result)
    except Exception as e:
        logger.error(f"Failed to check if table {table_name} exists: {e}")
        return False


async def get_table_schema(manager: RDSConnectionManager, table_name: str) -> List[Dict[str, Any]]:
    """
    Get table schema information.
    
    Args:
        manager: RDSConnectionManager instance
        table_name: Table name
        
    Returns:
        List of column information dictionaries
    """
    query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
    """
    
    try:
        async with manager.get_connection() as conn:
            results = await conn.fetch(query, table_name)
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Failed to get schema for table {table_name}: {e}")
        return []


class PydanticModelRepository:
    """
    Generic repository class for Pydantic model database operations.
    
    This class provides a high-level interface for common database operations
    with Pydantic models, including CRUD operations and query building.
    """
    
    def __init__(self, manager: RDSConnectionManager, model_class: Type[T], table_name: str):
        self.manager = manager
        self.model_class = model_class
        self.table_name = table_name
    
    async def create(self, model: T, conflict_columns: Optional[List[str]] = None) -> T:
        """Create a new record from Pydantic model."""
        result = await self.manager.save_pydantic_model(model, self.table_name, conflict_columns)
        return self.model_class.model_validate(result)
    
    async def get_by_id(self, record_id: str) -> Optional[T]:
        """Get record by ID."""
        return await self.manager.get_pydantic_model(
            self.model_class, self.table_name, "id = $1", [record_id]
        )
    
    async def get_by_field(self, field_name: str, field_value: Any) -> Optional[T]:
        """Get record by specific field."""
        return await self.manager.get_pydantic_model(
            self.model_class, self.table_name, f"{field_name} = $1", [field_value]
        )
    
    async def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None,
                     order_by: Optional[str] = None) -> List[T]:
        """Get all records with optional pagination and ordering."""
        return await self.manager.get_pydantic_models(
            self.model_class, self.table_name, 
            order_by=order_by, limit=limit, offset=offset
        )
    
    async def get_where(self, where_clause: str, params: Optional[List[Any]] = None,
                       limit: Optional[int] = None, offset: Optional[int] = None,
                       order_by: Optional[str] = None) -> List[T]:
        """Get records matching WHERE clause."""
        return await self.manager.get_pydantic_models(
            self.model_class, self.table_name, where_clause, params,
            order_by, limit, offset
        )
    
    async def update(self, model: T, where_clause: str, params: Optional[List[Any]] = None) -> bool:
        """Update record with Pydantic model data."""
        return await self.manager.update_pydantic_model(model, self.table_name, where_clause, params)
    
    async def update_by_id(self, record_id: str, model: T) -> bool:
        """Update record by ID."""
        return await self.update(model, "id = $1", [record_id])
    
    async def delete(self, where_clause: str, params: Optional[List[Any]] = None, 
                    soft_delete: bool = True) -> bool:
        """Delete record(s) matching WHERE clause."""
        return await self.manager.delete_pydantic_model(
            self.table_name, where_clause, params, soft_delete
        )
    
    async def delete_by_id(self, record_id: str, soft_delete: bool = True) -> bool:
        """Delete record by ID."""
        return await self.delete("id = $1", [record_id], soft_delete)
    
    async def count(self, where_clause: Optional[str] = None, params: Optional[List[Any]] = None) -> int:
        """Count records matching optional WHERE clause."""
        return await count_records(self.manager, self.table_name, where_clause, params)
    
    async def exists(self, where_clause: str, params: Optional[List[Any]] = None) -> bool:
        """Check if record exists matching WHERE clause."""
        count = await self.count(where_clause, params)
        return count > 0
    
    async def bulk_create(self, models: List[T], conflict_columns: Optional[List[str]] = None) -> List[T]:
        """Bulk create multiple records."""
        results = await self.manager.bulk_save_pydantic_models(models, self.table_name, conflict_columns)
        return [self.model_class.model_validate(result) for result in results]