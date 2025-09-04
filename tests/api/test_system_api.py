def test_root_health_endpoints(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "healthy"

    r2 = api_client.get("/health/detailed")
    assert r2.status_code == 200


def test_system_health(api_client):
    r = api_client.get("/api/v1/system/health")
    # Should return 200 with health structure, even if underlying components are fake
    assert r.status_code == 200
    payload = r.json()
    assert "components" in payload
    assert "status" in payload


def test_system_metrics(api_client):
    r = api_client.get("/api/v1/system/metrics")
    assert r.status_code == 200
    data = r.json()
    # Basic keys presence
    assert "system_resources" in data
    assert "redis_metrics" in data
    assert "job_metrics" in data

