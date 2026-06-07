# -*- coding: utf-8 -*-
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.crud.customer import get_customer, get_customer_carbon_stats
from app.database import get_db
from app.models import User
from app.services.email_service import send_carbon_report, send_email


router = APIRouter(prefix="/notifications", tags=["notifications"])


class TestEmailRequest(BaseModel):
    to: str
    subject: str = "Bagcibasi Logistics AI Test E-postası"
    body: str = "<p>Test e-postası başarıyla tetiklendi.</p>"


@router.post("/test-email")
def send_test_email(
    payload: TestEmailRequest,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_roles("admin")),
) -> dict:
    background_tasks.add_task(send_email, str(payload.to), payload.subject, payload.body)
    return {"status": "queued"}


@router.post("/carbon-report/{customer_id}")
def send_customer_carbon_report(
    customer_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "manager")),
) -> dict:
    customer = get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")
    if not customer.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Musterinin e-posta adresi yok")

    summary = get_customer_carbon_stats(db, customer_id)
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Karbon raporu bulunamadi")
    background_tasks.add_task(send_carbon_report, customer, summary)
    return {"status": "queued", "customer_id": str(customer_id)}
