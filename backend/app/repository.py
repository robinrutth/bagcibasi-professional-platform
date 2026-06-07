from __future__ import annotations

from datetime import date
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .calculations import calculate_operation
from .crud.shipment import calculate_invoice
from .models import CashMovement, Customer, Shipment, User
from .services.carbon_service import calculate_distance_km, calculate_emission, seed_default_emission_factors


SHIPMENT_MODEL_FIELDS = {
    "origin",
    "destination",
    "cargo_type",
    "tonnage",
    "desi",
    "delivery_date",
    "distance_km",
    "vehicle_type",
    "invoice",
    "cost",
    "profit",
    "cost_amount",
    "invoice_amount",
    "profit_amount",
    "profit_margin",
    "co2_kg",
    "risk_level",
    "ai_recommendation",
}


def to_shipment_model_payload(calculated: dict) -> dict:
    return {key: value for key, value in calculated.items() if key in SHIPMENT_MODEL_FIELDS}


def seed_shipments() -> list[dict]:
    base = [
        ("Berksa", "Manisa", "İzmir", "Ambalaj", 12, date(2026, 5, 4), "Teslim Edildi"),
        ("Kent Beton", "Manisa", "İzmir", "İnşaat", 16, date(2026, 5, 5), "Teslim Edildi"),
        ("MamaTürkiye", "Manisa", "İzmir", "Gıda", 3, date(2026, 5, 6), "Yolda"),
        ("Gürel İnşaat", "Manisa", "İstanbul", "İnşaat", 22, date(2026, 5, 7), "Yolda"),
    ]
    rows: list[dict] = []
    for customer, origin, destination, cargo, tonnage, delivery_date, status in base:
        calculated = calculate_operation(origin, destination, cargo, tonnage, delivery_date)
        rows.append(
            {
                "customer_name": customer,
                "status": status,
                **to_shipment_model_payload(calculated),
            }
        )
    return rows


def seed_database(db: Session) -> None:
    seed_users(db)
    seed_default_emission_factors(db)

    has_shipments = db.scalar(select(Shipment).limit(1))
    if has_shipments:
        db.commit()
        return

    has_customers = db.scalar(select(Customer).limit(1))
    if not has_customers:
        customers = [
            Customer(name="Berksa", sector="Ambalaj", payment_terms="Vadeli", risk_level="Orta", notes="İlk müşteri, vadeli çalışır."),
            Customer(name="Kent Beton", sector="İnşaat", payment_terms="Peşin", risk_level="Düşük", notes="Peşin ödeme alışkanlığı iyi."),
            Customer(name="MamaTürkiye", sector="Gıda", payment_terms="Peşin", risk_level="Düşük", notes="Düzenli küçük hacimli taşıma."),
            Customer(name="Gürel İnşaat", sector="İnşaat", payment_terms="Vadeli", risk_level="Orta", notes="Yüksek hacimli potansiyel."),
        ]
        db.add_all(customers)

    for row in seed_shipments():
        row["weight_kg"] = row["tonnage"] * 1000
        row["co2_kg"] = calculate_emission(db, row["vehicle_type"], row["distance_km"], row["weight_kg"])
        invoice_result = calculate_invoice(row["weight_kg"], row.get("desi"), row["distance_km"], row["vehicle_type"])
        if invoice_result:
            row["invoice"] = row["invoice_amount"] = invoice_result["invoice"]
            row["cost"] = row["cost_amount"] = invoice_result["cost"]
            row["profit"] = row["profit_amount"] = invoice_result["profit"]
            row["profit_margin"] = invoice_result["profit_margin"]
        db.add(Shipment(**row))

    has_cash = db.scalar(select(CashMovement).limit(1))
    if not has_cash:
        db.add_all(
            [
                CashMovement(description="Açılış sermayesi", movement_type="in", amount=550000, payment_type="Peşin"),
                CashMovement(description="Operasyon tahsilatı", movement_type="in", amount=30000, payment_type="Peşin"),
                CashMovement(description="Tedarikçi ödemeleri", movement_type="out", amount=70000, payment_type="Havale"),
                CashMovement(description="Bekleyen tahsilat", movement_type="pending", amount=63000, payment_type="Vadeli"),
            ]
        )
    db.commit()


def seed_users(db: Session) -> None:
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    operation_password = os.getenv("OPERATION_PASSWORD", "operasyon123")
    finance_password = os.getenv("FINANCE_PASSWORD", "finans123")
    admin = db.scalar(select(User).where(User.username == "admin"))
    if admin:
        return
    db.add_all(
        [
            User(
                username="admin",
                full_name="Bağcıbaşı Admin",
                role="admin",
                password_hash=hash_password(admin_password),
            ),
            User(
                username="operasyon",
                full_name="Operasyon Kullanıcısı",
                role="operation",
                password_hash=hash_password(operation_password),
            ),
            User(
                username="finans",
                full_name="Finans Kullanıcısı",
                role="finance",
                password_hash=hash_password(finance_password),
            ),
        ]
    )


def shipment_to_dict(shipment: Shipment) -> dict:
    return {
        "id": str(shipment.id),
        "customer_id": str(shipment.customer_id) if shipment.customer_id else None,
        "driver_id": str(shipment.driver_id) if shipment.driver_id else None,
        "vehicle_id": str(shipment.vehicle_id) if shipment.vehicle_id else None,
        "customer_name": shipment.customer_name,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "cargo_type": shipment.cargo_type,
        "tonnage": shipment.tonnage,
        "weight_kg": shipment.weight_kg,
        "desi": shipment.desi,
        "delivery_date": shipment.delivery_date,
        "distance_km": shipment.distance_km,
        "vehicle_type": shipment.vehicle_type,
        "status": shipment.status,
        "invoice": shipment.invoice,
        "cost": shipment.cost,
        "profit": shipment.profit,
        "cost_amount": shipment.cost_amount,
        "invoice_amount": shipment.invoice_amount,
        "profit_amount": shipment.profit_amount,
        "profit_margin": shipment.profit_margin,
        "co2_kg": shipment.co2_kg,
        "carbon_emission": shipment.co2_kg,
        "risk_level": shipment.risk_level,
        "ai_recommendation": shipment.ai_recommendation,
        "created_at": shipment.created_at,
        "updated_at": shipment.updated_at,
    }


def list_shipments(db: Session) -> list[dict]:
    rows = db.scalars(select(Shipment).where(Shipment.is_deleted.is_(False)).order_by(Shipment.created_at.desc())).all()
    return [shipment_to_dict(row) for row in rows]


def create_shipment(db: Session, payload: dict) -> dict:
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
    else:
        auto_distance = calculate_distance_km(payload["origin"], payload["destination"])
        if auto_distance is not None:
            calculated["distance_km"] = auto_distance
    weight_kg = payload["weight_kg"] if payload.get("weight_kg") else payload["tonnage"] * 1000
    desi = payload.get("desi")
    if payload.get("vehicle_type"):
        calculated["vehicle_type"] = payload["vehicle_type"]
    calculated["co2_kg"] = calculate_emission(
        db,
        calculated["vehicle_type"],
        calculated["distance_km"],
        weight_kg,
        payload["origin"],
        payload["destination"],
    )
    invoice_result = calculate_invoice(weight_kg, desi, calculated["distance_km"], calculated["vehicle_type"])
    if invoice_result:
        calculated["invoice"] = calculated["invoice_amount"] = invoice_result["invoice"]
        calculated["cost"] = calculated["cost_amount"] = invoice_result["cost"]
        calculated["profit"] = calculated["profit_amount"] = invoice_result["profit"]
        calculated["profit_margin"] = invoice_result["profit_margin"]
    shipment = Shipment(
        customer_name=payload["customer_name"],
        vehicle_id=payload.get("vehicle_id"),
        status="Hazırlanıyor",
        weight_kg=weight_kg,
        desi=desi,
        **to_shipment_model_payload(calculated),
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return shipment_to_dict(shipment)


def dashboard_summary(db: Session) -> dict:
    shipments = list_shipments(db)
    total_revenue = sum(item["invoice_amount"] for item in shipments)
    total_profit = sum(item["profit_amount"] for item in shipments)
    active_operations = len([item for item in shipments if item["status"] != "Teslim Edildi"])
    delivered = len([item for item in shipments if item["status"] == "Teslim Edildi"])
    total_co2 = sum(item["co2_kg"] for item in shipments)
    risky = len([item for item in shipments if item["risk_level"] != "Düşük"])

    return {
        "total_revenue": round(total_revenue, 2),
        "total_profit": round(total_profit, 2),
        "active_operations": active_operations,
        "delivery_success_rate": round((delivered / len(shipments)) * 100, 2) if shipments else 0,
        "total_co2_kg": round(total_co2, 2),
        "risky_operations": risky,
    }


def finance_summary(db: Session) -> dict:
    movements = db.scalars(select(CashMovement)).all()
    current_cash = 0.0
    pending = 0.0
    for movement in movements:
        if movement.movement_type == "in":
            current_cash += movement.amount
        elif movement.movement_type == "out":
            current_cash -= movement.amount
        elif movement.movement_type == "pending":
            pending += movement.amount

    projected_outflow = 85000
    projected_cash = current_cash + pending - projected_outflow
    return {
        "current_cash": current_cash,
        "pending_collections": pending,
        "projected_outflow": projected_outflow,
        "projected_cash_15_days": projected_cash,
        "total_profit": dashboard_summary(db)["total_profit"],
        "ai_warning": "Vadeli tahsilatlar gecikirse 15 gün içinde kasa baskısı oluşabilir.",
    }


def list_users(db: Session) -> list[dict]:
    users = db.scalars(select(User).order_by(User.created_at.asc())).all()
    return [
        {
            "id": str(user.id),
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }
        for user in users
    ]
