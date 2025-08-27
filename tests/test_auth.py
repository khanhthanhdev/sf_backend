"""
Unit tests for Clerk authentication integration.

This module tests the authentication flow, user management utilities,
and permission checking functionality.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from src.app.core.auth import (
    ClerkManager, 
    ClerkAuthError, 
    extract_bearer_token,
    verify_clerk_token,
    AuthenticationError
)
from src.app.middleware.clerk_auth import ClerkAuthMiddleware
from src.app.services.user_service import UserService
from src.app.models.user import (
    UserProfile, 
    UserSession, 
    UserPermissions, 
    UserRole,
    AuthenticationContext
)


class TestClerkManager:
    """Test cases for ClerkManager class."""
    
    @pytest.fixture
    def clerk_manager(self):
        """Create ClerkManager instance for testing."""
        manager = ClerkManager()
        return manager
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('src.app.core.auth.settings') as mock_settings:
            mock_settings.clerk_secret_key = "test_secret_key"
            mock_settings.clerk_jwt_verification = False
            mock_settings.is_development = True
            mock_settings.is_production = False
            yield mock_settings
    
    def test_initialize_success(self, clerk_manager, mock_settings):
        """Test successful Clerk manager initialization."""
        with patch('src.app.core.auth.Clerk') as mock_clerk:
            mock_clerk.return_value = Mock()
            
            clerk_manager.initialize()
            
            assert clerk_manager.is_initialized
            mock_clerk.assert_called_once_with(bearer_auth="test_secret_key")
    
    def test_initialize_missing_secret_key(self, clerk_manager, mock_settings):
        """Test initialization failure with missing secret key."""
        mock_settings.clerk_secret_key = ""
        
        with pytest.raises(ClerkAuthError, match="Clerk secret key not configured"):
            clerk_manager.initialize()
    
    @pytest.mark.asyncio
    async def test_verify_session_token_development(self, clerk_manager, mock_settings):
        """Test session token verification in development mode."""
        clerk_manager._is_initialized = True
        
        test_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyXzEyMyIsInNpZCI6InNlc3Npb25fNDU2In0.test"
        
        with patch('jwt.decode') as mock_decode:
            mock_decode.return_value = {"sub": "user_123", "sid": "session_456"}
            
            result = await clerk_manager.verify_session_token(test_token)
            
            assert result["user_id"] == "user_123"
            assert result["session_id"] == "session_456"
            assert "verified_at" in result
    
    @pytest.mark.asyncio
    async def test_verify_session_token_invalid(self, clerk_manager, mock_settings):
        """Test session token verification with invalid token."""
        clerk_manager._is_initialized = True
        
        with patch('jwt.decode') as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")
            
            with pytest.raises(ClerkAuthError, match="Token verification failed"):
                await clerk_manager.verify_session_token("invalid_token")
    
    @pytest.mark.asyncio
    async def test_get_user_info_success(self, clerk_manager):
        """Test successful user info retrieval."""
        clerk_manager._is_initialized = True
        
        mock_user = Mock()
        mock_user.id = "user_123"
        mock_user.email_addresses = [Mock(email_address="test@example.com")]
        mock_user.email_addresses[0].verification.status = "verified"
        mock_user.first_name = "John"
        mock_user.last_name = "Doe"
        mock_user.username = "johndoe"
        mock_user.image_url = "https://example.com/avatar.jpg"
        mock_user.created_at = datetime.utcnow()
        mock_user.updated_at = datetime.utcnow()
        mock_user.last_sign_in_at = datetime.utcnow()
        
        mock_response = Mock()
        mock_response.object = mock_user
        
        mock_client = Mock()
        mock_client.users.get.return_value = mock_response
        clerk_manager._client = mock_client
        
        result = await clerk_manager.get_user_info("user_123")
        
        assert result["id"] == "user_123"
        assert result["email"] == "test@example.com"
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["email_verified"] is True
    
    @pytest.mark.asyncio
    async def test_get_user_info_not_found(self, clerk_manager):
        """Test user info retrieval with user not found."""
        clerk_manager._is_initialized = True
        
        mock_client = Mock()
        mock_client.users.get.return_value = None
        clerk_manager._client = mock_client
        
        with pytest.raises(ClerkAuthError, match="User not found"):
            await clerk_manager.get_user_info("nonexistent_user")
    
    @pytest.mark.asyncio
    async def test_validate_user_permissions_verified(self, clerk_manager):
        """Test user permission validation for verified user."""
        clerk_manager._is_initialized = True
        
        # Mock get_user_info to return verified user
        with patch.object(clerk_manager, 'get_user_info') as mock_get_user:
            mock_get_user.return_value = {"email_verified": True}
            
            result = await clerk_manager.validate_user_permissions("user_123")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_user_permissions_unverified(self, clerk_manager):
        """Test user permission validation for unverified user."""
        clerk_manager._is_initialized = True
        
        # Mock get_user_info to return unverified user
        with patch.object(clerk_manager, 'get_user_info') as mock_get_user:
            mock_get_user.return_value = {"email_verified": False}
            
            result = await clerk_manager.validate_user_permissions("user_123")
            
            assert result is False
    
    def test_health_check_healthy(self, clerk_manager):
        """Test health check when Clerk is healthy."""
        clerk_manager._is_initialized = True
        
        with patch('src.app.core.auth.settings') as mock_settings:
            mock_settings.clerk_jwt_verification = True
            mock_settings.environment = "development"
            
            result = clerk_manager.health_check()
            
            assert result["status"] == "healthy"
            assert result["initialized"] is True
            assert result["jwt_verification_enabled"] is True
    
    def test_health_check_unhealthy(self, clerk_manager):
        """Test health check when Clerk is not initialized."""
        clerk_manager._is_initialized = False
        
        result = clerk_manager.health_check()
        
        assert result["status"] == "unhealthy"
        assert "not initialized" in result["error"]


class TestAuthenticationUtilities:
    """Test cases for authentication utility functions."""
    
    def test_extract_bearer_token_success(self):
        """Test successful bearer token extraction."""
        auth_header = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9"
        
        token = extract_bearer_token(auth_header)
        
        assert token == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9"
    
    def test_extract_bearer_token_missing_header(self):
        """Test bearer token extraction with missing header."""
        with pytest.raises(AuthenticationError, match="Missing authorization header"):
            extract_bearer_token("")
    
    def test_extract_bearer_token_invalid_scheme(self):
        """Test bearer token extraction with invalid scheme."""
        auth_header = "Basic dXNlcjpwYXNz"
        
        with pytest.raises(AuthenticationError, match="Invalid authentication scheme"):
            extract_bearer_token(auth_header)
    
    def test_extract_bearer_token_missing_token(self):
        """Test bearer token extraction with missing token."""
        auth_header = "Bearer "
        
        with pytest.raises(AuthenticationError, match="Missing bearer token"):
            extract_bearer_token(auth_header)
    
    def test_extract_bearer_token_invalid_format(self):
        """Test bearer token extraction with invalid format."""
        auth_header = "InvalidFormat"
        
        with pytest.raises(AuthenticationError, match="Invalid authorization header format"):
            extract_bearer_token(auth_header)
    
    @pytest.mark.asyncio
    async def test_verify_clerk_token_success(self):
        """Test successful Clerk token verification."""
        test_token = "valid_token"
        
        with patch('src.app.core.auth.clerk_manager') as mock_manager:
            mock_manager.verify_session_token.return_value = {
                "user_id": "user_123",
                "session_id": "session_456"
            }
            mock_manager.get_user_info.return_value = {
                "id": "user_123",
                "email": "test@example.com",
                "first_name": "John",
                "last_name": "Doe"
            }
            
            result = await verify_clerk_token(test_token)
            
            assert "token_info" in result
            assert "user_info" in result
            assert result["user_info"]["id"] == "user_123"
    
    @pytest.mark.asyncio
    async def test_verify_clerk_token_failure(self):
        """Test Clerk token verification failure."""
        test_token = "invalid_token"
        
        with patch('src.app.core.auth.clerk_manager') as mock_manager:
            mock_manager.verify_session_token.side_effect = ClerkAuthError("Invalid token")
            
            with pytest.raises(AuthenticationError, match="Invalid token"):
                await verify_clerk_token(test_token)


class TestUserService:
    """Test cases for UserService class."""
    
    @pytest.fixture
    def user_service(self):
        """Create UserService instance for testing."""
        service = UserService()
        service.redis_client = AsyncMock()
        return service
    
    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing."""
        return {
            "id": "user_123",
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
            "image_url": "https://example.com/avatar.jpg",
            "email_verified": True,
            "created_at": datetime.utcnow(),
            "last_sign_in_at": datetime.utcnow()
        }
    
    @pytest.mark.asyncio
    async def test_extract_user_data_success(self, user_service, sample_user_data):
        """Test successful user data extraction."""
        with patch('src.app.services.user_service.clerk_manager') as mock_manager:
            mock_manager.get_user_info.return_value = sample_user_data
            
            with patch('src.app.services.user_service.redis_json_set') as mock_redis_set:
                result = await user_service.extract_user_data("user_123")
                
                assert result == sample_user_data
                mock_redis_set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_cached_user_data_success(self, user_service, sample_user_data):
        """Test successful cached user data retrieval."""
        with patch('src.app.services.user_service.redis_json_get') as mock_redis_get:
            mock_redis_get.return_value = sample_user_data
            
            result = await user_service.get_cached_user_data("user_123")
            
            assert result == sample_user_data
    
    @pytest.mark.asyncio
    async def test_get_cached_user_data_not_found(self, user_service):
        """Test cached user data retrieval when not found."""
        with patch('src.app.services.user_service.redis_json_get') as mock_redis_get:
            mock_redis_get.return_value = None
            
            result = await user_service.get_cached_user_data("user_123")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_create_user_session_success(self, user_service):
        """Test successful user session creation."""
        with patch('src.app.services.user_service.redis_json_set') as mock_redis_set:
            session = await user_service.create_user_session(
                "user_123", 
                "session_456", 
                {"sub": "user_123"}
            )
            
            assert session.user_id == "user_123"
            assert session.session_id == "session_456"
            assert session.token_claims == {"sub": "user_123"}
            mock_redis_set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_session_success(self, user_service):
        """Test successful user session retrieval."""
        session_data = {
            "user_id": "user_123",
            "session_id": "session_456",
            "token_claims": {},
            "verified_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
        
        with patch('src.app.services.user_service.redis_json_get') as mock_redis_get:
            mock_redis_get.return_value = session_data
            
            session = await user_service.get_user_session("user_123")
            
            assert session is not None
            assert session.user_id == "user_123"
            assert session.session_id == "session_456"
    
    @pytest.mark.asyncio
    async def test_get_user_session_expired(self, user_service):
        """Test user session retrieval with expired session."""
        session_data = {
            "user_id": "user_123",
            "session_id": "session_456",
            "token_claims": {},
            "verified_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat()  # Expired
        }
        
        with patch('src.app.services.user_service.redis_json_get') as mock_redis_get:
            mock_redis_get.return_value = session_data
            
            with patch.object(user_service, 'invalidate_user_session') as mock_invalidate:
                session = await user_service.get_user_session("user_123")
                
                assert session is None
                mock_invalidate.assert_called_once_with("user_123")
    
    @pytest.mark.asyncio
    async def test_get_user_permissions_default(self, user_service, sample_user_data):
        """Test user permissions retrieval with default role."""
        with patch('src.app.services.user_service.redis_json_get') as mock_redis_get:
            mock_redis_get.return_value = None  # No cached permissions
            
            with patch.object(user_service, 'get_user_data') as mock_get_user:
                mock_get_user.return_value = sample_user_data
                
                with patch('src.app.services.user_service.redis_json_set') as mock_redis_set:
                    permissions = await user_service.get_user_permissions("user_123")
                    
                    assert permissions.user_id == "user_123"
                    assert permissions.role == UserRole.USER
                    assert permissions.can_generate_videos is True
                    mock_redis_set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_permissions_admin(self, user_service):
        """Test user permissions retrieval for admin user."""
        admin_user_data = {
            "id": "user_123",
            "email": "admin@admin.com",  # Admin email pattern
            "first_name": "Admin",
            "last_name": "User",
            "email_verified": True
        }
        
        with patch('src.app.services.user_service.redis_json_get') as mock_redis_get:
            mock_redis_get.return_value = None  # No cached permissions
            
            with patch.object(user_service, 'get_user_data') as mock_get_user:
                mock_get_user.return_value = admin_user_data
                
                with patch('src.app.services.user_service.redis_json_set') as mock_redis_set:
                    permissions = await user_service.get_user_permissions("user_123")
                    
                    assert permissions.user_id == "user_123"
                    assert permissions.role == UserRole.ADMIN
                    assert permissions.can_access_system_metrics is True
                    assert permissions.can_view_all_jobs is True
    
    @pytest.mark.asyncio
    async def test_check_user_permission_success(self, user_service):
        """Test successful user permission check."""
        mock_permissions = UserPermissions.from_user_role("user_123", UserRole.USER)
        mock_permissions.permissions = ["generate_videos"]
        
        with patch.object(user_service, 'get_user_permissions') as mock_get_permissions:
            mock_get_permissions.return_value = mock_permissions
            
            result = await user_service.check_user_permission("user_123", "generate_videos")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_check_user_permission_failure(self, user_service):
        """Test user permission check failure."""
        mock_permissions = UserPermissions.from_user_role("user_123", UserRole.USER)
        
        with patch.object(user_service, 'get_user_permissions') as mock_get_permissions:
            mock_get_permissions.return_value = mock_permissions
            
            result = await user_service.check_user_permission("user_123", "admin_access")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_create_authentication_context_success(self, user_service, sample_user_data):
        """Test successful authentication context creation."""
        with patch.object(user_service, 'get_user_data') as mock_get_user:
            mock_get_user.return_value = sample_user_data
            
            with patch.object(user_service, 'create_user_session') as mock_create_session:
                mock_session = UserSession(
                    user_id="user_123",
                    verified_at=datetime.utcnow()
                )
                mock_create_session.return_value = mock_session
                
                with patch.object(user_service, 'get_user_permissions') as mock_get_permissions:
                    mock_permissions = UserPermissions.from_user_role("user_123", UserRole.USER)
                    mock_get_permissions.return_value = mock_permissions
                    
                    context = await user_service.create_authentication_context("user_123")
                    
                    assert context.user.id == "user_123"
                    assert context.session.user_id == "user_123"
                    assert context.permissions.user_id == "user_123"
                    assert context.is_authenticated is True
    
    @pytest.mark.asyncio
    async def test_log_user_activity_success(self, user_service):
        """Test successful user activity logging."""
        activity_details = {
            "action": "login",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0"
        }
        
        result = await user_service.log_user_activity("user_123", "login", activity_details)
        
        assert result is True
        user_service.redis_client.lpush.assert_called_once()
        user_service.redis_client.ltrim.assert_called_once()
        user_service.redis_client.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, user_service):
        """Test cleanup of expired sessions."""
        # Mock Redis keys method to return session keys
        user_service.redis_client.keys.return_value = [
            "cache:user_session:user_123",
            "cache:user_session:user_456"
        ]
        
        # Mock expired session data
        expired_session = {
            "user_id": "user_123",
            "verified_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat()
        }
        
        valid_session = {
            "user_id": "user_456",
            "verified_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
        
        with patch('src.app.services.user_service.redis_json_get') as mock_redis_get:
            mock_redis_get.side_effect = [expired_session, valid_session]
            
            cleaned_count = await user_service.cleanup_expired_sessions()
            
            assert cleaned_count == 1
            user_service.redis_client.delete.assert_called_once_with("cache:user_session:user_123")


class TestUserModels:
    """Test cases for user data models."""
    
    def test_user_profile_creation(self):
        """Test UserProfile model creation."""
        profile = UserProfile(
            id="user_123",
            username="johndoe",
            full_name="John Doe",
            email="john@example.com",
            email_verified=True,
            created_at=datetime.utcnow()
        )
        
        assert profile.id == "user_123"
        assert profile.username == "johndoe"
        assert profile.full_name == "John Doe"
        assert profile.email == "john@example.com"
        assert profile.email_verified is True
    
    def test_user_session_expiration(self):
        """Test UserSession expiration check."""
        # Create expired session
        expired_session = UserSession(
            user_id="user_123",
            verified_at=datetime.utcnow(),
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        
        assert expired_session.is_expired is True
        
        # Create valid session
        valid_session = UserSession(
            user_id="user_123",
            verified_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        assert valid_session.is_expired is False
    
    def test_user_permissions_from_role(self):
        """Test UserPermissions creation from role."""
        # Test user role
        user_permissions = UserPermissions.from_user_role("user_123", UserRole.USER)
        
        assert user_permissions.role == UserRole.USER
        assert user_permissions.can_generate_videos is True
        assert user_permissions.can_access_system_metrics is False
        assert user_permissions.max_concurrent_jobs == 3
        
        # Test admin role
        admin_permissions = UserPermissions.from_user_role("admin_123", UserRole.ADMIN)
        
        assert admin_permissions.role == UserRole.ADMIN
        assert admin_permissions.can_generate_videos is True
        assert admin_permissions.can_access_system_metrics is True
        assert admin_permissions.max_concurrent_jobs == 10
    
    def test_user_permissions_has_permission(self):
        """Test UserPermissions permission checking."""
        permissions = UserPermissions.from_user_role("user_123", UserRole.USER)
        permissions.permissions = ["generate_videos", "upload_files"]
        
        assert permissions.has_permission("generate_videos") is True
        assert permissions.has_permission("upload_files") is True
        assert permissions.has_permission("admin_access") is False
        
        # Test admin permissions (admin has all permissions)
        admin_permissions = UserPermissions.from_user_role("admin_123", UserRole.ADMIN)
        
        assert admin_permissions.has_permission("any_permission") is True
    
    def test_authentication_context_properties(self):
        """Test AuthenticationContext properties."""
        user_profile = UserProfile(
            id="user_123",
            full_name="John Doe",
            email="john@example.com",
            email_verified=True,
            created_at=datetime.utcnow()
        )
        
        user_session = UserSession(
            user_id="user_123",
            verified_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        user_permissions = UserPermissions.from_user_role("user_123", UserRole.USER)
        
        context = AuthenticationContext(
            user=user_profile,
            session=user_session,
            permissions=user_permissions
        )
        
        assert context.user_id == "user_123"
        assert context.is_authenticated is True
        assert context.is_verified is True
        assert context.can_perform_action("generate_videos") is False  # Not in permissions list


if __name__ == "__main__":
    pytest.main([__file__])