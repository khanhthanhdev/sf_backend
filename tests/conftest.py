"""
Test configuration and fixtures.
"""

import pytest
from fastapi.testclient import TestClient

from src.app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_settings():
    """Test settings override."""
    from src.app.core.config import Settings
    
    return Settings(
        environment="testing",
        debug=True,
        clerk_secret_key="test_secret_key",
        clerk_publishable_key="test_publishable_key",
        secret_key="test_secret_key_for_testing",
        redis_url="redis://localhost:6379/1",  # Use different DB for tests
    )