# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.crud.customer import get_customer, get_customer_carbon_stats
from app.crud.shipment import get_shipment
from app.database import get_db
from app.models import Customer, Shipment, User
from app.services.email_service import send_invoice_email
from app.services.pdf_service import generate_carbon_report_pdf, generate_shipment_invoice

router = APIRouter(prefix="/documents", tags=["documents"])

INVOICE_ROLES = {"admin", "manager", "operation", "viewer"}
REPORT_ROLES = {"admin", "manager", "viewer"}


def _customer_matches_user(customer: Customer | None, user: User) -> bool:
    if not customer:
        return False
    username = (user.username or "").strip().lower()
    return username in {(customer.email or "").strip().lower(), str(customer.id).lower()}


def _ensure_invoice_access(shipment: Shipment, customer: Customer | None, user: User) -> None:
    if user.role in INVOICE_ROLES:
        return
    if user.role == "driver" and shipment.driver_id == user.id:
        return
    if _customer_matches_user(customer, user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu faturayi goruntuleme yetkiniz yok")


def _ensure_report_access(customer: Customer, user: User) -> None:
    if user.role in REPORT_ROLES or _customer_matches_user(customer, user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu karbon raporunu goruntuleme yetkiniz yok")


def _pdf_response(pdf_bytes: bytes, filename: str) -> StreamingResponse:
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


def _period_filters(period: Literal["monthly", "yearly"]) -> tuple[date, date]:
    today = date.today()
    if period == "yearly":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    return date(today.year, today.month, 1), today


def _customer_summary_for_period(db: Session, customer_id: UUID, period: Literal["monthly", "yearly"]) -> dict:
    start_date, end_date = _period_filters(period)
    shipments = list(
        db.scalars(
            select(Shipment).where(
                Shipment.customer_id == customer_id,
                Shipment.is_deleted.is_(False),
                Shipment.delivery_date >= start_date,
                Shipment.delivery_date <= end_date,
            )
        ).all()
    )
    if not shipments:
        summary = get_customer_carbon_stats(db, customer_id) or {
            "total_co2_kg": 0,
            "shipment_count": 0,
            "average_co2_kg": 0,
            "by_vehicle": [],
            "top_routes": [],
        }
    else:
        from app.services.carbon_service import get_top_routes_from_shipments, get_vehicle_distribution_from_shipments

        total = round(sum(row.co2_kg for row in shipments), 2)
        summary = {
            "total_co2_kg": total,
            "shipment_count": len(shipments),
            "average_co2_kg": round(total / len(shipments), 2),
            "by_vehicle": get_vehicle_distribution_from_shipments(shipments),
            "top_routes": get_top_routes_from_shipments(shipments),
        }
    summary["benchmark_note"] = "Sektor ortalamasi 0.35 kg CO2/km varsayimi ile karsilastirilir."
    return summary


@router.get("/invoice/{shipment_id}")
def download_invoice(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    shipment = get_shipment(db, shipment_id)
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sevkiyat bulunamadi")
    customer = db.get(Customer, shipment.customer_id) if shipment.customer_id else None
    _ensure_invoice_access(shipment, customer, current_user)
    try:
        pdf_bytes = generate_shipment_invoice(shipment, customer)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Fatura PDF olusturulamadi") from exc
    return _pdf_response(pdf_bytes, f"invoice-{shipment.id}.pdf")


@router.get("/carbon-report/{customer_id}")
def download_carbon_report(
    customer_id: UUID,
    period: Literal["monthly", "yearly"] = Query("monthly"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    customer = get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")
    _ensure_report_access(customer, current_user)
    summary = _customer_summary_for_period(db, customer_id, period)
    try:
        pdf_bytes = generate_carbon_report_pdf(customer, summary, period)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Karbon raporu PDF olusturulamadi") from exc
    return _pdf_response(pdf_bytes, f"carbon-report-{customer.id}-{period}.pdf")


@router.post("/invoice/{shipment_id}/email")
async def email_invoice(
    shipment_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    shipment = get_shipment(db, shipment_id)
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sevkiyat bulunamadi")
    customer = db.get(Customer, shipment.customer_id) if shipment.customer_id else None
    if not customer or not customer.email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Musterinin e-posta adresi bulunamadi")
    _ensure_invoice_access(shipment, customer, current_user)
    try:
        pdf_bytes = generate_shipment_invoice(shipment, customer)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Fatura PDF olusturulamadi") from exc
    background_tasks.add_task(send_invoice_email, customer, pdf_bytes)
    return {"status": "queued", "message": "Fatura e-posta gonderimi kuyruğa alindi"}
