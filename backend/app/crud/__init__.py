"""Feature CRUD modules for the Bağcıbaşı API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Shipment, Vehicle, VehicleStatus
from app.schemas import VehicleAssign, VehicleCreate, VehicleUpdate


VALID_VEHICLE_TRANSITIONS = {
    VehicleStatus.Bosta.value: {VehicleStatus.Yukleniyor.value, VehicleStatus.Bakimda.value},
    VehicleStatus.Yukleniyor.value: {VehicleStatus.Yolda.value, VehicleStatus.Bosta.value},
    VehicleStatus.Yolda.value: {VehicleStatus.Bosta.value, VehicleStatus.Bakimda.value},
    VehicleStatus.Bakimda.value: {VehicleStatus.Bosta.value},
}


def _normalize_status(value: str) -> str:
    aliases = {
        "Boşta": VehicleStatus.Bosta.value,
        "Bosta": VehicleStatus.Bosta.value,
        "Yükleniyor": VehicleStatus.Yukleniyor.value,
        "Yukleniyor": VehicleStatus.Yukleniyor.value,
        "Yolda": VehicleStatus.Yolda.value,
        "Bakımda": VehicleStatus.Bakimda.value,
        "Bakimda": VehicleStatus.Bakimda.value,
    }
    normalized = aliases.get(value.strip())
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz araç durumu")
    return normalized


def get_vehicles(db: Session, status_filter: str | None = None) -> tuple[list[Vehicle], int]:
    statement = select(Vehicle).where(Vehicle.is_deleted.is_(False))
    if status_filter:
        statement = statement.where(Vehicle.status == _normalize_status(status_filter))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(statement.order_by(Vehicle.plate_number.asc())).all()
    return list(rows), total


def get_vehicle(db: Session, vehicle_id: UUID | str) -> Vehicle | None:
    return db.scalar(select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.is_deleted.is_(False)))


def create_vehicle(db: Session, vehicle_in: VehicleCreate) -> Vehicle:
    payload = vehicle_in.model_dump()
    payload["status"] = _normalize_status(payload.get("status") or VehicleStatus.Bosta.value)
    vehicle = Vehicle(**payload)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def update_vehicle(db: Session, vehicle_id: UUID | str, vehicle_in: VehicleUpdate) -> Vehicle | None:
    vehicle = get_vehicle(db, vehicle_id)
    if not vehicle:
        return None
    updates = vehicle_in.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] is not None:
        updates["status"] = _normalize_status(updates["status"])
    if "current_load_tons" in updates and updates["current_load_tons"] and updates["current_load_tons"] > vehicle.capacity_tons:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Araç kapasitesi aşılamaz")
    for key, value in updates.items():
        if hasattr(vehicle, key):
            setattr(vehicle, key, value)
    vehicle.updated_at = datetime.utcnow()
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def delete_vehicle(db: Session, vehicle_id: UUID | str) -> Vehicle | None:
    vehicle = get_vehicle(db, vehicle_id)
    if not vehicle:
        return None
    vehicle.is_deleted = True
    vehicle.current_shipment_id = None
    vehicle.current_load_tons = 0
    vehicle.status = VehicleStatus.Bakimda.value
    vehicle.updated_at = datetime.utcnow()
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def update_vehicle_status(db: Session, vehicle_id: UUID | str, new_status: str) -> Vehicle | None:
    vehicle = get_vehicle(db, vehicle_id)
    if not vehicle:
        return None
    next_status = _normalize_status(new_status)
    if next_status not in VALID_VEHICLE_TRANSITIONS.get(vehicle.status, set()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz durum geçişi")
    vehicle.status = next_status
    if next_status == VehicleStatus.Bosta.value:
        vehicle.current_shipment_id = None
        vehicle.current_load_tons = 0
    vehicle.updated_at = datetime.utcnow()
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def assign_vehicle(db: Session, vehicle_id: UUID | str, shipment_id: UUID | str, load_tons: float) -> Vehicle | None:
    statement = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.is_deleted.is_(False)).with_for_update()
    vehicle = db.scalar(statement)
    if not vehicle:
        return None

    is_bosta = vehicle.status == VehicleStatus.Bosta.value
    is_partial = vehicle.status == VehicleStatus.Yukleniyor.value
    current_load_tons = vehicle.current_load_tons or 0
    remaining_capacity = vehicle.capacity_tons - current_load_tons

    if not is_bosta and not is_partial:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Araç artık müsait değil")
    if load_tons > remaining_capacity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Araç kapasitesi aşıldı")
    shipment = db.scalar(select(Shipment).where(Shipment.id == shipment_id, Shipment.is_deleted.is_(False)).with_for_update())
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sevkiyat bulunamadı")

    vehicle.status = VehicleStatus.Yukleniyor.value
    vehicle.current_shipment_id = shipment.id
    vehicle.current_load_tons = current_load_tons + load_tons
    vehicle.updated_at = datetime.utcnow()
    shipment.vehicle_id = vehicle.id
    shipment.vehicle_type = vehicle.vehicle_type
    shipment.tonnage = load_tons
    shipment.weight_kg = load_tons * 1000
    shipment.updated_at = datetime.utcnow()
    db.add_all([vehicle, shipment])
    db.commit()
    db.refresh(vehicle)
    return vehicle


def complete_delivery(db: Session, vehicle_id: UUID | str) -> Vehicle | None:
    vehicle = get_vehicle(db, vehicle_id)
    if not vehicle:
        return None
    if vehicle.status != VehicleStatus.Yolda.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Teslim tamamlamak için araç Yolda olmalı")
    vehicle.status = VehicleStatus.Bosta.value
    vehicle.current_shipment_id = None
    vehicle.current_load_tons = 0
    vehicle.updated_at = datetime.utcnow()
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def update_vehicle_location(db: Session, vehicle_id: UUID | str, lat: float, lng: float) -> Vehicle | None:
    vehicle = get_vehicle(db, vehicle_id)
    if not vehicle:
        return None
    vehicle.current_lat = lat
    vehicle.current_lng = lng
    vehicle.updated_at = datetime.utcnow()
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle
