"""
Secure URL generation utilities for file access.

This module provides utilities for generating secure, time-limited URLs
for file access with proper authentication and authorization checks.
"""

import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from ..core.config import get_settings
from ..core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class SecureURLGenerator:
    """Generator for secure, time-limited file access URLs."""
    
    def __init__(self, secret_key: Optional[str] = None):
        """Initialize with secret key for URL signing."""
        self.secret_key = secret_key or getattr(settings, 'url_signing_key', 'default-secret-key')
    
    def generate_signed_url(
        self,
        file_id: str,
        user_id: str,
        file_type: str,
        expires_in: int = 3600,
        inline: bool = False,
        additional_params: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate a signed URL for secure file access.
        
        Args:
            file_id: File identifier
            user_id: User ID for access control
            file_type: Type of file
            expires_in: Expiration time in seconds
            inline: Whether to serve inline
            additional_params: Additional URL parameters
            
        Returns:
            Signed URL with expiration and security token
        """
        try:
            # Calculate expiration timestamp
            expires_at = int(time.time()) + expires_in
            
            # Base parameters
            params = {
                'user_id': user_id,
                'expires': str(expires_at),
                'file_type': file_type
            }
            
            if inline:
                params['inline'] = 'true'
            
            # Add additional parameters
            if additional_params:
                params.update(additional_params)
            
            # Generate signature
            signature = self._generate_signature(file_id, params)
            params['signature'] = signature
            
            # Build URL
            base_url = f"/api/v1/files/{file_id}/secure"
            query_string = urlencode(params)
            
            signed_url = f"{base_url}?{query_string}"
            
            logger.debug(
                "Generated signed URL",
                file_id=file_id,
                user_id=user_id,
                expires_in=expires_in,
                url_length=len(signed_url)
            )
            
            return signed_url
            
        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            # Fallback to basic URL
            return f"/api/v1/files/{file_id}/download"
    
    def verify_signed_url(
        self,
        file_id: str,
        params: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Verify a signed URL and extract parameters.
        
        Args:
            file_id: File identifier
            params: URL parameters to verify
            
        Returns:
            Dictionary with verification result and extracted data
        """
        try:
            # Check required parameters
            required_params = ['user_id', 'expires', 'signature']
            for param in required_params:
                if param not in params:
                    return {
                        'valid': False,
                        'error': f'Missing required parameter: {param}'
                    }
            
            # Check expiration
            expires_at = int(params['expires'])
            current_time = int(time.time())
            
            if current_time > expires_at:
                return {
                    'valid': False,
                    'error': 'URL has expired'
                }
            
            # Verify signature
            signature = params.pop('signature')
            expected_signature = self._generate_signature(file_id, params)
            
            if not hmac.compare_digest(signature, expected_signature):
                return {
                    'valid': False,
                    'error': 'Invalid signature'
                }
            
            # Extract data
            return {
                'valid': True,
                'user_id': params['user_id'],
                'file_type': params.get('file_type'),
                'inline': params.get('inline', 'false').lower() == 'true',
                'expires_at': datetime.fromtimestamp(expires_at)
            }
            
        except Exception as e:
            logger.error(f"Failed to verify signed URL: {e}")
            return {
                'valid': False,
                'error': 'Verification failed'
            }
    
    def _generate_signature(self, file_id: str, params: Dict[str, str]) -> str:
        """Generate HMAC signature for URL parameters."""
        # Sort parameters for consistent signature
        sorted_params = sorted(params.items())
        
        # Create message to sign
        message_parts = [file_id] + [f"{k}={v}" for k, v in sorted_params]
        message = "&".join(message_parts)
        
        # Generate HMAC signature
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def generate_thumbnail_url(
        self,
        file_id: str,
        user_id: str,
        size: str = "medium",
        expires_in: int = 86400  # 24 hours for thumbnails
    ) -> str:
        """Generate signed URL for thumbnail access."""
        return self.generate_signed_url(
            file_id=file_id,
            user_id=user_id,
            file_type="thumbnail",
            expires_in=expires_in,
            inline=True,
            additional_params={'size': size}
        )
    
    def generate_streaming_url(
        self,
        file_id: str,
        user_id: str,
        quality: str = "auto",
        expires_in: int = 7200  # 2 hours for streaming
    ) -> str:
        """Generate signed URL for streaming access."""
        return self.generate_signed_url(
            file_id=file_id,
            user_id=user_id,
            file_type="stream",
            expires_in=expires_in,
            inline=True,
            additional_params={'quality': quality}
        )
    
    def generate_download_url(
        self,
        file_id: str,
        user_id: str,
        file_type: str,
        expires_in: int = 3600,
        inline: bool = False
    ) -> str:
        """Generate signed URL for download access."""
        return self.generate_signed_url(
            file_id=file_id,
            user_id=user_id,
            file_type=file_type,
            expires_in=expires_in,
            inline=inline
        )


# Global URL generator instance
secure_url_generator = SecureURLGenerator()


# Utility functions
def generate_secure_file_url(
    file_id: str,
    user_id: str,
    file_type: str,
    expires_in: int = 3600,
    inline: bool = False
) -> str:
    """Generate secure file URL with expiration."""
    return secure_url_generator.generate_download_url(
        file_id=file_id,
        user_id=user_id,
        file_type=file_type,
        expires_in=expires_in,
        inline=inline
    )


def generate_secure_thumbnail_url(
    file_id: str,
    user_id: str,
    size: str = "medium"
) -> str:
    """Generate secure thumbnail URL."""
    return secure_url_generator.generate_thumbnail_url(
        file_id=file_id,
        user_id=user_id,
        size=size
    )


def generate_secure_streaming_url(
    file_id: str,
    user_id: str,
    quality: str = "auto"
) -> str:
    """Generate secure streaming URL."""
    return secure_url_generator.generate_streaming_url(
        file_id=file_id,
        user_id=user_id,
        quality=quality
    )


def verify_url_signature(file_id: str, params: Dict[str, str]) -> Dict[str, Any]:
    """Verify URL signature and extract parameters."""
    return secure_url_generator.verify_signed_url(file_id, params)