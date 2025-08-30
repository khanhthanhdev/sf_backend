"""
AWS RDS-integrated User Service.

This service migrates user management from Redis to AWS RDS PostgreSQL,
providing user data management, session handling, and activity logging
using Pydantic models and async database operations.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
from uuid import UUID, uuid4

from ..database.connection import RDSConnectionManager
from ..database.pydantic_models import UserDB, UserQueries
from ..models.user import (
    ClerkUser, 
    UserProfile, 
    UserSession, 
    UserPermissions, 
    UserRole,
    UserStatus,
    AuthenticationContext
)
from ..core.auth import clerk_manager, ClerkAuthError

logger = logging.getLogger(__name__)


class AWSUserService:
    """
    AWS RDS-integrated user service for Clerk authentication.
    
    Provides user data management, session handling, and activity logging
    using PostgreSQL database storage with Pydantic model integration.
    """
    
    def __init__(self, db_manager: RDSConnectionManager, redis_client=None):
        """
        Initialize AWS User Service.
        
        Args:
            db_manager: RDS connection manager
            redis_client: Optional Redis client for caching
        """
        self.db_manager = db_manager
        self.redis_client = redis_client
        self._initialized = False
        
        logger.info("Initialized AWS User Service with RDS integration")
    
    async def initialize(self) -> bool:
        """
        Initialize the user service.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Test database connectivity
            health_check = await self.db_manager.health_check()
            if not health_check:
                raise ConnectionError("Database health check failed")
            
            self._initialized = True
            logger.info("AWS User Service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize AWS User Service: {e}")
            return False
    
    async def extract_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Extract comprehensive user data from Clerk and store in RDS.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            Dict containing user data
            
        Raises:
            ClerkAuthError: If user data extraction fails
        """
        try:
            # Get user info from Clerk
            user_info = await clerk_manager.get_user_info(user_id)
            
            # Create ClerkUser model from Clerk data
            clerk_user = ClerkUser(**user_info)
            
            # Convert to database model
            user_db = UserDB.from_clerk_user(clerk_user)
            
            # Save to database with upsert
            await self.db_manager.save_pydantic_model(
                user_db, 
                'users', 
                conflict_columns=['clerk_user_id']
            )
            
            # Log user data extraction activity
            await self.log_user_activity(
                user_id,
                'user_data_extracted',
                {'source': 'clerk', 'timestamp': datetime.utcnow().isoformat()}
            )
            
            logger.info(f"User data extracted and stored for user {user_id}")
            return user_info
            
        except Exception as e:
            logger.error(f"Failed to extract user data for {user_id}: {e}")
            raise ClerkAuthError(f"User data extraction failed: {e}")
    
    async def get_user_by_clerk_id(self, clerk_user_id: str) -> Optional[UserDB]:
        """
        Get user by Clerk user ID from database.
        
        Args:
            clerk_user_id: Clerk user ID
            
        Returns:
            UserDB instance or None if not found
        """
        try:
            user = await self.db_manager.get_pydantic_model(
                UserDB,
                'users',
                'clerk_user_id = $1 AND is_deleted = FALSE',
                [clerk_user_id]
            )
            
            if user:
                # Update last_active_at
                await self._update_user_activity(user.id)
            
            return user
            
        except Exception as e:
            logger.error(f"Failed to get user by Clerk ID {clerk_user_id}: {e}")
            return None
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[UserDB]:
        """
        Get user by internal user ID from database.
        
        Args:
            user_id: Internal user ID
            
        Returns:
            UserDB instance or None if not found
        """
        try:
            user = await self.db_manager.get_pydantic_model(
                UserDB,
                'users',
                'id = $1 AND is_deleted = FALSE',
                [user_id]
            )
            
            if user:
                # Update last_active_at
                await self._update_user_activity(user_id)
            
            return user
            
        except Exception as e:
            logger.error(f"Failed to get user by ID {user_id}: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[UserDB]:
        """
        Get user by primary email from database.
        
        Args:
            email: Primary email address
            
        Returns:
            UserDB instance or None if not found
        """
        try:
            user = await self.db_manager.get_pydantic_model(
                UserDB,
                'users',
                'primary_email = $1 AND is_deleted = FALSE',
                [email]
            )
            
            if user:
                # Update last_active_at
                await self._update_user_activity(user.id)
            
            return user
            
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            return None
    
    async def create_or_update_user(self, clerk_user: ClerkUser) -> UserDB:
        """
        Create or update user in database from Clerk user data.
        
        Args:
            clerk_user: ClerkUser instance
            
        Returns:
            UserDB instance
        """
        try:
            # Convert to database model
            user_db = UserDB.from_clerk_user(clerk_user)
            
            # Save to database with upsert
            saved_data = await self.db_manager.save_pydantic_model(
                user_db,
                'users',
                conflict_columns=['clerk_user_id']
            )
            
            # Return updated user model
            return UserDB.model_validate(saved_data)
            
        except Exception as e:
            logger.error(f"Failed to create/update user {clerk_user.id}: {e}")
            raise
    
    async def create_user_session(
        self, 
        user_id: str, 
        session_id: Optional[str] = None,
        token_claims: Optional[Dict[str, Any]] = None
    ) -> UserSession:
        """
        Create and store user session information in database.
        
        Args:
            user_id: Clerk user ID
            session_id: Session ID from Clerk
            token_claims: JWT token claims
            
        Returns:
            UserSession instance
        """
        try:
            # Get user from database
            user = await self.get_user_by_clerk_id(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Create session object
            session = UserSession(
                user_id=user_id,
                session_id=session_id,
                token_claims=token_claims or {},
                verified_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24)  # 24 hour session
            )
            
            # Store session in database
            session_data = {
                'id': uuid4(),
                'user_id': user.id,
                'clerk_user_id': user_id,
                'session_id': session_id,
                'token_claims': session.token_claims,
                'verified_at': session.verified_at,
                'expires_at': session.expires_at,
                'is_active': True,
                'created_at': datetime.utcnow()
            }
            
            await self.db_manager.execute_command(
                """
                INSERT INTO user_sessions (id, user_id, clerk_user_id, session_id, token_claims, 
                                         verified_at, expires_at, is_active, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (clerk_user_id) 
                DO UPDATE SET 
                    session_id = EXCLUDED.session_id,
                    token_claims = EXCLUDED.token_claims,
                    verified_at = EXCLUDED.verified_at,
                    expires_at = EXCLUDED.expires_at,
                    is_active = EXCLUDED.is_active,
                    updated_at = CURRENT_TIMESTAMP
                """,
                {
                    'id': session_data['id'],
                    'user_id': session_data['user_id'],
                    'clerk_user_id': session_data['clerk_user_id'],
                    'session_id': session_data['session_id'],
                    'token_claims': json.dumps(session_data['token_claims']),
                    'verified_at': session_data['verified_at'],
                    'expires_at': session_data['expires_at'],
                    'is_active': session_data['is_active'],
                    'created_at': session_data['created_at']
                }
            )
            
            # Log session creation
            await self.log_user_activity(
                user_id,
                'session_created',
                {'session_id': session_id, 'expires_at': session.expires_at.isoformat()}
            )
            
            logger.info(f"User session created for user {user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create user session for {user_id}: {e}")
            raise ClerkAuthError(f"Session creation failed: {e}")
    
    async def get_user_session(self, user_id: str) -> Optional[UserSession]:
        """
        Get user session from database.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            UserSession instance or None if not found/expired
        """
        try:
            session_data = await self.db_manager.execute_query(
                """
                SELECT * FROM user_sessions 
                WHERE clerk_user_id = $1 AND is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
                """,
                {'clerk_user_id': user_id}
            )
            
            if not session_data:
                return None
            
            session_record = session_data[0]
            
            # Parse token claims
            token_claims = {}
            if session_record.get('token_claims'):
                try:
                    token_claims = json.loads(session_record['token_claims'])
                except json.JSONDecodeError:
                    pass
            
            session = UserSession(
                user_id=session_record['clerk_user_id'],
                session_id=session_record['session_id'],
                token_claims=token_claims,
                verified_at=session_record['verified_at'],
                expires_at=session_record['expires_at']
            )
            
            # Check if session is expired
            if session.is_expired:
                await self.invalidate_user_session(user_id)
                return None
            
            return session
            
        except Exception as e:
            logger.warning(f"Failed to get user session for {user_id}: {e}")
            return None
    
    async def invalidate_user_session(self, user_id: str) -> bool:
        """
        Invalidate user session in database.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            True if session was invalidated
        """
        try:
            result = await self.db_manager.execute_command(
                """
                UPDATE user_sessions 
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE clerk_user_id = $1 AND is_active = TRUE
                """,
                {'clerk_user_id': user_id}
            )
            
            # Log session invalidation
            await self.log_user_activity(
                user_id,
                'session_invalidated',
                {'timestamp': datetime.utcnow().isoformat()}
            )
            
            logger.info(f"User session invalidated for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate session for {user_id}: {e}")
            return False
    
    async def get_user_permissions(self, user_id: str) -> UserPermissions:
        """
        Get user permissions from database with role-based defaults.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            UserPermissions instance
        """
        try:
            # Get user from database
            user = await self.get_user_by_clerk_id(user_id)
            if not user:
                # Return default permissions for unknown user
                return UserPermissions.from_user_role(user_id, UserRole.USER)
            
            # Check for cached permissions
            cached_permissions = await self._get_cached_permissions(user.id)
            if cached_permissions:
                return cached_permissions
            
            # Create permissions based on user role
            permissions = UserPermissions.from_user_role(user_id, user.role)
            
            # Store permissions in database
            permissions_data = {
                'id': uuid4(),
                'user_id': user.id,
                'clerk_user_id': user_id,
                'role': user.role.value,
                'permissions': permissions.permissions,
                'can_generate_videos': permissions.can_generate_videos,
                'can_upload_files': permissions.can_upload_files,
                'can_access_premium_features': permissions.can_access_premium_features,
                'can_view_all_jobs': permissions.can_view_all_jobs,
                'can_cancel_any_job': permissions.can_cancel_any_job,
                'can_access_system_metrics': permissions.can_access_system_metrics,
                'max_concurrent_jobs': permissions.max_concurrent_jobs,
                'max_daily_jobs': permissions.max_daily_jobs,
                'max_file_size_mb': permissions.max_file_size_mb,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            await self.db_manager.execute_command(
                """
                INSERT INTO user_permissions (id, user_id, clerk_user_id, role, permissions,
                                            can_generate_videos, can_upload_files, can_access_premium_features,
                                            can_view_all_jobs, can_cancel_any_job, can_access_system_metrics,
                                            max_concurrent_jobs, max_daily_jobs, max_file_size_mb,
                                            created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                ON CONFLICT (clerk_user_id)
                DO UPDATE SET
                    role = EXCLUDED.role,
                    permissions = EXCLUDED.permissions,
                    can_generate_videos = EXCLUDED.can_generate_videos,
                    can_upload_files = EXCLUDED.can_upload_files,
                    can_access_premium_features = EXCLUDED.can_access_premium_features,
                    can_view_all_jobs = EXCLUDED.can_view_all_jobs,
                    can_cancel_any_job = EXCLUDED.can_cancel_any_job,
                    can_access_system_metrics = EXCLUDED.can_access_system_metrics,
                    max_concurrent_jobs = EXCLUDED.max_concurrent_jobs,
                    max_daily_jobs = EXCLUDED.max_daily_jobs,
                    max_file_size_mb = EXCLUDED.max_file_size_mb,
                    updated_at = EXCLUDED.updated_at
                """,
                {
                    'id': permissions_data['id'],
                    'user_id': permissions_data['user_id'],
                    'clerk_user_id': permissions_data['clerk_user_id'],
                    'role': permissions_data['role'],
                    'permissions': json.dumps(permissions_data['permissions']),
                    'can_generate_videos': permissions_data['can_generate_videos'],
                    'can_upload_files': permissions_data['can_upload_files'],
                    'can_access_premium_features': permissions_data['can_access_premium_features'],
                    'can_view_all_jobs': permissions_data['can_view_all_jobs'],
                    'can_cancel_any_job': permissions_data['can_cancel_any_job'],
                    'can_access_system_metrics': permissions_data['can_access_system_metrics'],
                    'max_concurrent_jobs': permissions_data['max_concurrent_jobs'],
                    'max_daily_jobs': permissions_data['max_daily_jobs'],
                    'max_file_size_mb': permissions_data['max_file_size_mb'],
                    'created_at': permissions_data['created_at'],
                    'updated_at': permissions_data['updated_at']
                }
            )
            
            logger.info(f"User permissions determined for {user_id}: {user.role}")
            return permissions
            
        except Exception as e:
            logger.error(f"Failed to get user permissions for {user_id}: {e}")
            # Return default permissions on error
            return UserPermissions.from_user_role(user_id, UserRole.USER)
    
    async def _get_cached_permissions(self, user_id: UUID) -> Optional[UserPermissions]:
        """Get cached permissions from database."""
        try:
            permissions_data = await self.db_manager.execute_query(
                """
                SELECT * FROM user_permissions 
                WHERE user_id = $1 
                AND updated_at > $2
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                {
                    'user_id': user_id,
                    'cache_threshold': datetime.utcnow() - timedelta(hours=1)  # 1 hour cache
                }
            )
            
            if not permissions_data:
                return None
            
            perm_record = permissions_data[0]
            
            # Parse permissions list
            permissions_list = []
            if perm_record.get('permissions'):
                try:
                    permissions_list = json.loads(perm_record['permissions'])
                except json.JSONDecodeError:
                    pass
            
            return UserPermissions(
                user_id=perm_record['clerk_user_id'],
                role=UserRole(perm_record['role']),
                permissions=permissions_list,
                can_generate_videos=perm_record['can_generate_videos'],
                can_upload_files=perm_record['can_upload_files'],
                can_access_premium_features=perm_record['can_access_premium_features'],
                can_view_all_jobs=perm_record['can_view_all_jobs'],
                can_cancel_any_job=perm_record['can_cancel_any_job'],
                can_access_system_metrics=perm_record['can_access_system_metrics'],
                max_concurrent_jobs=perm_record['max_concurrent_jobs'],
                max_daily_jobs=perm_record['max_daily_jobs'],
                max_file_size_mb=perm_record['max_file_size_mb']
            )
            
        except Exception as e:
            logger.warning(f"Failed to get cached permissions: {e}")
            return None
    
    async def check_user_permission(self, user_id: str, permission: str) -> bool:
        """
        Check if user has specific permission.
        
        Args:
            user_id: Clerk user ID
            permission: Permission string to check
            
        Returns:
            True if user has permission
        """
        try:
            permissions = await self.get_user_permissions(user_id)
            return permissions.has_permission(permission)
            
        except Exception as e:
            logger.error(f"Permission check failed for {user_id}: {e}")
            return False
    
    async def create_authentication_context(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        token_claims: Optional[Dict[str, Any]] = None
    ) -> AuthenticationContext:
        """
        Create complete authentication context for user.
        
        Args:
            user_id: Clerk user ID
            session_id: Session ID from Clerk
            token_claims: JWT token claims
            
        Returns:
            AuthenticationContext instance
        """
        try:
            # Get or create user in database
            user = await self.get_user_by_clerk_id(user_id)
            if not user:
                # Extract user data from Clerk and create in database
                await self.extract_user_data(user_id)
                user = await self.get_user_by_clerk_id(user_id)
                
                if not user:
                    raise ValueError(f"Failed to create user {user_id}")
            
            # Create user profile
            user_profile = user.to_user_profile()
            
            # Create or get session
            session = await self.create_user_session(user_id, session_id, token_claims)
            
            # Get permissions
            permissions = await self.get_user_permissions(user_id)
            
            # Create authentication context
            auth_context = AuthenticationContext(
                user=user_profile,
                session=session,
                permissions=permissions
            )
            
            # Log authentication context creation
            await self.log_user_activity(
                user_id,
                'auth_context_created',
                {'session_id': session_id, 'timestamp': datetime.utcnow().isoformat()}
            )
            
            logger.info(f"Authentication context created for user {user_id}")
            return auth_context
            
        except Exception as e:
            logger.error(f"Failed to create auth context for {user_id}: {e}")
            raise ClerkAuthError(f"Authentication context creation failed: {e}")
    
    async def log_user_activity(
        self,
        user_id: str,
        activity_type: str,
        details: Dict[str, Any]
    ) -> bool:
        """
        Log user activity to database.
        
        Args:
            user_id: Clerk user ID
            activity_type: Type of activity
            details: Activity details
            
        Returns:
            True if activity was logged
        """
        try:
            # Get user from database
            user = await self.get_user_by_clerk_id(user_id)
            if not user:
                logger.warning(f"Cannot log activity for unknown user {user_id}")
                return False
            
            activity_record = {
                'id': uuid4(),
                'user_id': user.id,
                'clerk_user_id': user_id,
                'activity_type': activity_type,
                'details': details,
                'timestamp': datetime.utcnow(),
                'ip_address': details.get('ip_address'),
                'user_agent': details.get('user_agent')
            }
            
            await self.db_manager.execute_command(
                """
                INSERT INTO user_activity_log (id, user_id, clerk_user_id, activity_type, 
                                             details, timestamp, ip_address, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                {
                    'id': activity_record['id'],
                    'user_id': activity_record['user_id'],
                    'clerk_user_id': activity_record['clerk_user_id'],
                    'activity_type': activity_record['activity_type'],
                    'details': json.dumps(activity_record['details']),
                    'timestamp': activity_record['timestamp'],
                    'ip_address': activity_record['ip_address'],
                    'user_agent': activity_record['user_agent']
                }
            )
            
            logger.debug(f"Activity logged for user {user_id}: {activity_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log activity for {user_id}: {e}")
            return False
    
    async def get_user_activity_log(
        self, 
        user_id: str, 
        limit: int = 50,
        activity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get user activity log from database.
        
        Args:
            user_id: Clerk user ID
            limit: Maximum number of activities to return
            activity_type: Filter by activity type
            
        Returns:
            List of activity records
        """
        try:
            # Get user from database
            user = await self.get_user_by_clerk_id(user_id)
            if not user:
                return []
            
            where_clause = "user_id = $1"
            params = [user.id]
            
            if activity_type:
                where_clause += " AND activity_type = $2"
                params.append(activity_type)
            
            activities = await self.db_manager.execute_query(
                f"""
                SELECT * FROM user_activity_log 
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT {limit}
                """,
                dict(zip([f'param_{i}' for i in range(len(params))], params))
            )
            
            # Parse activity details
            parsed_activities = []
            for activity in activities:
                activity_dict = dict(activity)
                
                # Parse JSON details
                if activity_dict.get('details'):
                    try:
                        activity_dict['details'] = json.loads(activity_dict['details'])
                    except json.JSONDecodeError:
                        pass
                
                parsed_activities.append(activity_dict)
            
            return parsed_activities
            
        except Exception as e:
            logger.error(f"Failed to get activity log for {user_id}: {e}")
            return []
    
    async def _update_user_activity(self, user_id: UUID) -> bool:
        """Update user's last_active_at timestamp."""
        try:
            await self.db_manager.execute_command(
                """
                UPDATE users 
                SET last_active_at = $1, updated_at = $1
                WHERE id = $2
                """,
                {'timestamp': datetime.utcnow(), 'user_id': user_id}
            )
            return True
            
        except Exception as e:
            logger.warning(f"Failed to update user activity timestamp: {e}")
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired user sessions from database.
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            result = await self.db_manager.execute_command(
                """
                UPDATE user_sessions 
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE expires_at < $1 AND is_active = TRUE
                """,
                {'current_time': datetime.utcnow()}
            )
            
            # Extract number of affected rows from result
            cleaned_count = int(result.split()[-1]) if result else 0
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired sessions")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check for the user service.
        
        Returns:
            Dict containing health status information
        """
        health_status = {
            'service': 'AWSUserService',
            'status': 'healthy',
            'initialized': self._initialized,
            'database': 'unknown',
            'redis': 'not_configured',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            # Check database connectivity
            db_healthy = await self.db_manager.health_check()
            health_status['database'] = 'healthy' if db_healthy else 'unhealthy'
            
            if not db_healthy:
                health_status['status'] = 'unhealthy'
            
            # Check Redis connectivity if configured
            if self.redis_client:
                try:
                    await self.redis_client.ping()
                    health_status['redis'] = 'healthy'
                except Exception:
                    health_status['redis'] = 'unhealthy'
            
            # Test basic database operations
            try:
                await self.db_manager.execute_query("SELECT 1")
                health_status['database_operations'] = 'healthy'
            except Exception as e:
                health_status['database_operations'] = 'unhealthy'
                health_status['database_error'] = str(e)
                health_status['status'] = 'unhealthy'
            
        except Exception as e:
            health_status['status'] = 'error'
            health_status['error'] = str(e)
        
        return health_status
    
    # User-File Relationship Management
    
    async def get_user_files(
        self, 
        user_id: str, 
        file_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get files associated with a user.
        
        Args:
            user_id: Clerk user ID
            file_type: Optional file type filter
            limit: Maximum number of files to return
            offset: Number of files to skip
            
        Returns:
            List of file metadata records
        """
        try:
            # Get user from database
            user = await self.get_user_by_clerk_id(user_id)
            if not user:
                return []
            
            where_clause = "user_id = $1 AND is_deleted = FALSE"
            params = [user.id]
            
            if file_type:
                where_clause += " AND file_type = $2"
                params.append(file_type)
            
            files = await self.db_manager.execute_query(
                f"""
                SELECT fm.*, 
                       j.status as job_status,
                       j.created_at as job_created_at
                FROM file_metadata fm
                LEFT JOIN jobs j ON fm.job_id = j.id
                WHERE {where_clause}
                ORDER BY fm.created_at DESC
                LIMIT {limit} OFFSET {offset}
                """,
                dict(zip([f'param_{i}' for i in range(len(params))], params))
            )
            
            # Parse file metadata
            parsed_files = []
            for file_record in files:
                file_dict = dict(file_record)
                
                # Parse JSON fields
                if file_dict.get('file_metadata'):
                    try:
                        file_dict['file_metadata'] = json.loads(file_dict['file_metadata'])
                    except json.JSONDecodeError:
                        pass  # Keep as string if not valid JSON
                
                parsed_files.append(file_dict)
            
            return parsed_files
            
        except Exception as e:
            logger.error(f"Failed to get user files for {user_id}: {e}")
            return []
    