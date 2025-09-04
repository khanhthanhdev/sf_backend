def test_openapi_schema_includes_videos_generate(api_client):
    r = api_client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "/api/v1/videos/generate" in schema.get("paths", {})
    # Response 201 should be present
    responses = schema["paths"]["/api/v1/videos/generate"]["post"]["responses"]
    assert "201" in responses


def test_swagger_ui_accessible(api_client):
    r = api_client.get("/docs")
    assert r.status_code == 200
    assert "Swagger UI" in r.text or "swagger-ui" in r.text.lower()

