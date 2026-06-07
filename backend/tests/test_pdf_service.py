from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.services import email_service
from app.services.pdf_service import generate_carbon_report_pdf, generate_shipment_invoice, render_pdf_template


def test_generate_shipment_invoice_returns_pdf(sample_shipments, sample_customer):
    pdf = generate_shipment_invoice(sample_shipments[0], sample_customer)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_invoice_template_contains_expected_content(sample_shipments, sample_customer):
    html = render_pdf_template(
        "invoice.html",
        {
            "shipment": sample_shipments[0],
            "customer": sample_customer,
            "invoice_no": "INV-TEST-20260520",
            "issued_at": sample_shipments[0].created_at,
            "subtotal": 12000,
            "tax_amount": 0,
            "total_amount": 12000,
        },
    )

    assert "INV-TEST-20260520" in html
    assert "Api Customer" in html
    assert "Manisa" in html
    assert "#16a34a" in html
    assert "kg CO2" in html


def test_generate_carbon_report_returns_pdf(sample_customer):
    summary = {
        "total_co2_kg": 54,
        "shipment_count": 2,
        "average_co2_kg": 27,
        "by_vehicle": [{"vehicle_type": "truck", "co2": 54}],
        "top_routes": [{"origin": "Manisa", "destination": "Ankara", "vehicle_type": "truck", "co2": 54, "shipment_count": 2}],
        "benchmark_note": "Sektor ortalamasi",
    }

    pdf = generate_carbon_report_pdf(sample_customer, summary, "monthly")

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_invoice_endpoint_streams_pdf(client, auth_headers, sample_shipments):
    response = client.get(f"/api/v1/documents/invoice/{sample_shipments[0].id}", headers=auth_headers("manager"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "attachment" in response.headers["content-disposition"]


def test_carbon_report_endpoint_streams_pdf(client, auth_headers, sample_customer):
    response = client.get(
        f"/api/v1/documents/carbon-report/{sample_customer.id}?period=monthly",
        headers=auth_headers("viewer"),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_invoice_email_endpoint_queues_attachment(client, auth_headers, sample_shipments, monkeypatch):
    calls = []

    async def fake_send_invoice(customer, pdf_bytes):
        calls.append((customer.email, pdf_bytes[:4]))
        return True

    monkeypatch.setattr("app.routers.documents.send_invoice_email", fake_send_invoice)

    response = client.post(f"/api/v1/documents/invoice/{sample_shipments[0].id}/email", headers=auth_headers("manager"))

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert calls == [("api.customer@example.com", b"%PDF")]


def test_send_invoice_email_attaches_pdf(monkeypatch):
    sent = {}

    async def fake_send(message, **kwargs):
        sent["message"] = message
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
            platform_name="Bagcibasi Lojistik AI",
            frontend_url="http://localhost:3000",
        ),
    )
    monkeypatch.setattr(email_service.aiosmtplib, "send", fake_send)

    result = asyncio.run(email_service.send_invoice_email(SimpleNamespace(name="Api Customer", email="to@example.com"), b"%PDF-1.4"))

    assert result is True
    assert sent["message"]["To"] == "to@example.com"
    assert sent["message"]["Subject"] == "PDF Faturanız"
    attachments = [part for part in sent["message"].walk() if part.get_content_disposition() == "attachment"]
    assert attachments[0].get_filename() == "fatura.pdf"
