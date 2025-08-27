"""
Tests for user management utilities.

This module contains unit tests for the user management utilities
including user data extraction, session management, and permission checking.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.app.utils.user_utils import (
    UserDataExtractor,
    UserSessionManager,
    UserPermissionChecker,
    extract_user_from_token,
    create_auth_context,
    validate_user_permission,
    SessionCache
)
from src.app.core.auth import ClerkManager, ClerkAuthError
from src.app.models.user import ClerkUser, UserRole, UserStatus, UserPermissions


@pytest.fixture
def mock_clerk_manager():
    """Create mock Clerk manager for testing."""
    manager = Mock(spec=ClerkManager)
    manager.get_user_info = AsyncMock()
    manager.verify_session_token = AsyncMock()
    return manager


@pytest.fixture
def sample_user_info():
    """Sample user info from Clerk API."""
    return {
        "id": "user_123",
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "image_url": "https://example.com/avatar.jpg",
        "email_verified": True,
        "created_at": datetime.utcnow() - timedelta(days=30),
        "updated_at": datetime.utcnow(),
        "last_sign_in_at": datetime.utcnow() - timedelta(hours=1)
    }


@pytest.fixture
def sample_token_info():
    """Sample token info from Clerk verification."""
    return {
        "user_id": "user_123",
        "session_id": "sess_456",
        "claims": {
            "sub": "user_123",
            "sid": "sess_456",
            "exp": (datetime.utcnow() + timedelta(hours=24)).timestamp()
        },
        "verified_at": datetime.utcnow().isoformat()
    }


class TestUserDataExtractor:
    """Test cases for UserDataExtractor."""
    
    @pytest.mark.asyncio
    async def test_extract_user_from_clerk_success(self, mock_clerk_manager, sample_user_info):
        """Test successful user data extraction."""
        mock_clerk_manager.get_user_info.return_value = sample_user_info
        
        extractor = UserDataExtractor(mock_clerk_manager)
        result = await extractor.extract_user_from_clerk("user_123")
        
        assert isinstance(result, ClerkUser)
        assert result.id == "user_123"
        assert result.username == "testuser"
        assert result.first_name == "Test"
        assert result.last_name == "User"
        assert result.email_verified is True
        
        mock_clerk_manager.get_user_info.assert_called_once_with("user_123")
    
    @pytest.mark.asyncio
    async def test_extract_user_from_clerk_failure(self, mock_clerk_manager):
        """Test user data extraction failure."""
        mock_clerk_manager.get_user_info.side_effect = Exception("API Error")
        
        extractor = UserDataExtractor(mock_clerk_manager)
        
        with pytest.raises(ClerkAuthError, match="User data extraction failed"):
            await extractor.extract_user_from_clerk("user_123")
    
    def test_create_user_profile(self, mock_clerk_manager):
        """Test user profile creation."""
        clerk_user = ClerkUser(
            id="user_123",
            username="testuser",
            first_name="Test",
            last_name="User",
            email_verified=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        extractor = UserDataExtractor(mock_clerk_manager)
        profile = extractor.create_user_profile(clerk_user)
        
        assert profile.id == "user_123"
        assert profile.username == "testuser"
        assert profile.full_name == "Test User"
        assert profile.email_verified is True
    
    def test_extract_user_metadata(self, mock_clerk_manager):
        """Test user metadata extraction."""
        clerk_user = ClerkUser(
            id="user_123",
            username="testuser",
            first_name="Test",
            last_name="User",
            email_verified=True,
            phone_verified=False,
            two_factor_enabled=True,
            created_at=datetime.utcnow() - timedelta(days=30),
            updated_at=datetime.utcnow(),
            last_sign_in_at=datetime.utcnow() - timedelta(hours=1)
        )
        
        extractor = UserDataExtractor(mock_clerk_manager)
        metadata = extractor.extract_user_metadata(clerk_user)
        
        assert metadata["account_age_days"] == 30
        assert metadata["is_verified"] is True
        assert "email" in metadata["verification_methods"]
        assert "2fa" in metadata["verification_methods"]
        assert "phone" not in metadata["verification_methods"]
        assert metadata["profile_completeness"] > 0.5


class TestUserSessionManager:
    """Test cases for UserSessionManager."""
    
    @pytest.mark.asyncio
    async def test_create_user_session_success(self, mock_clerk_manager, sample_token_info):
        """Test successful session creation."""
        mock_clerk_manager.verify_session_token.return_value = sample_token_info
        
        session_manager = UserSessionManager(mock_clerk_manager)
        session = await session_manager.create_user_session("test_token")
        
        assert session.user_id == "user_123"
        assert session.session_id == "sess_456"
        assert session.token_claims["sub"] == "user_123"
        assert not session.is_expired
        
        mock_clerk_manager.verify_session_token.assert_called_once_with("test_token")
    
    @pytest.mark.asyncio
    async def test_create_user_session_failure(self, mock_clerk_manager):
        """Test session creation failure."""
        mock_clerk_manager.verify_session_token.side_effect = Exception("Token invalid")
        
        session_manager = UserSessionManager(mock_clerk_manager)
        
        with pytest.raises(ClerkAuthError, match="Session creation failed"):
            await session_manager.create_user_session("invalid_token")
    
    @pytest.mark.asyncio
    async def test_validate_session_valid(self, mock_clerk_manager):
        """Test validation of valid session."""
        from src.app.models.user import UserSession
        
        session = UserSession(
            user_id="user_123",
            session_id="sess_456",
            verified_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        session_manager = UserSessionManager(mock_clerk_manager)
        is_valid = await session_manager.validate_session(session)
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_validate_session_expired(self, mock_clerk_manager):
        """Test validation of expired session."""
        from src.app.models.user import UserSession
        
        session = UserSession(
            user_id="user_123",
            session_id="sess_456",
            verified_at=datetime.utcnow() - timedelta(hours=2),
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        
        session_manager = UserSessionManager(mock_clerk_manager)
        is_valid = await session_manager.validate_session(session)
        
        assert is_valid is False


class TestUserPermissionChecker:
    """Test cases for UserPermissionChecker."""
    
    @pytest.mark.asyncio
    async def test_check_user_permissions_regular_user(self, mock_clerk_manager, sample_user_info):
        """Test permission checking for regular user."""
        mock_clerk_manager.get_user_info.return_value = sample_user_info
        
        permission_checker = UserPermissionChecker(mock_clerk_manager)
        permissions = await permission_checker.check_user_permissions("user_123")
        
        assert isinstance(permissions, UserPermissions)
        assert permissions.user_id == "user_123"
        assert permissions.role == UserRole.USER
        assert permissions.can_generate_videos is True
        assert permissions.can_view_all_jobs is False
        assert permissions.can_access_system_metrics is False
    
    @pytest.mark.asyncio
    async def test_check_user_permissions_admin_user(self, mock_clerk_manager):
        """Test permission checking for admin user."""
        admin_user_info = {
            "id": "admin_123",
            "email": "admin@admin.com",
            "first_name": "Admin",
            "last_name": "User",
            "email_verified": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        mock_clerk_manager.get_user_info.return_value = admin_user_info
        
        permission_checker = UserPermissionChecker(mock_clerk_manager)
        permissions = await permission_checker.check_user_permissions("admin_123")
        
        assert permissions.role == UserRole.ADMIN
        assert permissions.can_view_all_jobs is True
        assert permissions.can_access_system_metrics is True
        assert permissions.max_concurrent_jobs == 10
    
    @pytest.mark.asyncio
    async def test_validate_user_access_job(self, mock_clerk_manager, sample_user_info):
        """Test user access validation for job resource."""
        mock_clerk_manager.get_user_info.return_value = sample_user_info
        
        permission_checker = UserPermissionChecker(mock_clerk_manager)
        has_access = await permission_checker.validate_user_access("user_123", "job", "job_456")
        
        assert has_access is True
    
    def test_check_rate_limits(self, mock_clerk_manager):
        """Test rate limit checking."""
        permissions = UserPermissions.from_user_role("user_123", UserRole.USER)
        
        permission_checker = UserPermissionChecker(mock_clerk_manager)
        rate_limits = permission_checker.check_rate_limits("user_123", permissions)
        
        assert "max_concurrent_jobs" in rate_limits
        assert "max_daily_jobs" in rate_limits
        assert "current_concurrent_jobs" in rate_limits
        assert rate_limits["rate_limit_exceeded"] is False


class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    @pytest.mark.asyncio
    @patch('src.app.utils.user_utils.get_clerk_manager')
    async def test_extract_user_from_token(self, mock_get_clerk_manager, sample_token_info, sample_user_info):
        """Test user extraction from token."""
        mock_clerk_manager = Mock(spec=ClerkManager)
        mock_clerk_manager.verify_session_token = AsyncMock(return_value=sample_token_info)
        mock_clerk_manager.get_user_info = AsyncMock(return_value=sample_user_info)
        mock_get_clerk_manager.return_value = mock_clerk_manager
        
        user = await extract_user_from_token("test_token")
        
        assert isinstance(user, ClerkUser)
        assert user.id == "user_123"
        assert user.username == "testuser"
    
    @pytest.mark.asyncio
    async def test_validate_user_permission_success(self):
        """Test successful permission validation."""
        with patch('src.app.utils.user_utils.get_clerk_manager') as mock_get_clerk_manager:
            mock_clerk_manager = Mock(spec=ClerkManager)
            mock_clerk_manager.get_user_info = AsyncMock(return_value={
                "id": "user_123",
                "email": "test@example.com",
                "email_verified": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            mock_get_clerk_manager.return_value = mock_clerk_manager
            
            has_permission = await validate_user_permission("user_123", "generate_videos")
            
            assert has_permission is True
    
    @pytest.mark.asyncio
    async def test_validate_user_permission_failure(self):
        """Test permission validation failure."""
        with patch('src.app.utils.user_utils.get_clerk_manager') as mock_get_clerk_manager:
            mock_clerk_manager = Mock(spec=ClerkManager)
            mock_clerk_manager.get_user_info = AsyncMock(side_effect=Exception("API Error"))
            mock_get_clerk_manager.return_value = mock_clerk_manager
            
            has_permission = await validate_user_permission("user_123", "generate_videos")
            
            assert has_permission is False


class TestSessionCache:
    """Test cases for SessionCache."""
    
    def test_session_cache_operations(self):
        """Test basic session cache operations."""
        from src.app.models.user import AuthenticationContext, UserProfile, UserSession, UserPermissions
        
        cache = SessionCache()
        
        # Create test context
        user_profile = UserProfile(
            id="user_123",
            full_name="Test User",
            email="test@example.com",
            created_at=datetime.utcnow()
        )
        
        session = UserSession(
            user_id="user_123",
            session_id="sess_456",
            verified_at=datetime.utcnow()
        )
        
        permissions = UserPermissions.from_user_role("user_123", UserRole.USER)
        
        context = AuthenticationContext(
            user=user_profile,
            session=session,
            permissions=permissions
        )
        
        # Test cache operations
        cache.set("sess_456", context)
        cached_context = cache.get("sess_456")
        
        assert cached_context is not None
        assert cached_context.user.id == "user_123"
        
        cache.delete("sess_456")
        assert cache.get("sess_456") is None
    
    def test_clear_expired_sessions(self):
        """Test clearing expired sessions."""
        from src.app.models.user import AuthenticationContext, UserProfile, UserSession, UserPermissions
        
        cache = SessionCache()
        
        # Create expired session
        user_profile = UserProfile(
            id="user_123",
            full_name="Test User",
            email="test@example.com",
            created_at=datetime.utcnow()
        )
        
        expired_session = UserSession(
            user_id="user_123",
            session_id="sess_expired",
            verified_at=datetime.utcnow() - timedelta(hours=2),
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        
        permissions = UserPermissions.from_user_role("user_123", UserRole.USER)
        
        expired_context = AuthenticationContext(
            user=user_profile,
            session=expired_session,
            permissions=permissions
        )
        
        cache.set("sess_expired", expired_context)
        assert cache.get("sess_expired") is not None
        
        cache.clear_expired()
        assert cache.get("sess_expired") is None