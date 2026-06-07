from app.models import User


def test_login_success_and_failure(client, users: dict[str, User]):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["user"]["role"] == "admin"

    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_token_refresh_rotates_refresh_token(client, users: dict[str, User]):
    login = client.post("/api/auth/login", json={"username": "manager", "password": "secret"}).json()

    response = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 200
    refreshed = response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"] != login["refresh_token"]
    assert refreshed["user"]["role"] == "manager"

    response = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 401


def test_logout_revokes_access_and_refresh_tokens(client, users: dict[str, User]):
    login = client.post("/api/auth/login", json={"username": "viewer", "password": "secret"}).json()

    response = client.post(
        "/api/auth/logout",
        json={"access_token": login["access_token"], "refresh_token": login["refresh_token"]},
    )
    assert response.status_code == 200

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login['access_token']}"})
    assert response.status_code == 401

    response = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 401


def test_invalid_token_cannot_access_protected_endpoint(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-valid-token"})
    assert response.status_code == 401


def test_role_based_access_control(client, users: dict[str, User], auth_headers):
    response = client.get("/api/users", headers=auth_headers("admin"))
    assert response.status_code == 200

    response = client.get("/api/users", headers=auth_headers("manager"))
    assert response.status_code == 403

    response = client.get("/api/v1/customers", headers=auth_headers("driver"))
    assert response.status_code == 403
