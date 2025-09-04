def auth_header(token: str = "testtoken"):
    return {"Authorization": f"Bearer {token}"}


def test_generate_video_creates_job(api_client):
    body = {
        "configuration": {
            "topic": "Test Topic",
            "context": "Explain something",
            "quality": "medium",
            "use_rag": False,
            "enable_subtitles": True,
            "enable_thumbnails": True,
            "output_format": "mp4"
        },
        "priority": "normal"
    }
    r = api_client.post("/api/v1/videos/generate", json=body, headers=auth_header())
    assert r.status_code == 201
    data = r.json()
    assert data.get("job_id")
    assert data.get("status")


def test_generate_video_validation_error(api_client):
    # Missing topic -> should 422
    body = {
        "configuration": {
            # "topic": "Missing",
            "context": "Explain something",
            "quality": "medium"
        },
        "priority": "normal"
    }
    r = api_client.post("/api/v1/videos/generate", json=body, headers=auth_header())
    assert r.status_code == 422

