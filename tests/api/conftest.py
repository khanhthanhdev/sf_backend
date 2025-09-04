"""
API test configuration and fixtures.

Provides a shared FastAPI TestClient with environment setup and
dependency overrides for external services (Redis, AWS, Clerk).
"""

import os
import pytest
from typing import Any, Dict, Optional

from fastapi.testclient import TestClient


class FakeRedis:
    """Minimal in-memory fake Redis for metrics and simple ops used by endpoints."""

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._lists: Dict[str, list] = {}

    async def ping(self):
        return True

    async def info(self):
        return {
            "used_memory": 1024 * 1024,  # 1MB
            "connected_clients": 1,
            "total_commands_processed": 10,
            "keyspace_hits": 5,
            "keyspace_misses": 1,
            "redis_version": "7.0.0",
            "uptime_in_seconds": 100,
        }

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None):
        self._store[key] = value
        return True

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    # Pipeline compatibility used by redis_transaction if needed
    def pipeline(self, transaction: bool = True):
        class _Pipe:
            def __init__(self, outer):
                self.outer = outer
                self.ops = []

            def set(self, key: str, value: Any):
                self.ops.append(("set", key, value))
                return self

            def incr(self, key: str):
                self.ops.append(("incr", key))
                return self

            async def execute(self):
                for op in self.ops:
                    if op[0] == "set":
                        _, k, v = op
                        await self.outer.set(k, v)
                    elif op[0] == "incr":
                        _, k = op
                        val = int((await self.outer.get(k)) or 0) + 1
                        await self.outer.set(k, str(val))
                self.ops.clear()
                return True

            async def reset(self):
                self.ops.clear()

        return _Pipe(self)


class FakeVideoService:
    """Minimal in-memory fake VideoService to back job status/metadata queries."""

    def __init__(self):
        # job_id -> job dict (serializable) to be rehydrated with pydantic models when needed
        self._jobs: Dict[str, Dict[str, Any]] = {}

    async def get_job_status(self, job_id: str):
        # Lazily import to avoid heavy imports at module load
        from src.app.models.job import Job
        data = self._jobs.get(job_id)
        if not data:
            return None
        # Return pydantic model instance as real service would
        return Job(**data)

    def set_job(self, job_id: str, job_dict: Dict[str, Any]):
        self._jobs[job_id] = job_dict


class FakeAWSJobService:
    async def get_jobs_paginated(self, user_id: str, limit: int, offset: int, filters: Dict[str, Any]):
        # Return shape compatible with JobListResponse (Pydantic will coerce)
        return {
            "jobs": [],
            "page": (offset // max(limit, 1)) + 1 if limit else 1,
            "items_per_page": limit,
            "total_count": 0,
            "has_more": False,
        }

    async def get_job(self, job_id: str, user_id: str):
        # Return a simple fake job dict
        return {
            "id": job_id,
            "user_id": user_id,
            "status": "queued",
            "progress_percentage": 0,
            "created_at": None,
            "updated_at": None,
        }

    async def cancel_job(self, job_id: str) -> bool:
        return True

    async def delete_job(self, job_id: str) -> bool:
        return True

    async def get_job_logs(self, job_id: str, limit: int, offset: int, level: Optional[str] = None):
        return {"logs": [], "total_count": 0}


class FakeEnhancedVideoService:
    class _Job:
        def __init__(self, job_id: str):
            from datetime import datetime
            self.id = job_id
            self.status = "queued"
            self.priority = "normal"
            self.progress = None
            self.created_at = datetime.utcnow()

    async def create_video_job(self, request, user_id: str, user_info: Dict[str, Any]):
        return self._Job(job_id="test-job-123")

    async def process_video_with_core_pipeline(self, job_id: str):
        return None


class FakeAWSS3FileService:
    async def upload_file(self, file, user_id: str, file_type: str, job_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        return {
            "file_id": "file-123",
            "s3_url": "s3://bucket/file-123",
            "download_url": "/api/v1/files/file-123/download",
        }


@pytest.fixture(scope="session")
def test_env(monkeysession):
    """Set test-friendly environment before app import."""
    monkeysession.setenv("ENVIRONMENT", "development")  # enable dev fallback paths
    monkeysession.setenv("CLERK_JWT_VERIFICATION", "false")
    # Ensure docs available
    monkeysession.setenv("DOCS_URL", "/docs")
    monkeysession.setenv("REDOC_URL", "/redoc")
    monkeysession.setenv("OPENAPI_URL", "/openapi.json")
    return True


@pytest.fixture(scope="session")
def fake_redis_instance():
    return FakeRedis()


@pytest.fixture(scope="session")
def fake_video_service_instance():
    return FakeVideoService()


@pytest.fixture()
def api_client(test_env, fake_redis_instance, fake_video_service_instance):
    """Create a TestClient with dependency overrides for external services."""
    # Import after env setup
    from src.app.main import app
    from src.app.core.redis import get_redis
    from src.app.api.dependencies import (
        get_aws_job_service,
        get_enhanced_video_service,
        get_video_service,
        get_aws_file_service,
        get_current_user as dep_get_current_user,
    )

    # Basic overrides
    # Use shared fakes to preserve state across requests
    app.dependency_overrides[get_redis] = lambda: fake_redis_instance
    app.dependency_overrides[get_aws_job_service] = lambda: FakeAWSJobService()
    app.dependency_overrides[get_enhanced_video_service] = lambda: FakeEnhancedVideoService()
    app.dependency_overrides[get_video_service] = lambda: fake_video_service_instance
    app.dependency_overrides[get_aws_file_service] = lambda: FakeAWSS3FileService()

    # Bypass Clerk user info by returning a fixed user when dependency is used
    async def _fake_current_user(authorization: Optional[str] = None):
        # Allow token-derived user id to test authorization scenarios
        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        user_id = token or "user_test_1"
        return {
            "user_info": {
                "id": user_id,
                "email": f"{user_id}@example.com",
                "email_verified": True,
                "username": user_id,
            }
        }

    app.dependency_overrides[dep_get_current_user] = _fake_current_user

    with TestClient(app) as client:
        # Expose fakes for tests that want to seed state
        client.app.state.test_fake_redis = fake_redis_instance
        client.app.state.test_fake_video_service = fake_video_service_instance
        yield client
