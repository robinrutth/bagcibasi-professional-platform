from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Customer, Shipment
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services.carbon_service import get_top_routes_from_shipments, get_vehicle_distribution_from_shipments
from app.services.email_service import send_welcome_email


def _base_query(include_inactive: bool = False):
    statement = select(Customer)
    if not include_inactive:
        statement = statement.where(Customer.is_active.is_(True))
    return statement


def _apply_filters(statement, filters: dict | None):
    filters = filters or {}
    search = filters.get("search")
    if search:
        like = f"%{search}%"
        statement = statement.where(
            Customer.name.ilike(like)
            | Customer.email.ilike(like)
            | Customer.phone.ilike(like)
            | Customer.city.ilike(like)
            | Customer.tax_number.ilike(like)
        )
    if filters.get("city"):
        statement = statement.where(Customer.city.ilike(f"%{filters['city']}%"))
    if filters.get("is_active") is not None:
        statement = statement.where(Customer.is_active.is_(filters["is_active"]))
    return statement


def get_customer(db: Session, customer_id: UUID | str) -> Customer | None:
    return db.scalar(_base_query().where(Customer.id == customer_id))


def get_customers(db: Session, skip: int = 0, limit: int = 100, filters: dict | None = None) -> tuple[list[Customer], int]:
    statement = _apply_filters(_base_query(include_inactive=filters and filters.get("is_active") is not None), filters)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(statement.order_by(Customer.created_at.desc()).offset(skip).limit(limit)).all()
    return list(rows), total


def get_customer_by_email(db: Session, email: str) -> Customer | None:
    return db.scalar(_base_query(include_inactive=True).where(Customer.email == email))


def create_customer(db: Session, customer_in: CustomerCreate, background_tasks=None) -> Customer:
    customer = Customer(**customer_in.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    if background_tasks and customer.email:
        background_tasks.add_task(send_welcome_email, customer)
    return customer


def update_customer(db: Session, customer_id: UUID | str, customer_in: CustomerUpdate) -> Customer | None:
    customer = get_customer(db, customer_id)
    if not customer:
        return None
    for key, value in customer_in.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    customer.updated_at = datetime.utcnow()
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def delete_customer(db: Session, customer_id: UUID | str) -> Customer | None:
    customer = get_customer(db, customer_id)
    if not customer:
        return None
    customer.is_active = False
    customer.updated_at = datetime.utcnow()
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def get_customer_with_shipments(db: Session, customer_id: UUID | str) -> Customer | None:
    return db.scalar(
        _base_query()
        .options(selectinload(Customer.shipments.and_(Shipment.is_deleted.is_(False))))
        .where(Customer.id == customer_id)
    )


def get_customer_carbon_stats(db: Session, customer_id: UUID | str) -> dict | None:
    customer = get_customer(db, customer_id)
    if not customer:
        return None
    shipments = list(
        db.scalars(
            select(Shipment)
            .where(Shipment.customer_id == customer_id, Shipment.is_deleted.is_(False))
            .order_by(Shipment.created_at.desc())
        ).all()
    )
    total = round(sum(row.co2_kg for row in shipments), 2)
    count = len(shipments)
    return {
        "customer_id": customer.id,
        "total_co2_kg": total,
        "shipment_count": count,
        "average_co2_kg": round(total / count, 2) if count else 0,
        "by_vehicle": get_vehicle_distribution_from_shipments(shipments),
        "top_routes": get_top_routes_from_shipments(shipments),
    }
