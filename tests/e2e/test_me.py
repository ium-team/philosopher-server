from fastapi.testclient import TestClient

from app.api.v1.dependencies.auth import get_current_user_claims
from app.main import app

client = TestClient(app)


def test_me_requires_bearer_token() -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Authorization bearer token is required"}


def test_me_returns_claims_from_dependency_override() -> None:
    app.dependency_overrides[get_current_user_claims] = lambda: {
        "sub": "test-user-id",
        "email": "tester@example.com",
        "role": "authenticated",
    }
    try:
        response = client.get("/api/v1/me")
        assert response.status_code == 200
        assert response.json() == {
            "id": "test-user-id",
            "email": "tester@example.com",
            "role": "authenticated",
        }
    finally:
        app.dependency_overrides.clear()
