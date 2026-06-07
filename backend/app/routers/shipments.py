# -*- coding: utf-8 -*-
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.crud.shipment import (
    calculate_invoice,
    create_shipment,
    delete_shipment,
    get_shipment,
    get_shipments,
    get_shipments_by_customer,
    update_shipment,
)
from app.database import get_db
from app.models import Shipment, User
from app.schemas.shipment import ShipmentCreate, ShipmentListResponse, ShipmentResponse, ShipmentUpdate


router = APIRouter(prefix="/shipments", tags=["shipments"])

MANAGE_ROLES = {"admin", "manager", "operation"}
READ_ROLES = {"admin", "manager"}


class PricingRequest(BaseModel):
    weight_kg: float = Field(ge=0)
    desi: float = Field(ge=0)
    distance_km: float = Field(ge=0)
    vehicle_type: str = Field(min_length=2)


class PricingResponse(BaseModel):
    invoice_amount: float
    distance_km: float
    vehicle_type: str


def _ensure_reader(user: User) -> None:
    if user.role not in READ_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu kayıtları görüntüleme yetkiniz yok")


def _ensure_manager(user: User) -> None:
    if user.role not in MANAGE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için admin veya manager yetkisi gerekli")


def _ensure_can_view(shipment: Shipment, user: User) -> None:
    if user.role == "driver" and shipment.driver_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sadece size atanmış sevkiyatları görebilirsiniz")


def _response(shipment: Shipment) -> ShipmentResponse:
    return ShipmentResponse.model_validate(shipment)


@router.get("", response_model=ShipmentListResponse)
def list_shipments_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    customer_id: UUID | None = None,
    driver_id: UUID | None = None,
    origin: str | None = None,
    destination: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShipmentListResponse:
    # Versioned list endpoint with pagination and role-aware filtering.
    _ensure_reader(current_user)
    filters = {
        "status": status_filter,
        "customer_id": customer_id,
        "driver_id": driver_id,
        "origin": origin,
        "destination": destination,
    }
    if current_user.role == "driver":
        filters["driver_id"] = current_user.id
    rows, total = get_shipments(db, skip=skip, limit=limit, filters=filters)
    return ShipmentListResponse(items=[_response(row) for row in rows], total=total, skip=skip, limit=limit)


@router.get("/customer/{customer_id}", response_model=list[ShipmentResponse])
def list_customer_shipments_endpoint(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ShipmentResponse]:
    _ensure_reader(current_user)
    rows = get_shipments_by_customer(db, customer_id)
    if current_user.role == "driver":
        rows = [row for row in rows if row.driver_id == current_user.id]
    return [_response(row) for row in rows]


@router.post("/pricing/preview", response_model=PricingResponse)
def preview_pricing_endpoint(
    payload: PricingRequest,
    current_user: User = Depends(get_current_user),
) -> PricingResponse:
    _ensure_reader(current_user)
    result = calculate_invoice(payload.weight_kg, payload.desi, payload.distance_km, payload.vehicle_type)
    if result is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Fiyat hesaplamak icin gecerli yuk ve mesafe girin")
    return PricingResponse(
        invoice_amount=result["invoice"],
        distance_km=payload.distance_km,
        vehicle_type=payload.vehicle_type,
    )


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment_endpoint(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShipmentResponse:
    _ensure_reader(current_user)
    shipment = get_shipment(db, shipment_id)
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sevkiyat bulunamadı")
    _ensure_can_view(shipment, current_user)
    return _response(shipment)


@router.post("", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("operation", "manager"))])
def create_shipment_endpoint(
    payload: ShipmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShipmentResponse:
    _ensure_manager(current_user)
    return _response(create_shipment(db, payload, current_user, background_tasks))


@router.put("/{shipment_id}", response_model=ShipmentResponse, dependencies=[Depends(require_roles("operation", "manager"))])
def update_shipment_endpoint(
    shipment_id: UUID,
    payload: ShipmentUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShipmentResponse:
    existing = get_shipment(db, shipment_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sevkiyat bulunamadı")
    if current_user.role == "driver":
        _ensure_can_view(existing, current_user)
        if payload.model_fields_set - {"status"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Suruculer sadece kendi sevkiyat durumunu guncelleyebilir")
    else:
        _ensure_manager(current_user)
    shipment = update_shipment(db, shipment_id, payload, background_tasks)
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sevkiyat bulunamadı")
    return _response(shipment)


@router.delete("/{shipment_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles("manager"))])
def delete_shipment_endpoint(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _ensure_manager(current_user)
    shipment = delete_shipment(db, shipment_id)
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sevkiyat bulunamadı")
    return None
