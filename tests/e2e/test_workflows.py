import os
import json
import asyncio
from pathlib import Path

from typing import Dict, Any

from src.app.core.redis import RedisKeyManager, redis_json_set
from src.app.models.job import JobStatus, JobConfiguration
from src.app.models.video import VideoMetadata, VideoStatus


def auth_header(token: str = "user_e2e_1"):
    return {"Authorization": f"Bearer {token}"}


def _make_dirs(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _seed_completed_job_state(client, job_id: str, user_id: str, video_dir: Path) -> Dict[str, Any]:
    """Seed fake services and redis with a completed job and a video file on disk."""
    # Create a tiny fake mp4 and thumbnail files
    video_path = video_dir / "video.mp4"
    thumbs_dir = video_dir / "thumbnails"
    _make_dirs(thumbs_dir)
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42\x00\x00\x00\x08free\x00\x00\x00\x08mdat")
    (thumbs_dir / "video_thumb_small.jpg").write_bytes(b"JPEGSMALL")
    (thumbs_dir / "video_thumb_medium.jpg").write_bytes(b"JPEGMED")
    (thumbs_dir / "video_thumb_large.jpg").write_bytes(b"JPEGLARGE")

    # Seed FakeVideoService job store
    video_service = client.app.state.test_fake_video_service
    job_dict = {
        "id": job_id,
        "user_id": user_id,
        "status": JobStatus.COMPLETED.value,
        "configuration": JobConfiguration(
            topic="E2E Demo",
            context="End-to-end path",
            quality="medium",
            use_rag=False,
            enable_subtitles=True,
            enable_thumbnails=True,
            output_format="mp4",
        ).model_dump(),
        "result_url": f"/api/v1/videos/jobs/{job_id}/stream",
    }
    video_service.set_job(job_id, job_dict)

    # Seed Redis job + video metadata used by download/stream/thumbnail
    redis_client = client.app.state.test_fake_redis
    job_key = RedisKeyManager.job_key(job_id)
    video_key = RedisKeyManager.video_key(f"job_{job_id}")

    video_metadata = VideoMetadata(
        job_id=job_id,
        user_id=user_id,
        filename="video.mp4",
        file_path=str(video_path),
        file_size=video_path.stat().st_size,
        duration_seconds=1.0,
        width=1920,
        height=1080,
        format="mp4",
        status=VideoStatus.READY,
    ).model_dump()

    asyncio.run(redis_json_set(redis_client, job_key, job_dict))
    asyncio.run(redis_json_set(redis_client, video_key, video_metadata))

    return {"video_path": video_path, "thumbs_dir": thumbs_dir}


def test_e2e_generate_process_and_retrieve(api_client, tmp_path):
    # 1) Create a job
    body = {
        "configuration": {
            "topic": "E2E Demo",
            "context": "End-to-end path",
            "quality": "medium",
            "use_rag": False,
            "enable_subtitles": True,
            "enable_thumbnails": True,
            "output_format": "mp4",
        },
        "priority": "normal",
    }
    r = api_client.post("/api/v1/videos/generate", json=body, headers=auth_header("user_e2e_1"))
    assert r.status_code == 201
    job_id = r.json()["job_id"]

    # 2) Simulate processing to completion and seed backing stores
    paths = _seed_completed_job_state(api_client, job_id, user_id="user_e2e_1", video_dir=tmp_path / job_id)

    # 3) Get metadata (VideoService path)
    r_meta = api_client.get(f"/api/v1/videos/jobs/{job_id}/metadata", headers=auth_header("user_e2e_1"))
    assert r_meta.status_code == 200
    meta = r_meta.json()
    assert meta["video"]["status"] == "ready"
    assert meta["streaming_url"].endswith(f"/api/v1/videos/jobs/{job_id}/stream")

    # 4) Stream the video (Redis-backed path)
    r_stream = api_client.get(f"/api/v1/videos/jobs/{job_id}/stream", headers=auth_header("user_e2e_1"))
    assert r_stream.status_code == 200
    assert r_stream.headers.get("Content-Disposition", "").startswith("inline")

    # 5) Download the video as attachment
    r_dl = api_client.get(f"/api/v1/videos/jobs/{job_id}/download?inline=false", headers=auth_header("user_e2e_1"))
    assert r_dl.status_code == 200
    assert r_dl.headers.get("Content-Disposition", "").startswith("attachment")

    # 6) Retrieve a thumbnail
    r_thumb = api_client.get(f"/api/v1/videos/jobs/{job_id}/thumbnail?size=medium", headers=auth_header("user_e2e_1"))
    assert r_thumb.status_code == 200
    # Content-Disposition for thumbnail is inline
    assert r_thumb.headers.get("Content-Disposition", "").startswith("inline")


def test_e2e_auth_and_authorization_enforced(api_client, tmp_path):
    # Without auth, generation requires 401
    r_unauth = api_client.post("/api/v1/videos/generate", json={})
    assert r_unauth.status_code in (401, 422)  # may fail validation first, but endpoint requires auth

    # Create a completed job for user A
    job_id = "job_authz_1"
    _seed_completed_job_state(api_client, job_id, user_id="userA", video_dir=tmp_path / job_id)

    # User B cannot access user A's job resources
    for path in [
        f"/api/v1/videos/jobs/{job_id}/metadata",
        f"/api/v1/videos/jobs/{job_id}/stream",
        f"/api/v1/videos/jobs/{job_id}/download",
        f"/api/v1/videos/jobs/{job_id}/thumbnail",
    ]:
        resp = api_client.get(path, headers=auth_header("userB"))
        # Stream/download/thumbnail endpoints use 403 for ownership, metadata also 403
        assert resp.status_code == 403


def test_e2e_error_handling_scenarios(api_client, tmp_path):
    # Seed a processing (not completed) job
    job_id = "job_err_1"
    user_id = "user_e2e_2"
    # Prepare files but leave job status as processing
    video_dir = tmp_path / job_id
    _make_dirs(video_dir / "thumbnails")
    (video_dir / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")

    # Seed job as processing in both stores
    video_service = api_client.app.state.test_fake_video_service
    job_dict = {
        "id": job_id,
        "user_id": user_id,
        "status": JobStatus.PROCESSING.value,
        "configuration": JobConfiguration(
            topic="E2E Error",
            context="ctx",
            quality="medium",
        ).model_dump(),
        "result_url": None,
    }
    video_service.set_job(job_id, job_dict)

    redis_client = api_client.app.state.test_fake_redis
    job_key = RedisKeyManager.job_key(job_id)
    asyncio.run(redis_json_set(redis_client, job_key, job_dict))

    # Streaming and metadata should report 409 conflict (not completed)
    r_meta = api_client.get(f"/api/v1/videos/jobs/{job_id}/metadata", headers=auth_header(user_id))
    assert r_meta.status_code == 409
    r_stream = api_client.get(f"/api/v1/videos/jobs/{job_id}/stream", headers=auth_header(user_id))
    assert r_stream.status_code == 409

    # Now mark as completed but remove file to force 404 on download/stream
    job_dict_completed = {**job_dict, "status": JobStatus.COMPLETED.value}
    video_service.set_job(job_id, job_dict_completed)
    asyncio.run(redis_json_set(redis_client, job_key, job_dict_completed))
    # Do not seed video metadata to simulate missing file metadata
    resp_dl = api_client.get(f"/api/v1/videos/jobs/{job_id}/download", headers=auth_header(user_id))
    assert resp_dl.status_code == 404
    resp_stream = api_client.get(f"/api/v1/videos/jobs/{job_id}/stream", headers=auth_header(user_id))
    assert resp_stream.status_code == 404

