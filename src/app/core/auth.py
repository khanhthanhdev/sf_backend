"""
Clerk authentication utilities and integration.

This module provides Clerk SDK integration, token validation,
and user information extraction for the FastAPI backend.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

import jwt
from jwt import PyJWTError
from fastapi import HTTPException, status
from clerk_backend_api import Clerk
from clerk_backend_api.models import User as ClerkUser

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ClerkAuthError(Exception):
    """Custom exception for Clerk authentication errors."""
    pass


class ClerkManager:
    """
    Clerk authentication manager.
    
    Provides centralized Clerk SDK integration, token validation,
    and user management for the FastAPI application.
    """
    
    def __init__(self):
        self._client: Optional[Clerk] = None
        self._is_initialized = False
    
    def initialize(self) -> None:
        """Initialize Clerk client."""
        try:
            if not settings.clerk_secret_key:
                raise ClerkAuthError("Clerk secret key not configured")
            
            self._client = Clerk(bearer_auth=settings.clerk_secret_key)
            self._is_initialized = True
            
            logger.info("Clerk authentication initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Clerk authentication: {e}")
            self._is_initialized = False
            raise ClerkAuthError(f"Clerk initialization failed: {e}")
    
    @property
    def client(self) -> Clerk:
        """Get Clerk client instance."""
        if not self._client or not self._is_initialized:
            raise ClerkAuthError("Clerk client not initialized")
        return self._client
    
    @property
    def is_initialized(self) -> bool:
        """Check if Clerk is initialized."""
        return self._is_initialized
    
    async def verify_session_token(self, session_token: str) -> Dict[str, Any]:
        """
        Verify Clerk session token and extract claims.
        
        Args:
            session_token: Clerk session token from request
            
        Returns:
            Dict containing token claims and user information
            
        Raises:
            ClerkAuthError: If token verification fails
        """
        try:
            if not settings.clerk_jwt_verification:
                logger.warning("JWT verification is disabled - this should only be used in development")
                # In development, we might want to skip verification
                # This is NOT recommended for production
                return {"sub": "dev_user", "session_id": "dev_session"}
            
            # Verify the JWT token
            # Note: In a real implementation, you would need to fetch Clerk's public keys
            # and verify the token signature. For now, we'll decode without verification
            # in development mode only.
            
            if settings.is_development:
                # Development mode - decode without verification (NOT for production)
                decoded_token = jwt.decode(
                    session_token, 
                    options={"verify_signature": False}
                )
            else:
                # Production mode - proper verification needed
                # You would need to implement proper JWT verification with Clerk's public keys
                raise NotImplementedError(
                    "Production JWT verification not implemented. "
                    "Please implement proper JWT verification with Clerk's public keys."
                )
            
            # Extract user ID and session information
            user_id = decoded_token.get("sub")
            session_id = decoded_token.get("sid")
            
            if not user_id:
                raise ClerkAuthError("Invalid token: missing user ID")
            
            return {
                "user_id": user_id,
                "session_id": session_id,
                "claims": decoded_token,
                "verified_at": datetime.utcnow().isoformat()
            }
            
        except PyJWTError as e:
            logger.error(f"JWT verification failed: {e}")
            raise ClerkAuthError(f"Invalid session token: {e}")
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise ClerkAuthError(f"Token verification failed: {e}")
    
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get user information from Clerk.
        
        Args:
            user_id: Clerk user ID
            
        Returns:
            Dict containing user information
            
        Raises:
            ClerkAuthError: If user retrieval fails
        """
        try:
            # In development mode, provide fallback user info if Clerk API fails
            if settings.is_development:
                try:
                    # Try to get user from Clerk
                    user_response = self.client.users.get(user_id=user_id)
                    
                    if user_response and user_response.object:
                        user: ClerkUser = user_response.object
                        
                        # Return the full user object structure for proper processing
                        # Convert the Clerk user object to a dict with all fields
                        user_dict = user.to_dict() if hasattr(user, 'to_dict') else {}
                        
                        # Ensure we have at least the basic structure
                        user_info = {
                            "id": getattr(user, 'id', user_id),
                            "object": getattr(user, 'object', 'user'),
                            "username": getattr(user, 'username', None),
                            "first_name": getattr(user, 'first_name', None),
                            "last_name": getattr(user, 'last_name', None),
                            "image_url": getattr(user, 'image_url', None),
                            "has_image": getattr(user, 'has_image', False),
                            "primary_email_address_id": getattr(user, 'primary_email_address_id', None),
                            "primary_phone_number_id": getattr(user, 'primary_phone_number_id', None),
                            "primary_web3_wallet_id": getattr(user, 'primary_web3_wallet_id', None),
                            "password_enabled": getattr(user, 'password_enabled', False),
                            "two_factor_enabled": getattr(user, 'two_factor_enabled', False),
                            "email_addresses": [],
                            "phone_numbers": getattr(user, 'phone_numbers', []),
                            "web3_wallets": getattr(user, 'web3_wallets', []),
                            "external_accounts": getattr(user, 'external_accounts', []),
                            "public_metadata": getattr(user, 'public_metadata', {}),
                            "private_metadata": getattr(user, 'private_metadata', {}),
                            "unsafe_metadata": getattr(user, 'unsafe_metadata', {}),
                            "delete_self_enabled": getattr(user, 'delete_self_enabled', True),
                            "create_organization_enabled": getattr(user, 'create_organization_enabled', True),
                            "last_sign_in_at": getattr(user, 'last_sign_in_at', None),
                            "banned": getattr(user, 'banned', False),
                            "locked": getattr(user, 'locked', False),
                            "lockout_expires_in_seconds": getattr(user, 'lockout_expires_in_seconds', None),
                            "verification_attempts_remaining": getattr(user, 'verification_attempts_remaining', 3),
                            "updated_at": getattr(user, 'updated_at', None),
                            "created_at": getattr(user, 'created_at', None),
                            "last_active_at": getattr(user, 'last_active_at', None)
                        }
                        
                        # Extract email addresses with full structure
                        if hasattr(user, 'email_addresses') and user.email_addresses:
                            email_addresses = []
                            for email_addr in user.email_addresses:
                                verification = getattr(email_addr, 'verification', None)
                                email_data = {
                                    "id": getattr(email_addr, 'id', None),
                                    "object": getattr(email_addr, 'object', 'email_address'),
                                    "email_address": getattr(email_addr, 'email_address', None),
                                    "verification": {
                                        "status": getattr(verification, 'status', 'unverified'),
                                        "strategy": getattr(verification, 'strategy', None),
                                        "attempts": getattr(verification, 'attempts', None),
                                        "expire_at": getattr(verification, 'expire_at', None)
                                    },
                                    "linked_to": getattr(email_addr, 'linked_to', [])
                                }
                                email_addresses.append(email_data)
                            user_info["email_addresses"] = email_addresses
                        
                        # Set email_verified based on verification status
                        email_verified = False
                        if user_info.get("email_addresses"):
                            for email_addr in user_info["email_addresses"]:
                                verification = email_addr.get("verification", {})
                                if verification.get("status") == "verified":
                                    email_verified = True
                                    break
                        user_info["email_verified"] = email_verified
                        
                        return user_info
                    else:
                        # No user found from Clerk API, use fallback
                        logger.warning(f"User not found in Clerk API for {user_id}, using fallback")
                        raise Exception("User not found, will use fallback")
                        
                except Exception as clerk_error:
                    logger.warning(f"Clerk API failed in development mode, using fallback: {clerk_error}")
                    # Fallback user info for development with proper structure
                    return {
                        "id": user_id,
                        "object": "user",
                        "username": "testuser",
                        "first_name": "Test",
                        "last_name": "User",
                        "image_url": None,
                        "has_image": False,
                        "primary_email_address_id": "email_fallback_001",
                        "primary_phone_number_id": None,
                        "primary_web3_wallet_id": None,
                        "password_enabled": True,
                        "two_factor_enabled": False,
                        "email_addresses": [
                            {
                                "id": "email_fallback_001",
                                "object": "email_address",
                                "email_address": "testuser@example.com",
                                "verification": {
                                    "status": "verified",
                                    "strategy": "email_code",
                                    "attempts": 1,
                                    "expire_at": None
                                },
                                "linked_to": []
                            }
                        ],
                        "phone_numbers": [],
                        "web3_wallets": [],
                        "external_accounts": [],
                        "public_metadata": {},
                        "private_metadata": {},
                        "unsafe_metadata": {},
                        "delete_self_enabled": True,
                        "create_organization_enabled": True,
                        "last_sign_in_at": None,
                        "banned": False,
                        "locked": False,
                        "lockout_expires_in_seconds": None,
                        "verification_attempts_remaining": 3,
                        "updated_at": None,
                        "created_at": None,
                        "last_active_at": None,
                        "email_verified": True  # Add this for compatibility
                    }
            else:
                # Production mode - strict Clerk API usage
                user_response = self.client.users.get(user_id=user_id)
                
                if not user_response or not user_response.object:
                    raise ClerkAuthError(f"User not found: {user_id}")
                
                user: ClerkUser = user_response.object
                
                # Return the full user object structure for proper processing
                user_info = {
                    "id": getattr(user, 'id', user_id),
                    "object": getattr(user, 'object', 'user'),
                    "username": getattr(user, 'username', None),
                    "first_name": getattr(user, 'first_name', None),
                    "last_name": getattr(user, 'last_name', None),
                    "image_url": getattr(user, 'image_url', None),
                    "has_image": getattr(user, 'has_image', False),
                    "primary_email_address_id": getattr(user, 'primary_email_address_id', None),
                    "primary_phone_number_id": getattr(user, 'primary_phone_number_id', None),
                    "primary_web3_wallet_id": getattr(user, 'primary_web3_wallet_id', None),
                    "password_enabled": getattr(user, 'password_enabled', False),
                    "two_factor_enabled": getattr(user, 'two_factor_enabled', False),
                    "email_addresses": [],
                    "phone_numbers": getattr(user, 'phone_numbers', []),
                    "web3_wallets": getattr(user, 'web3_wallets', []),
                    "external_accounts": getattr(user, 'external_accounts', []),
                    "public_metadata": getattr(user, 'public_metadata', {}),
                    "private_metadata": getattr(user, 'private_metadata', {}),
                    "unsafe_metadata": getattr(user, 'unsafe_metadata', {}),
                    "delete_self_enabled": getattr(user, 'delete_self_enabled', True),
                    "create_organization_enabled": getattr(user, 'create_organization_enabled', True),
                    "last_sign_in_at": getattr(user, 'last_sign_in_at', None),
                    "banned": getattr(user, 'banned', False),
                    "locked": getattr(user, 'locked', False),
                    "lockout_expires_in_seconds": getattr(user, 'lockout_expires_in_seconds', None),
                    "verification_attempts_remaining": getattr(user, 'verification_attempts_remaining', 3),
                    "updated_at": getattr(user, 'updated_at', None),
                    "created_at": getattr(user, 'created_at', None),
                    "last_active_at": getattr(user, 'last_active_at', None)
                }
                
                # Extract email addresses with full structure
                if hasattr(user, 'email_addresses') and user.email_addresses:
                    email_addresses = []
                    for email_addr in user.email_addresses:
                        verification = getattr(email_addr, 'verification', None)
                        email_data = {
                            "id": getattr(email_addr, 'id', None),
                            "object": getattr(email_addr, 'object', 'email_address'),
                            "email_address": getattr(email_addr, 'email_address', None),
                            "verification": {
                                "status": getattr(verification, 'status', 'unverified'),
                                "strategy": getattr(verification, 'strategy', None),
                                "attempts": getattr(verification, 'attempts', None),
                                "expire_at": getattr(verification, 'expire_at', None)
                            },
                            "linked_to": getattr(email_addr, 'linked_to', [])
                        }
                        email_addresses.append(email_data)
                    user_info["email_addresses"] = email_addresses
                
                # Set email_verified based on verification status
                email_verified = False
                if user_info.get("email_addresses"):
                    for email_addr in user_info["email_addresses"]:
                        verification = email_addr.get("verification", {})
                        if verification.get("status") == "verified":
                            email_verified = True
                            break
                user_info["email_verified"] = email_verified
                
                return user_info
            
        except ClerkAuthError:
            raise
        except Exception as e:
            logger.error(f"Failed to get user info for {user_id}: {e}")
            raise ClerkAuthError(f"Failed to retrieve user information: {e}")
    
    async def validate_user_permissions(self, user_id: str, required_permission: str = None) -> bool:
        """
        Validate user permissions (placeholder for future implementation).
        
        Args:
            user_id: Clerk user ID
            required_permission: Required permission (optional)
            
        Returns:
            True if user has required permissions
        """
        try:
            # For now, all authenticated users have basic permissions
            # This can be extended to check specific roles/permissions
            user_info = await self.get_user_info(user_id)
            
            # Basic validation - user exists and is verified
            if not user_info.get("email_verified", False):
                logger.warning(f"User {user_id} email not verified")
                return False
            
            # TODO: Implement role-based permission checking
            # This would involve checking user roles/metadata in Clerk
            
            return True
            
        except Exception as e:
            logger.error(f"Permission validation failed for {user_id}: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform Clerk authentication health check.
        
        Returns:
            Dict containing health status
        """
        try:
            if not self._is_initialized:
                return {
                    "status": "unhealthy",
                    "error": "Clerk client not initialized"
                }
            
            # Basic connectivity check
            # In a real implementation, you might want to make a test API call
            return {
                "status": "healthy",
                "initialized": self._is_initialized,
                "jwt_verification_enabled": settings.clerk_jwt_verification,
                "environment": settings.environment
            }
            
        except Exception as e:
            logger.error(f"Clerk health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Global Clerk manager instance
clerk_manager = ClerkManager()


def get_clerk_manager() -> ClerkManager:
    """
    Get Clerk manager instance.
    
    Returns:
        ClerkManager instance
    """
    return clerk_manager


class AuthenticationError(HTTPException):
    """Custom authentication error with consistent formatting."""
    
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationError(HTTPException):
    """Custom authorization error with consistent formatting."""
    
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


def extract_bearer_token(authorization_header: str) -> str:
    """
    Extract bearer token from Authorization header.
    
    Args:
        authorization_header: Authorization header value
        
    Returns:
        Bearer token string
        
    Raises:
        AuthenticationError: If token extraction fails
    """
    if not authorization_header:
        raise AuthenticationError("Missing authorization header")
    
    try:
        scheme, token = authorization_header.split(" ", 1)
        if scheme.lower() != "bearer":
            raise AuthenticationError("Invalid authentication scheme")
        
        if not token:
            raise AuthenticationError("Missing bearer token")
        
        return token
        
    except ValueError:
        raise AuthenticationError("Invalid authorization header format")


async def verify_clerk_token(token: str) -> Dict[str, Any]:
    """
    Verify Clerk session token and return user information.
    
    Args:
        token: Clerk session token
        
    Returns:
        Dict containing user information and token claims
        
    Raises:
        AuthenticationError: If token verification fails
    """
    try:
        # Verify token with Clerk
        token_info = await clerk_manager.verify_session_token(token)
        
        # Get user information
        user_info = await clerk_manager.get_user_info(token_info["user_id"])
        
        return {
            "token_info": token_info,
            "user_info": user_info
        }
        
    except ClerkAuthError as e:
        raise AuthenticationError(str(e))
    except Exception as e:
        logger.error("Token verification failed", extra={"error": str(e)}, exc_info=True)
        raise AuthenticationError("Token verification failed")