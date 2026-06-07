from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.calculations import calculate_operation, classify_emission
from app.models import Customer, Shipment, User
from app.schemas.shipment import ShipmentCreate, ShipmentUpdate
from app.services.carbon_service import calculate_distance_km, calculate_emission
from app.services.email_service import is_delivered_status, queue_shipment_notification


RECALC_FIELDS = {"origin", "destination", "cargo_type", "tonnage", "delivery_date"}
CARBON_RECALC_FIELDS = {"vehicle_type", "distance_km", "weight_kg", "tonnage"}
INVOICE_RECALC_FIELDS = {"vehicle_type", "distance_km", "weight_kg", "desi", "tonnage"}
VEHICLE_COEFFICIENTS = {
    "panelvan": 1.0,
    "kamyonet": 1.2,
    "kamyon": 1.5,
    "tir": 2.2,
    "elektrikli": 1.1,
}
VEHICLE_BASE_PRICES = {
    "panelvan": 500.0,
    "elektrikli": 600.0,
    "kamyonet": 750.0,
    "kamyon": 1500.0,
    "tir": 3000.0,
}
VEHICLE_ALIASES = {
    "panelvan": "panelvan",
    "hafif ticari": "panelvan",
    "minivan": "kamyonet",
    "kamyonet": "kamyonet",
    "truck": "kamyon",
    "kamyon": "kamyon",
    "tir": "tir",
    "tır": "tir",
    "electric": "elektrikli",
    "elektrikli": "elektrikli",
    "elektrikli arac": "elektrikli",
    "elektrikli araç": "elektrikli",
}
DEFAULT_PROFIT_MARGIN = 0.20


def _normalize_invoice_vehicle(vehicle_type: str | None) -> str:
    key = (vehicle_type or "kamyon").strip().lower()
    return VEHICLE_ALIASES.get(key, key)


def _tiered_unit_price(chargeable_weight: float) -> float:
    if chargeable_weight <= 200:
        return 15.0
    if chargeable_weight <= 500:
        return 12.0
    if chargeable_weight <= 1000:
        return 8.0
    return 6.0


def _distance_floor_price(distance_km: float) -> float:
    if distance_km <= 300:
        return 2500.0
    if distance_km <= 700:
        return 4500.0
    return 7000.0


def calculate_invoice(
    weight_kg: float | None,
    desi: float | None,
    distance_km: float | None,
    vehicle_type: str | None,
) -> dict[str, float] | None:
    chargeable_weight = max(float(weight_kg or 0), float(desi or 0))
    if chargeable_weight <= 0 or distance_km is None or float(distance_km) < 0:
        return None

    normalized_vehicle = _normalize_invoice_vehicle(vehicle_type)
    coefficient = VEHICLE_COEFFICIENTS.get(normalized_vehicle, VEHICLE_COEFFICIENTS["kamyon"])
    vehicle_base_price = VEHICLE_BASE_PRICES.get(normalized_vehicle, VEHICLE_BASE_PRICES["kamyon"])
    min_partial_price = _distance_floor_price(float(distance_km))
    volume_cost = chargeable_weight * _tiered_unit_price(chargeable_weight)
    distance_cost = float(distance_km) * 40
    raw_cost = (volume_cost + distance_cost) * coefficient
    cost = max(raw_cost, vehicle_base_price, min_partial_price)
    invoice = cost * (1 + DEFAULT_PROFIT_MARGIN)
    profit = invoice - cost
    return {
        "invoice": round(invoice, 2),
        "cost": round(cost, 2),
        "profit": round(profit, 2),
        "navlun": round(chargeable_weight, 2),
        "profit_margin": DEFAULT_PROFIT_MARGIN,
    }


def _apply_invoice(shipment: Shipment, result: dict[str, float] | None) -> None:
    if result is None:
        shipment.invoice = None
        shipment.cost = None
        shipment.profit = None
        return
    shipment.invoice = result["invoice"]
    shipment.cost = result["cost"]
    shipment.profit = result["profit"]
    shipment.invoice_amount = result["invoice"]
    shipment.cost_amount = result["cost"]
    shipment.profit_amount = result["profit"]
    shipment.profit_margin = result.get("profit_margin", DEFAULT_PROFIT_MARGIN)


def _base_query():
    return select(Shipment).where(Shipment.is_deleted.is_(False))


def _apply_filters(statement, filters: dict | None):
    filters = filters or {}
    if filters.get("customer_id"):
        statement = statement.where(Shipment.customer_id == filters["customer_id"])
    if filters.get("driver_id"):
        statement = statement.where(Shipment.driver_id == filters["driver_id"])
    if filters.get("status"):
        statement = statement.where(Shipment.status == filters["status"])
    if filters.get("origin"):
        statement = statement.where(Shipment.origin.ilike(f"%{filters['origin']}%"))
    if filters.get("destination"):
        statement = statement.where(Shipment.destination.ilike(f"%{filters['destination']}%"))
    return statement


def get_shipment(db: Session, shipment_id: UUID | str) -> Shipment | None:
    # Return a single active shipment or None when it was soft-deleted/not found.
    return db.scalar(_base_query().where(Shipment.id == shipment_id))


def get_shipments(db: Session, skip: int = 0, limit: int = 100, filters: dict | None = None) -> tuple[list[Shipment], int]:
    statement = _apply_filters(_base_query(), filters)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(statement.order_by(Shipment.created_at.desc()).offset(skip).limit(limit)).all()
    return list(rows), total


def create_shipment(db: Session, shipment_in: ShipmentCreate, current_user: User, background_tasks=None) -> Shipment:
    payload = shipment_in.model_dump()
    calculated = calculate_operation(
        payload["origin"],
        payload["destination"],
        payload["cargo_type"],
        payload["tonnage"],
        payload["delivery_date"],
    )
    provided_distance = payload.get("distance_km")
    if provided_distance and provided_distance > 0:
        calculated["distance_km"] = provided_distance
    elif provided_distance == 0:
        calculated["distance_km"] = 0
    elif payload.get("origin") and payload.get("destination"):
        auto_distance = calculate_distance_km(payload["origin"], payload["destination"])
        if auto_distance is not None:
            calculated["distance_km"] = auto_distance
    if payload.get("vehicle_type"):
        calculated["vehicle_type"] = payload["vehicle_type"]
    weight_kg = payload.get("weight_kg") or payload["tonnage"] * 1000
    provided_invoice = payload.get("invoice_amount")
    provided_co2 = payload.get("co2_kg")

    if provided_invoice and float(provided_invoice) > 0:
        # Frontend provided pre-calculated values, use them directly.
        provided_profit = payload.get("profit_amount")
        profit_margin = DEFAULT_PROFIT_MARGIN
        cost = float(provided_invoice) / (1 + profit_margin)
        profit = provided_profit if provided_profit and float(provided_profit) > 0 else float(provided_invoice) * profit_margin
        invoice_override = {
            "invoice": float(provided_invoice),
            "cost": round(cost, 2),
            "profit": round(float(profit), 2),
            "profit_margin": profit_margin,
        }
    else:
        invoice_override = calculate_invoice(weight_kg, payload.get("desi"), calculated["distance_km"], calculated["vehicle_type"])

    if provided_co2 and float(provided_co2) > 0:
        calculated["co2_kg"] = float(provided_co2)
    else:
        calculated["co2_kg"] = calculate_emission(
            db,
            calculated["vehicle_type"],
            calculated["distance_km"],
            weight_kg,
            payload["origin"],
            payload["destination"],
        )
    calculated["risk_level"] = classify_emission(
        calculated["co2_kg"] or 0,
        calculated.get("distance_km", 0),
        calculated.get("vehicle_type", "Kamyon"),
    )
    shipment = Shipment(
        customer_id=payload.get("customer_id"),
        driver_id=payload.get("driver_id"),
        vehicle_id=payload.get("vehicle_id"),
        customer_name=payload["customer_name"],
        status=payload.get("status") or "Hazırlanıyor",
        weight_kg=weight_kg,
        desi=payload.get("desi"),
        **{key: value for key, value in calculated.items() if hasattr(Shipment, key)},
    )
    _apply_invoice(shipment, invoice_override)
    if current_user.role == "driver":
        shipment.driver_id = current_user.id
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    customer = db.get(Customer, shipment.customer_id) if shipment.customer_id else None
    queue_shipment_notification(background_tasks, shipment, customer, "created")
    return shipment


def update_shipment(db: Session, shipment_id: UUID | str, shipment_in: ShipmentUpdate, background_tasks=None) -> Shipment | None:
    shipment = get_shipment(db, shipment_id)
    if not shipment:
        return None

    previous_status = shipment.status
    updates = shipment_in.model_dump(exclude_unset=True)
    if "carbon_emission" in updates:
        updates["co2_kg"] = updates.pop("carbon_emission")

    should_recalculate = bool(RECALC_FIELDS.intersection(updates))
    should_recalculate_carbon = bool(CARBON_RECALC_FIELDS.intersection(updates)) or should_recalculate
    should_recalculate_invoice = bool(INVOICE_RECALC_FIELDS.intersection(updates)) or should_recalculate
    for key, value in updates.items():
        if hasattr(shipment, key):
            setattr(shipment, key, value)

    if should_recalculate:
        calculated = calculate_operation(
            shipment.origin,
            shipment.destination,
            shipment.cargo_type,
            shipment.tonnage,
            shipment.delivery_date,
        )
        for key, value in calculated.items():
            if hasattr(shipment, key) and key not in updates:
                setattr(shipment, key, value)
        if shipment.weight_kg is None or "tonnage" in updates:
            shipment.weight_kg = shipment.tonnage * 1000

    if should_recalculate_carbon and "co2_kg" not in updates:
        shipment.co2_kg = calculate_emission(
            db,
            shipment.vehicle_type,
            shipment.distance_km,
            shipment.weight_kg or shipment.tonnage * 1000,
        )

    if should_recalculate_invoice:
        _apply_invoice(
            shipment,
            calculate_invoice(
                shipment.weight_kg or shipment.tonnage * 1000,
                shipment.desi,
                shipment.distance_km,
                shipment.vehicle_type,
            ),
        )

    shipment.updated_at = datetime.utcnow()
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    status_changed = "status" in updates and previous_status != shipment.status
    if status_changed:
        customer = db.get(Customer, shipment.customer_id) if shipment.customer_id else None
        event = "delivered" if is_delivered_status(shipment.status) else "updated"
        queue_shipment_notification(background_tasks, shipment, customer, event)
    return shipment


def delete_shipment(db: Session, shipment_id: UUID | str) -> Shipment | None:
    shipment = get_shipment(db, shipment_id)
    if not shipment:
        return None
    shipment.is_deleted = True
    shipment.updated_at = datetime.utcnow()
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return shipment


def get_shipments_by_customer(db: Session, customer_id: UUID | str) -> list[Shipment]:
    rows = db.scalars(
        _base_query()
        .where(Shipment.customer_id == customer_id)
        .order_by(Shipment.created_at.desc())
    ).all()
    return list(rows)
