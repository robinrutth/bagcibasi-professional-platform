from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

from app.services import email_service


def _shipment(**overrides):
    data = {
        "id": "SHP-1",
        "origin": "Manisa",
        "destination": "Ankara",
        "delivery_date": date(2026, 5, 21),
        "status": "Yolda",
        "vehicle_type": "truck",
        "co2_kg": 42.5,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_send_email_uses_smtp(monkeypatch):
    sent = {}

    async def fake_send(message, **kwargs):
        sent["to"] = message["To"]
        sent["subject"] = message["Subject"]
        sent["kwargs"] = kwargs

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            mail_server="smtp.example.com",
            mail_port=587,
            mail_username="user",
            mail_password="pass",
            mail_from="noreply@example.com",
            mail_tls=True,
            mail_ssl=False,
        ),
    )
    monkeypatch.setattr(email_service.aiosmtplib, "send", fake_send)

    result = asyncio.run(email_service.send_email("to@example.com", "Subject", "<p>Hello</p>"))

    assert result is True
    assert sent["to"] == "to@example.com"
    assert sent["subject"] == "Subject"
    assert sent["kwargs"]["hostname"] == "smtp.example.com"


def test_template_render_contains_brand_route_and_carbon():
    html = email_service.render_email_template(
        "shipment_created.html",
        {
            "customer": SimpleNamespace(name="Api Customer"),
            "shipment": _shipment(),
            "route": "Manisa - Ankara",
        },
    )

    assert "#16a34a" in html
    assert "Api Customer" in html
    assert "Manisa - Ankara" in html
    assert "42.50 kg CO2" in html


def test_shipment_creation_queues_email(client, auth_headers, sample_customer, driver_user, monkeypatch):
    calls = []

    async def fake_created(shipment, customer):
        calls.append((str(shipment.id), customer.email))
        return True

    monkeypatch.setattr(email_service, "send_shipment_created", fake_created)

    response = client.post(
        "/api/v1/shipments",
        json={
            "customer_id": str(sample_customer.id),
            "driver_id": str(driver_user.id),
            "customer_name": sample_customer.name,
            "origin": "Manisa",
            "destination": "Ankara",
            "cargo_type": "Tekstil",
            "tonnage": 8,
            "weight_kg": 8000,
            "delivery_date": "2026-05-21",
            "status": "Hazirlaniyor",
        },
        headers=auth_headers("manager"),
    )

    assert response.status_code == 201
    assert calls == [(response.json()["id"], sample_customer.email)]


def test_email_failure_does_not_block_shipment_creation(client, auth_headers, sample_customer, driver_user, monkeypatch):
    async def failing_send(*args, **kwargs):
        raise OSError("smtp unavailable")

    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            mail_server="smtp.example.com",
            mail_port=587,
            mail_username="user",
            mail_password="pass",
            mail_from="noreply@example.com",
            mail_tls=True,
            mail_ssl=False,
            platform_name="Bagcibasi Logistics AI",
            frontend_url="http://localhost:3000",
        ),
    )
    monkeypatch.setattr(email_service.aiosmtplib, "send", failing_send)

    response = client.post(
        "/api/v1/shipments",
        json={
            "customer_id": str(sample_customer.id),
            "driver_id": str(driver_user.id),
            "customer_name": sample_customer.name,
            "origin": "Manisa",
            "destination": "Ankara",
            "cargo_type": "Tekstil",
            "tonnage": 8,
            "weight_kg": 8000,
            "delivery_date": "2026-05-21",
            "status": "Hazirlaniyor",
        },
        headers=auth_headers("manager"),
    )

    assert response.status_code == 201
    assert response.json()["id"]
