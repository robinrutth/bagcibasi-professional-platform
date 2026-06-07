from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Customer, Shipment, User


def _client_with_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    admin = User(username="customer-admin", full_name="Admin", role="admin", password_hash=hash_password("x"), is_active=True)
    manager = User(username="customer-manager", full_name="Manager", role="manager", password_hash=hash_password("x"), is_active=True)
    viewer = User(username="customer-viewer", full_name="Viewer", role="viewer", password_hash=hash_password("x"), is_active=True)
    driver = User(username="customer-driver", full_name="Driver", role="driver", password_hash=hash_password("x"), is_active=True)
    customer = Customer(
        name="Api Customer",
        email="api.customer@example.com",
        phone="+90 555 000 00 00",
        city="Manisa",
        tax_number="5550001111",
        sector="Test",
    )
    session.add_all([admin, manager, viewer, driver, customer])
    session.commit()
    for row in [admin, manager, viewer, driver, customer]:
        session.refresh(row)

    shipment = Shipment(
        customer_id=customer.id,
        customer_name=customer.name,
        origin="Manisa",
        destination="Ankara",
        cargo_type="Tekstil",
        tonnage=10,
        weight_kg=10000,
        delivery_date=date(2026, 5, 20),
        distance_km=500,
        vehicle_type="truck",
        status="Yolda",
        cost_amount=10000,
        invoice_amount=12000,
        profit_amount=2000,
        profit_margin=0.1667,
        co2_kg=250,
        risk_level="Dusuk",
        ai_recommendation="ok",
    )
    session.add(shipment)
    session.commit()
    session.refresh(shipment)

    def override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    tokens = {
        "admin": create_access_token(admin),
        "manager": create_access_token(manager),
        "viewer": create_access_token(viewer),
        "driver": create_access_token(driver),
    }
    return client, session, tokens, customer


def _auth(tokens, role):
    return {"Authorization": f"Bearer {tokens[role]}"}


def test_customer_endpoints_crud_permissions_shipments_and_carbon_stats():
    client, session, tokens, customer = _client_with_db()
    try:
        response = client.get("/api/v1/customers", headers=_auth(tokens, "viewer"))
        assert response.status_code == 200
        assert response.json()["total"] == 1

        response = client.get(f"/api/v1/customers/{customer.id}", headers=_auth(tokens, "viewer"))
        assert response.status_code == 200
        assert response.json()["email"] == "api.customer@example.com"

        response = client.get(f"/api/v1/customers/{customer.id}/shipments", headers=_auth(tokens, "viewer"))
        assert response.status_code == 200
        assert len(response.json()["shipments"]) == 1

        response = client.get(f"/api/v1/customers/{customer.id}/carbon-stats", headers=_auth(tokens, "viewer"))
        assert response.status_code == 200
        assert response.json()["total_co2_kg"] == 250
        assert response.json()["shipment_count"] == 1

        payload = {
            "name": "Created Customer",
            "email": "created.customer@example.com",
            "phone": "+90 555 111 22 33",
            "address": "Organize Sanayi",
            "city": "Izmir",
            "tax_number": "1231231231",
        }
        response = client.post("/api/v1/customers", json=payload, headers=_auth(tokens, "viewer"))
        assert response.status_code == 403

        response = client.post("/api/v1/customers", json=payload, headers=_auth(tokens, "manager"))
        assert response.status_code == 201
        created_id = response.json()["id"]

        response = client.post("/api/v1/customers", json=payload, headers=_auth(tokens, "admin"))
        assert response.status_code == 409

        response = client.put(
            f"/api/v1/customers/{created_id}",
            json={"city": "Istanbul", "risk_level": "Orta"},
            headers=_auth(tokens, "admin"),
        )
        assert response.status_code == 200
        assert response.json()["city"] == "Istanbul"

        response = client.get("/api/v1/customers?search=Created&city=Istanbul", headers=_auth(tokens, "viewer"))
        assert response.status_code == 200
        assert response.json()["total"] == 1

        response = client.delete(f"/api/v1/customers/{created_id}", headers=_auth(tokens, "viewer"))
        assert response.status_code == 403

        response = client.delete(f"/api/v1/customers/{created_id}", headers=_auth(tokens, "manager"))
        assert response.status_code == 204

        response = client.get(f"/api/v1/customers/{created_id}", headers=_auth(tokens, "viewer"))
        assert response.status_code == 404

        response = client.get("/api/v1/customers", headers=_auth(tokens, "driver"))
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        session.close()
