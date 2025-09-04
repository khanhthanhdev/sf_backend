def auth_header(token: str = "testtoken"):
    return {"Authorization": f"Bearer {token}"}


def test_list_jobs_empty_ok(api_client):
    r = api_client.get("/api/v1/jobs", headers=auth_header())
    assert r.status_code == 200
    data = r.json()
    assert data.get("jobs") == []
    assert data.get("total_count") == 0


def test_list_jobs_validation_items_per_page(api_client):
    r = api_client.get("/api/v1/jobs?items_per_page=1000", headers=auth_header())
    # Dependency enforces max 100 -> should 400
    assert r.status_code == 400


def test_get_job_details_ok(api_client):
    r = api_client.get("/api/v1/jobs/job-abc", headers=auth_header())
    # Fake service returns a job
    assert r.status_code == 200
    body = r.json()
    assert body.get("job_id") == "job-abc"

