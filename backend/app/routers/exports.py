# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user, require_roles
from app.crud.customer import create_customer, get_customer_by_email, update_customer
from app.crud.shipment import calculate_invoice, create_shipment
from app.database import get_db
from app.models import Customer, Shipment, User
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.schemas.shipment import ShipmentCreate
from app.services.carbon_service import (
    calculate_emission,
    get_carbon_summary,
    get_top_routes_from_shipments,
    get_trend_from_shipments,
    get_vehicle_distribution_from_shipments,
)
from app.services.export_service import (
    export_carbon_report_excel,
    export_customers_csv,
    export_shipments_csv,
    export_shipments_excel,
    generate_import_rows,
    generate_import_template,
    validate_customer_row,
    validate_shipment_row,
)
from app.services.pdf_service import generate_carbon_report_pdf


router = APIRouter(prefix="/exports", tags=["exports"], dependencies=[Depends(require_roles("manager"))])
imports_router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(require_roles("manager"))])
READ_ROLES = {"admin", "manager"}
IMPORT_ROLES = {"admin", "manager"}
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def _ensure_export_reader(user: User) -> None:
    if user.role not in READ_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Export yetkiniz yok")


def _ensure_import_manager(user: User) -> None:
    if user.role not in IMPORT_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Import yetkiniz yok")


async def _read_import_file(file: UploadFile) -> bytes:
    filename = file.filename or ""
    if not filename.lower().endswith((".xlsx", ".csv")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sadece .xlsx veya .csv dosyasi yuklenebilir")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bos dosya yuklenemez")
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dosya boyutu 5MB limitini asamaz")
    return content


def _import_response(success: int, details: list[dict]) -> dict:
    return {"success": success, "errors": len(details), "details": details}


def _date_suffix() -> str:
    return date.today().isoformat()


def _shipment_statement(
    start_date: date | None,
    end_date: date | None,
    vehicle_type: str | None,
    status_filter: str | None,
    customer_id: UUID | None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="start_date end_date degerinden buyuk olamaz.")
    statement = select(Shipment).options(selectinload(Shipment.customer)).where(Shipment.is_deleted.is_(False))
    if start_date:
        statement = statement.where(Shipment.delivery_date >= start_date)
    if end_date:
        statement = statement.where(Shipment.delivery_date <= end_date)
    if vehicle_type:
        statement = statement.where(Shipment.vehicle_type == vehicle_type)
    if status_filter:
        statement = statement.where(Shipment.status == status_filter)
    if customer_id:
        statement = statement.where(Shipment.customer_id == customer_id)
    return statement.order_by(Shipment.created_at.desc())


def _shipment_rows(
    db: Session,
    start_date: date | None,
    end_date: date | None,
    vehicle_type: str | None,
    status_filter: str | None,
    customer_id: UUID | None,
) -> list[Shipment]:
    statement = _shipment_statement(start_date, end_date, vehicle_type, status_filter, customer_id)
    return list(db.scalars(statement).all())


def _shipment_stream(
    db: Session,
    start_date: date | None,
    end_date: date | None,
    vehicle_type: str | None,
    status_filter: str | None,
    customer_id: UUID | None,
):
    statement = _shipment_statement(start_date, end_date, vehicle_type, status_filter, customer_id)
    return db.scalars(statement).yield_per(500)


@router.get("/shipments/csv")
def shipments_csv_endpoint(
    start_date: date | None = None,
    end_date: date | None = None,
    vehicle_type: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    customer_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    _ensure_export_reader(current_user)
    shipments = _shipment_stream(db, start_date, end_date, vehicle_type, status_filter, customer_id)
    filename = f"shipments_{_date_suffix()}.csv"
    return StreamingResponse(
        export_shipments_csv(shipments),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/shipments/excel")
def shipments_excel_endpoint(
    start_date: date | None = None,
    end_date: date | None = None,
    vehicle_type: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    customer_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    _ensure_export_reader(current_user)
    shipments = _shipment_rows(db, start_date, end_date, vehicle_type, status_filter, customer_id)
    filename = f"shipments_{_date_suffix()}.xlsx"
    return StreamingResponse(
        export_shipments_excel(shipments),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/carbon/excel")
def carbon_excel_endpoint(
    period: str = Query("monthly", pattern="^(monthly|yearly)$"),
    customer_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    _ensure_export_reader(current_user)
    summary_period = "monthly"
    if customer_id:
        shipments = list(
            db.scalars(
                select(Shipment)
                .where(Shipment.customer_id == customer_id, Shipment.is_deleted.is_(False))
                .order_by(Shipment.created_at.desc())
            ).all()
        )
        summary = {
            "total_co2": round(sum(row.co2_kg or 0 for row in shipments), 4),
            "total_shipments": len(shipments),
            "avg_co2": round(sum(s.co2_kg or 0 for s in shipments) / len(shipments), 4) if shipments else 0,
            "by_vehicle": get_vehicle_distribution_from_shipments(shipments),
            "trend": get_trend_from_shipments(shipments, summary_period),
            "top_routes": get_top_routes_from_shipments(shipments),
            "shipments": [
                {
                    "musteri": s.customer.name if s.customer else (s.customer_name or ""),
                    "origin": s.origin or "",
                    "destination": s.destination or "",
                    "vehicle_type": s.vehicle_type or "",
                    "weight_kg": float(s.weight_kg or 0),
                    "distance_km": float(s.distance_km or 0),
                    "co2_kg": float(s.co2_kg or 0),
                    "invoice_amount": float(s.invoice_amount or 0),
                    "status": s.status or "",
                    "created_at": s.created_at.isoformat() if s.created_at else "",
                }
                for s in shipments
            ],
        }
    else:
        all_shipments = list(
            db.scalars(
                select(Shipment)
                .options(selectinload(Shipment.customer))
                .where(Shipment.is_deleted.is_(False))
                .order_by(Shipment.created_at.desc())
            ).all()
        )
        total_co2 = round(sum(s.co2_kg or 0 for s in all_shipments), 4)
        count = len(all_shipments)
        summary = get_carbon_summary(db, period=summary_period)
        summary["total_shipments"] = count
        summary["avg_co2"] = round(total_co2 / count, 4) if count > 0 else 0
        summary["shipments"] = [
            {
                "musteri": s.customer.name if s.customer else (s.customer_name or ""),
                "origin": s.origin or "",
                "destination": s.destination or "",
                "vehicle_type": s.vehicle_type or "",
                "weight_kg": float(s.weight_kg or 0),
                "distance_km": float(s.distance_km or 0),
                "co2_kg": float(s.co2_kg or 0),
                "invoice_amount": float(s.invoice_amount or 0),
                "status": s.status or "",
                "created_at": s.created_at.isoformat() if s.created_at else "",
            }
            for s in all_shipments
        ]
    filename = f"carbon_report_{period}_{_date_suffix()}.xlsx"
    return StreamingResponse(
        export_carbon_report_excel(summary, period),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/carbon/pdf")
def carbon_pdf_endpoint(
    period: str = Query("monthly", pattern="^(monthly|yearly)$"),
    customer_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    _ensure_export_reader(current_user)
    summary_period = "monthly"
    if customer_id:
        customer = db.get(Customer, customer_id)
        shipments = list(
            db.scalars(
                select(Shipment)
                .where(Shipment.customer_id == customer_id, Shipment.is_deleted.is_(False))
                .order_by(Shipment.created_at.desc())
            ).all()
        )
        summary = {
            "total_co2_kg": round(sum(row.co2_kg or 0 for row in shipments), 4),
            "total_co2": round(sum(row.co2_kg or 0 for row in shipments), 4),
            "shipment_count": len(shipments),
            "average_co2_kg": round(sum(row.co2_kg or 0 for row in shipments) / len(shipments), 2) if shipments else 0,
            "by_vehicle": get_vehicle_distribution_from_shipments(shipments),
            "top_routes": get_top_routes_from_shipments(shipments),
        }
    else:
        customer = None
        all_shipments = list(
            db.scalars(
                select(Shipment)
                .where(Shipment.is_deleted.is_(False))
                .order_by(Shipment.created_at.desc())
            ).all()
        )
        raw = get_carbon_summary(db, period=summary_period)
        total_co2 = round(sum(s.co2_kg or 0 for s in all_shipments), 4)
        shipment_count = len(all_shipments)
        avg_co2 = round(total_co2 / shipment_count, 2) if shipment_count > 0 else 0
        summary = {
            "total_co2_kg": total_co2,
            "total_co2": total_co2,
            "shipment_count": shipment_count,
            "average_co2_kg": avg_co2,
            "by_vehicle": get_vehicle_distribution_from_shipments(all_shipments),
            "top_routes": get_top_routes_from_shipments(all_shipments),
        }

    from io import BytesIO

    class _AllCustomers:
        name = "Tum Musteriler"
        id = None

    effective_customer = customer if customer else _AllCustomers()
    pdf_bytes = generate_carbon_report_pdf(effective_customer, summary, period)
    filename = f"cbam_iso14083_{period}_{_date_suffix()}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/customers/csv")
def customers_csv_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    _ensure_export_reader(current_user)
    customers = db.scalars(
        select(Customer)
        .options(selectinload(Customer.shipments))
        .where(Customer.is_active.is_(True))
        .order_by(Customer.created_at.desc())
    ).yield_per(500)
    filename = f"customers_{_date_suffix()}.csv"
    return StreamingResponse(
        export_customers_csv(customers),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@imports_router.post("/customers")
async def import_customers_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_import_manager(current_user)
    content = await _read_import_file(file)
    try:
        rows = generate_import_rows(content, file.filename or "", validate_customer_row)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    success = 0
    details: list[dict] = []
    for row_number, row, error in rows:
        if error:
            details.append({"row": row_number, "error": error})
            continue
        try:
            payload = CustomerCreate(**row)
            existing = get_customer_by_email(db, payload.email) if payload.email else None
            if existing:
                update_customer(db, existing.id, CustomerUpdate(**payload.model_dump()))
            else:
                create_customer(db, payload, background_tasks)
            success += 1
        except (ValidationError, ValueError) as exc:
            details.append({"row": row_number, "error": str(exc)})
    return _import_response(success, details)


@imports_router.post("/shipments")
async def import_shipments_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_import_manager(current_user)
    content = await _read_import_file(file)
    try:
        rows = generate_import_rows(content, file.filename or "", validate_shipment_row)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    success = 0
    details: list[dict] = []
    for row_number, row, error in rows:
        if error:
            details.append({"row": row_number, "error": error})
            continue
        customer = get_customer_by_email(db, row["customer_email"])
        if not customer:
            details.append({"row": row_number, "error": "Musteri email bulunamadi"})
            continue
        try:
            payload = ShipmentCreate(
                customer_id=customer.id,
                customer_name=customer.name,
                origin=row["origin"],
                destination=row["destination"],
                cargo_type=row["cargo_type"],
                tonnage=row["tonnage"],
                weight_kg=row["weight_kg"],
                delivery_date=row["delivery_date"],
                status=row["status"],
            )
            shipment = create_shipment(db, payload, current_user, background_tasks)
            shipment.vehicle_type = row["vehicle_type"]
            shipment.distance_km = row["distance_km"]
            shipment.co2_kg = calculate_emission(db, row["vehicle_type"], row["distance_km"], row["weight_kg"])
            invoice_result = calculate_invoice(row["weight_kg"], shipment.desi, row["distance_km"], row["vehicle_type"])
            if invoice_result:
                shipment.invoice = shipment.invoice_amount = invoice_result["invoice"]
                shipment.cost = shipment.cost_amount = invoice_result["cost"]
                shipment.profit = shipment.profit_amount = invoice_result["profit"]
                shipment.profit_margin = invoice_result["profit_margin"]
            db.add(shipment)
            db.commit()
            success += 1
        except (ValidationError, ValueError) as exc:
            details.append({"row": row_number, "error": str(exc)})
    return _import_response(success, details)


@imports_router.get("/template/customers")
def customer_import_template_endpoint(current_user: User = Depends(get_current_user)) -> StreamingResponse:
    _ensure_import_manager(current_user)
    return StreamingResponse(
        generate_import_template("customers"),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="customer_import_template.xlsx"'},
    )


@imports_router.get("/template/shipments")
def shipment_import_template_endpoint(current_user: User = Depends(get_current_user)) -> StreamingResponse:
    _ensure_import_manager(current_user)
    return StreamingResponse(
        generate_import_template("shipments"),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="shipment_import_template.xlsx"'},
    )
