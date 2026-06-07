# -*- coding: utf-8 -*-
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.crud.customer import (
    create_customer,
    delete_customer,
    get_customer,
    get_customer_by_email,
    get_customer_carbon_stats,
    get_customer_with_shipments,
    get_customers,
    update_customer,
)
from app.database import get_db
from app.models import User
from app.schemas.customer import (
    CustomerCarbonStats,
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
    CustomerWithShipments,
)


router = APIRouter(prefix="/customers", tags=["customers"], dependencies=[Depends(require_roles("manager"))])

MANAGE_ROLES = {"admin", "manager"}
READ_ROLES = MANAGE_ROLES


def _ensure_reader(user: User) -> None:
    if user.role not in READ_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Musteri kayitlarini goruntuleme yetkiniz yok")


def _ensure_manager(user: User) -> None:
    if user.role not in MANAGE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu islem icin admin veya manager yetkisi gerekli")


def _response(customer) -> CustomerResponse:
    return CustomerResponse.model_validate(customer)


@router.get("", response_model=CustomerListResponse)
def list_customers_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    city: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CustomerListResponse:
    _ensure_reader(current_user)
    rows, total = get_customers(db, skip=skip, limit=limit, filters={"search": search, "city": city, "is_active": is_active})
    return CustomerListResponse(items=[_response(row) for row in rows], total=total, skip=skip, limit=limit)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer_endpoint(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CustomerResponse:
    _ensure_reader(current_user)
    customer = get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")
    return _response(customer)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer_endpoint(
    payload: CustomerCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CustomerResponse:
    _ensure_manager(current_user)
    if payload.email and get_customer_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta ile musteri zaten var")
    return _response(create_customer(db, payload, background_tasks))


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer_endpoint(
    customer_id: UUID,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CustomerResponse:
    _ensure_manager(current_user)
    if payload.email:
        existing = get_customer_by_email(db, payload.email)
        if existing and existing.id != customer_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta ile musteri zaten var")
    customer = update_customer(db, customer_id, payload)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")
    return _response(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer_endpoint(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _ensure_manager(current_user)
    customer = delete_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")
    return None


@router.get("/{customer_id}/shipments", response_model=CustomerWithShipments)
def get_customer_shipments_endpoint(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CustomerWithShipments:
    _ensure_reader(current_user)
    customer = get_customer_with_shipments(db, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")
    return CustomerWithShipments.model_validate(customer)


@router.get("/{customer_id}/carbon-stats", response_model=CustomerCarbonStats)
def get_customer_carbon_stats_endpoint(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_reader(current_user)
    stats = get_customer_carbon_stats(db, customer_id)
    if not stats:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")
    return stats
