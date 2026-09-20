from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_cors_preflight_allows_web_origin() -> None:
    response = client.options(
        "/api/me",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_does_not_allow_unknown_origin() -> None:
    response = client.options(
        "/api/me",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers
