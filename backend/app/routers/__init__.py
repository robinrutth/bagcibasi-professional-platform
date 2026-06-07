# -*- coding: utf-8 -*-
"""Feature routers for versioned API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.crud import (
    assign_vehicle,
    complete_delivery,
    create_vehicle,
    delete_vehicle,
    get_vehicle,
    get_vehicles,
    update_vehicle,
    update_vehicle_location,
    update_vehicle_status,
)
from app.database import get_db
from app.models import User, Vehicle
from app.schemas import (
    VehicleAssign,
    VehicleCreate,
    VehicleListResponse,
    VehicleLocationUpdate,
    VehicleResponse,
    VehicleStatusUpdate,
    VehicleUpdate,
)


vehicles_router = APIRouter(prefix="/vehicles", tags=["vehicles"])
MANAGE_ROLES = {"admin", "manager"}
READ_ROLES = MANAGE_ROLES


def _ensure_reader(user: User) -> None:
    if user.role not in READ_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Araçları görüntüleme yetkiniz yok")


def _ensure_manager(user: User) -> None:
    if user.role not in MANAGE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için admin veya manager yetkisi gerekli")


def _ensure_can_view(vehicle: Vehicle, user: User) -> None:
    if user.role == "driver" and vehicle.driver_name != user.full_name:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sadece kendi aracınızı görebilirsiniz")


def _response(vehicle: Vehicle) -> VehicleResponse:
    return VehicleResponse.model_validate(vehicle)


@vehicles_router.get("", response_model=VehicleListResponse)
def list_vehicles_endpoint(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VehicleListResponse:
    _ensure_reader(current_user)
    rows, total = get_vehicles(db, status_filter)
    if current_user.role == "driver":
        rows = [row for row in rows if row.driver_name == current_user.full_name]
        total = len(rows)
    return VehicleListResponse(items=[_response(row) for row in rows], total=total)


@vehicles_router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle_endpoint(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VehicleResponse:
    _ensure_reader(current_user)
    vehicle = get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Araç bulunamadı")
    _ensure_can_view(vehicle, current_user)
    return _response(vehicle)


@vehicles_router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("admin"))])
def create_vehicle_endpoint(
    payload: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VehicleResponse:
    _ensure_manager(current_user)
    return _response(create_vehicle(db, payload))


@vehicles_router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle_endpoint(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VehicleResponse:
    _ensure_manager(current_user)
    vehicle = update_vehicle(db, vehicle_id, payload)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Araç bulunamadı")
    return _response(vehicle)


@vehicles_router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles("admin"))])
def delete_vehicle_endpoint(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _ensure_manager(current_user)
    vehicle = delete_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Araç bulunamadı")
    return None


@vehicles_router.put("/{vehicle_id}/status", response_model=VehicleResponse)
def update_vehicle_status_endpoint(
    vehicle_id: UUID,
    payload: VehicleStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VehicleResponse:
    _ensure_manager(current_user)
    vehicle = update_vehicle_status(db, vehicle_id, payload.status)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Araç bulunamadı")
    return _response(vehicle)


@vehicles_router.post("/{vehicle_id}/assign", response_model=VehicleResponse)
def assign_vehicle_endpoint(
    vehicle_id: UUID,
    payload: VehicleAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VehicleResponse:
    _ensure_manager(current_user)
    vehicle = assign_vehicle(db, vehicle_id, payload.shipment_id, payload.load_tons)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Araç bulunamadı")
    return _response(vehicle)


@vehicles_router.post("/{vehicle_id}/complete", response_model=VehicleResponse, dependencies=[Depends(require_roles("driver"))])
def complete_delivery_endpoint(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VehicleResponse:
    if current_user.role != "admin":
        vehicle = get_vehicle(db, vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Araç bulunamadı")
        _ensure_can_view(vehicle, current_user)
    vehicle = complete_delivery(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Araç bulunamadı")
    return _response(vehicle)


@vehicles_router.put("/{vehicle_id}/location", response_model=VehicleResponse, dependencies=[Depends(require_roles("driver"))])
def update_vehicle_location_endpoint(
    vehicle_id: UUID,
    payload: VehicleLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VehicleResponse:
    if current_user.role not in MANAGE_ROLES | {"driver"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Konum güncelleme yetkiniz yok")
    vehicle = get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Araç bulunamadı")
    _ensure_can_view(vehicle, current_user)
    return _response(update_vehicle_location(db, vehicle_id, payload.lat, payload.lng))
