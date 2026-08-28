from backend.app import create_app
from fastapi.testclient import TestClient
from backend.database.session import init_db


def test_news_video_routes_are_registered():
    app = create_app()
    # ``create_app`` includes a few nested routers; the public OpenAPI map is
    # the stable way to inspect their expanded paths.
    paths = set(app.openapi()["paths"])
    assert "/news-video/projects" in paths
    assert "/news-video/projects/{project_id}/speech-audit" in paths
    assert "/news-video/projects/{project_id}/render/jobs" in paths


def test_news_project_rejects_unsafe_source_scheme():
    init_db()
    client = TestClient(create_app())
    response = client.post("/news-video/projects", json={"topic": "Tin test", "source_note": "javascript:alert(1)"})
    assert response.status_code == 422
