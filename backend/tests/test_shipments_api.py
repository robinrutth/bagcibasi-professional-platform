from datetime import date

from app.models import Shipment, Vehicle


def _payload(customer, driver=None, **overrides):
    data = {
        "customer_id": str(customer.id),
        "driver_id": str(driver.id) if driver else None,
        "customer_name": customer.name,
        "origin": "Manisa",
        "destination": "Ankara",
        "cargo_type": "Tekstil",
        "tonnage": 8,
        "weight_kg": 8000,
        "delivery_date": "2026-05-21",
        "status": "Hazirlaniyor",
    }
    data.update(overrides)
    return data


def test_shipment_crud_full_coverage(client, auth_headers, sample_customer, driver_user):
    response = client.post(
        "/api/v1/shipments",
        json=_payload(sample_customer, driver_user),
        headers=auth_headers("manager"),
    )
    assert response.status_code == 201
    created = response.json()
    assert created["customer_id"] == str(sample_customer.id)
    assert created["driver_id"] == str(driver_user.id)
    assert created["co2_kg"] > 0

    response = client.get(f"/api/v1/shipments/{created['id']}", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]

    response = client.put(
        f"/api/v1/shipments/{created['id']}",
        json={"status": "Teslim Edildi", "tonnage": 9},
        headers=auth_headers("admin"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Teslim Edildi"
    assert response.json()["tonnage"] == 9

    response = client.delete(f"/api/v1/shipments/{created['id']}", headers=auth_headers("viewer"))
    assert response.status_code == 403

    response = client.delete(f"/api/v1/shipments/{created['id']}", headers=auth_headers("admin"))
    assert response.status_code == 204

    response = client.get(f"/api/v1/shipments/{created['id']}", headers=auth_headers("admin"))
    assert response.status_code == 404


def test_driver_only_sees_and_updates_own_shipments(client, auth_headers, sample_shipments):
    response = client.get("/api/v1/shipments", headers=auth_headers("driver"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert {item["id"] for item in payload["items"]} == {str(sample_shipments[0].id), str(sample_shipments[1].id)}

    response = client.get(f"/api/v1/shipments/{sample_shipments[2].id}", headers=auth_headers("driver"))
    assert response.status_code == 403

    response = client.put(
        f"/api/v1/shipments/{sample_shipments[0].id}",
        json={"status": "Teslim Edildi"},
        headers=auth_headers("driver"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Teslim Edildi"

    response = client.put(
        f"/api/v1/shipments/{sample_shipments[0].id}",
        json={"destination": "Bursa"},
        headers=auth_headers("driver"),
    )
    assert response.status_code == 403


def test_pagination_and_filters(client, auth_headers, sample_shipments, sample_customer):
    response = client.get("/api/v1/shipments?skip=0&limit=2", headers=auth_headers("admin"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 5
    assert payload["skip"] == 0
    assert payload["limit"] == 2
    assert len(payload["items"]) == 2

    response = client.get("/api/v1/shipments?status=Planlandi", headers=auth_headers("manager"))
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == str(sample_shipments[2].id)

    response = client.get(f"/api/v1/shipments/customer/{sample_customer.id}", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_create_requires_manager_role(client, auth_headers, sample_customer, driver_user):
    response = client.post(
        "/api/v1/shipments",
        json=_payload(sample_customer, driver_user),
        headers=auth_headers("viewer"),
    )
    assert response.status_code == 403


def _vehicle_payload(**overrides):
    payload = {
        "plate_number": "45 TEST 001",
        "vehicle_type": "Kamyon",
        "capacity_tons": 22,
        "current_load_tons": 0,
        "driver_name": "Test Sürücü",
        "driver_phone": "+90 555 111 22 33",
        "status": "Bosta",
        "current_lat": 39.0,
        "current_lng": 35.0,
        "notes": "pytest",
    }
    payload.update(overrides)
    return payload


def test_vehicle_crud_and_workflow_rules(client, auth_headers):
    response = client.post("/api/v1/vehicles", json=_vehicle_payload(), headers=auth_headers("manager"))
    assert response.status_code == 201
    vehicle = response.json()
    assert vehicle["plate_number"] == "45 TEST 001"
    assert vehicle["status"] == "Bosta"

    response = client.get("/api/v1/vehicles?status=Bosta", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert any(item["id"] == vehicle["id"] for item in response.json()["items"])

    response = client.put(f"/api/v1/vehicles/{vehicle['id']}/status", json={"status": "Yolda"}, headers=auth_headers("admin"))
    assert response.status_code == 400

    response = client.put(f"/api/v1/vehicles/{vehicle['id']}/status", json={"status": "Yukleniyor"}, headers=auth_headers("admin"))
    assert response.status_code == 200
    assert response.json()["status"] == "Yukleniyor"

    response = client.put(f"/api/v1/vehicles/{vehicle['id']}", json={"driver_phone": "+90 555 999 88 77"}, headers=auth_headers("manager"))
    assert response.status_code == 200
    assert response.json()["driver_phone"].endswith("77")

    response = client.delete(f"/api/v1/vehicles/{vehicle['id']}", headers=auth_headers("admin"))
    assert response.status_code == 204


def test_vehicle_assignment_capacity_and_double_assign_block(client, auth_headers, db_session, sample_customer):
    vehicle = Vehicle(
        plate_number="45 TEST 002",
        vehicle_type="Kamyon",
        capacity_tons=10,
        current_load_tons=0,
        driver_name="Race Driver",
        status="Bosta",
        current_lat=39,
        current_lng=35,
    )
    shipments = [
        Shipment(
            customer_id=sample_customer.id,
            customer_name=sample_customer.name,
            origin="Manisa",
            destination="Ankara",
            cargo_type="Tekstil",
            tonnage=6,
            weight_kg=6000,
            delivery_date=date(2026, 5, 23),
            distance_km=100,
            vehicle_type="Kamyon",
            status="Hazirlaniyor",
            cost_amount=100,
            invoice_amount=130,
            profit_amount=30,
            profit_margin=0.23,
            co2_kg=10,
            risk_level="Dusuk",
            ai_recommendation="ok",
        ),
        Shipment(
            customer_id=sample_customer.id,
            customer_name=sample_customer.name,
            origin="Manisa",
            destination="Izmir",
            cargo_type="Tekstil",
            tonnage=6,
            weight_kg=6000,
            delivery_date=date(2026, 5, 23),
            distance_km=80,
            vehicle_type="Kamyon",
            status="Hazirlaniyor",
            cost_amount=100,
            invoice_amount=130,
            profit_amount=30,
            profit_margin=0.23,
            co2_kg=10,
            risk_level="Dusuk",
            ai_recommendation="ok",
        ),
    ]
    db_session.add(vehicle)
    db_session.add_all(shipments)
    db_session.commit()
    db_session.refresh(vehicle)
    for shipment in shipments:
        db_session.refresh(shipment)

    response = client.post(
        f"/api/v1/vehicles/{vehicle.id}/assign",
        json={"shipment_id": str(shipments[0].id), "load_tons": 11},
        headers=auth_headers("manager"),
    )
    assert response.status_code == 400

    response = client.post(
        f"/api/v1/vehicles/{vehicle.id}/assign",
        json={"shipment_id": str(shipments[0].id), "load_tons": 6},
        headers=auth_headers("manager"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Yukleniyor"

    response = client.post(
        f"/api/v1/vehicles/{vehicle.id}/assign",
        json={"shipment_id": str(shipments[1].id), "load_tons": 6},
        headers=auth_headers("manager"),
    )
    assert response.status_code == 400
