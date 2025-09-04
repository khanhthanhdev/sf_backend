def auth_header(token: str = "testtoken"):
    return {"Authorization": f"Bearer {token}"}


def test_upload_requires_auth(api_client):
    r = api_client.post("/api/v1/files/upload")
    assert r.status_code == 401


def test_upload_validation_missing_file(api_client):
    # Even with auth, missing file should be 422 from FastAPI validation
    r = api_client.post("/api/v1/files/upload", headers=auth_header())
    assert r.status_code == 422

