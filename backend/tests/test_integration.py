from sqlalchemy import func, select

from app.models import Customer, EmissionFactor, Shipment, User
from scripts import seed_db


def test_create_shipment_automatically_calculates_carbon(client, auth_headers, sample_customer, driver_user):
    response = client.post(
        "/api/v1/shipments",
        json={
            "customer_id": str(sample_customer.id),
            "driver_id": str(driver_user.id),
            "customer_name": sample_customer.name,
            "origin": "Manisa",
            "destination": "Ankara",
            "cargo_type": "Tekstil",
            "tonnage": 10,
            "weight_kg": 10000,
            "delivery_date": "2026-05-25",
        },
        headers=auth_headers("manager"),
    )
    assert response.status_code == 201
    shipment = response.json()
    assert shipment["distance_km"] > 0
    assert shipment["vehicle_type"]
    assert shipment["co2_kg"] > 0

    response = client.get(f"/api/v1/carbon/shipment/{shipment['id']}", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert response.json()["carbon_emission"] == shipment["co2_kg"]


def test_soft_deleted_customer_no_longer_visible_but_shipments_remain(client, auth_headers, sample_customer, sample_shipments):
    response = client.delete(f"/api/v1/customers/{sample_customer.id}", headers=auth_headers("manager"))
    assert response.status_code == 204

    response = client.get(f"/api/v1/customers/{sample_customer.id}", headers=auth_headers("viewer"))
    assert response.status_code == 404

    response = client.get(f"/api/v1/shipments/customer/{sample_customer.id}", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_seed_script_populates_expected_database_state(db_session):
    seed_db.seed_admin_user(db_session)
    seed_db.seed_emission_factors(db_session)
    seed_db.seed_customers(db_session)
    db_session.commit()

    assert db_session.scalar(select(func.count()).select_from(User).where(User.username == seed_db.ADMIN_USERNAME)) == 1
    assert db_session.scalar(select(func.count()).select_from(Customer).where(Customer.email.in_([row["email"] for row in seed_db.SAMPLE_CUSTOMERS]))) == 4
    assert db_session.scalar(select(func.count()).select_from(EmissionFactor)) == 5
    assert db_session.scalar(select(func.count()).select_from(Shipment)) == 2
