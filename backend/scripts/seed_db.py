from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env", override=False)

from app.auth import hash_password
from app.database import SessionLocal
from app.models import Customer, User, Vehicle
from app.services.carbon_service import DEFAULT_EMISSION_FACTORS


ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@bagcibasi.com"
ADMIN_PASSWORD = "admin123"
SYSTEM_ROLES = ("admin", "manager", "driver", "viewer")
VEHICLE_TYPES = ("panelvan", "kamyonet", "kamyon", "tir", "elektrikli")
EMISSION_FACTORS = DEFAULT_EMISSION_FACTORS
SYSTEM_CONFIG = {
    "platform_name": "Bağcıbaşı Lojistik AI",
    "version": "1.0.0",
}


SAMPLE_CUSTOMERS = [
    {
        "name": "Ege Tekstil A.S.",
        "email": "operasyon@egetekstil.com",
        "phone": "+90 232 555 10 10",
        "address": "Ataturk OSB 10001 Sokak No:12",
        "city": "Izmir",
        "tax_number": "1234567890",
        "sector": "Tekstil",
        "payment_terms": "30 gun",
        "risk_level": "Dusuk",
    },
    {
        "name": "Marmara Gida Lojistik",
        "email": "lojistik@marmaragida.com",
        "phone": "+90 212 555 22 22",
        "address": "Hadimkoy Sanayi Bolgesi",
        "city": "Istanbul",
        "tax_number": "2234567890",
        "sector": "Gida",
        "payment_terms": "Pesin",
        "risk_level": "Orta",
    },
    {
        "name": "Anadolu Makine",
        "email": "sevkiyat@anadolumakine.com",
        "phone": "+90 312 555 33 33",
        "address": "OSTIM Mahallesi 1200 Cadde",
        "city": "Ankara",
        "tax_number": "3234567890",
        "sector": "Makine",
        "payment_terms": "45 gun",
        "risk_level": "Dusuk",
    },
    {
        "name": "Akdeniz Kimya",
        "email": "planlama@akdenizkimya.com",
        "phone": "+90 242 555 44 44",
        "address": "Organize Sanayi Bolgesi 3. Kisim",
        "city": "Antalya",
        "tax_number": "4234567890",
        "sector": "Kimya",
        "payment_terms": "60 gun",
        "risk_level": "Yuksek",
    },
]

SAMPLE_VEHICLES = [
    {
        "plate_number": "45 BL 002",
        "vehicle_type": "Kamyon",
        "capacity_tons": 22,
        "current_load_tons": 18,
        "driver_name": "Ahmet Usta",
        "driver_phone": "+90 555 450 02 02",
        "status": "Yolda",
        "current_lat": 39.9,
        "current_lng": 32.8,
    },
    {
        "plate_number": "35 BL 001",
        "vehicle_type": "Kamyonet",
        "capacity_tons": 3.5,
        "current_load_tons": 0,
        "driver_name": "Mehmet Şoför",
        "driver_phone": "+90 555 350 01 01",
        "status": "Bosta",
        "current_lat": 38.6,
        "current_lng": 27.4,
    },
    {
        "plate_number": "34 BL 003",
        "vehicle_type": "Tır",
        "capacity_tons": 26,
        "current_load_tons": 0,
        "driver_name": "Ali Şoför",
        "driver_phone": "+90 555 340 03 03",
        "status": "Bakimda",
        "current_lat": 39.0,
        "current_lng": 35.0,
    },
]


def get_model(name: str) -> type[Any] | None:
    import app.models as models

    model = getattr(models, name, None)
    if model is None:
        print(f"[skip] {name} modeli bulunamadı.")
    return model


def first_existing_attr(model: type[Any], names: tuple[str, ...]) -> str | None:
    for name in names:
        if hasattr(model, name):
            return name
    return None


def create_if_missing_by_field(db: Session, model: type[Any], field_name: str, value: Any, **extra_fields: Any) -> bool:
    field = getattr(model, field_name)
    existing = db.scalar(select(model).where(field == value))
    if existing:
        print(f"[ok] {model.__name__} zaten var: {value}")
        return False

    payload = {field_name: value, **extra_fields}
    db.add(model(**payload))
    print(f"[add] {model.__name__} eklendi: {value}")
    return True


def seed_admin_user(db: Session) -> None:
    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    if user_count > 0:
        existing_admin = db.scalar(select(User).where(User.username == ADMIN_USERNAME))
        if existing_admin:
            print("[ok] Admin kullanıcısı mevcut, değiştirilmedi.")
        else:
            print("[skip] Kullanıcı tablosunda kayıt var; admin otomatik oluşturulmadı.")
        return

    payload: dict[str, Any] = {
        "username": ADMIN_USERNAME,
        "full_name": "Admin",
        "role": "admin",
        "password_hash": hash_password(ADMIN_PASSWORD),
        "is_active": True,
    }
    if hasattr(User, "email"):
        payload["email"] = ADMIN_EMAIL
    else:
        print("[skip] User.email alanı bulunamadı; admin e-posta değeri yazılmadı.")

    db.add(User(**payload))
    print("[add] İlk admin kullanıcısı oluşturuldu.")


def seed_roles(db: Session) -> None:
    Role = get_model("Role")
    if Role is None:
        return

    field_name = first_existing_attr(Role, ("name", "code", "slug", "key"))
    if field_name is None:
        print("[skip] Role modeli için name/code/slug/key alanı bulunamadı.")
        return

    for role in SYSTEM_ROLES:
        create_if_missing_by_field(db, Role, field_name, role)


def seed_vehicle_types(db: Session) -> None:
    VehicleType = get_model("VehicleType")
    if VehicleType is None:
        return

    field_name = first_existing_attr(VehicleType, ("name", "code", "slug", "key"))
    if field_name is None:
        print("[skip] VehicleType modeli için name/code/slug/key alanı bulunamadı.")
        return

    for vehicle_type in VEHICLE_TYPES:
        create_if_missing_by_field(db, VehicleType, field_name, vehicle_type)


def seed_emission_factors(db: Session) -> None:
    EmissionFactor = get_model("EmissionFactor")
    if EmissionFactor is None:
        return

    vehicle_field = first_existing_attr(EmissionFactor, ("vehicle_type", "vehicle_type_name", "name", "code"))
    if vehicle_field is None or not hasattr(EmissionFactor, "co2_per_km") or not hasattr(EmissionFactor, "co2_per_kg_km"):
        print("[skip] EmissionFactor modeli için beklenen alanlar bulunamadı.")
        return

    for vehicle_type, values in EMISSION_FACTORS.items():
        field = getattr(EmissionFactor, vehicle_field)
        existing = db.scalar(select(EmissionFactor).where(field == vehicle_type))
        payload = {
            "co2_per_km": float(values["co2_per_km"]),
            "co2_per_kg_km": float(values["co2_per_kg_km"]),
            "description": str(values["description"]),
        }
        if existing:
            existing.co2_per_km = payload["co2_per_km"]
            existing.co2_per_kg_km = payload["co2_per_kg_km"]
            existing.description = payload["description"]
            print(f"[ok] EmissionFactor güncel: {vehicle_type}")
            continue
        db.add(EmissionFactor(**{vehicle_field: vehicle_type, **payload}))
        print(f"[add] EmissionFactor eklendi: {vehicle_type}")


def seed_system_config(db: Session) -> None:
    ConfigModel = get_model("SystemConfig") or get_model("Settings")
    if ConfigModel is None:
        return

    key_field = first_existing_attr(ConfigModel, ("key", "name", "code"))
    value_field = first_existing_attr(ConfigModel, ("value", "setting_value"))
    if key_field is None or value_field is None:
        print("[skip] SystemConfig/Settings modeli için key/value alanları bulunamadı.")
        return

    for key, value in SYSTEM_CONFIG.items():
        create_if_missing_by_field(db, ConfigModel, key_field, key, **{value_field: value})


def seed_customers(db: Session) -> None:
    for payload in SAMPLE_CUSTOMERS:
        existing = db.scalar(select(Customer).where(Customer.email == payload["email"]))
        if existing:
            print(f"[ok] Customer zaten var: {payload['name']}")
            continue
        db.add(Customer(**payload))
        print(f"[add] Customer eklendi: {payload['name']}")


def seed_vehicles(db: Session) -> None:
    for payload in SAMPLE_VEHICLES:
        existing = db.scalar(select(Vehicle).where(Vehicle.plate_number == payload["plate_number"]))
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            existing.is_deleted = False
            print(f"[ok] Vehicle güncel: {payload['plate_number']}")
            continue
        db.add(Vehicle(**payload))
        print(f"[add] Vehicle eklendi: {payload['plate_number']}")


def main() -> int:
    db = SessionLocal()
    try:
        print("[seed] Veritabanı seed işlemi başladı.")
        seed_admin_user(db)
        seed_roles(db)
        seed_vehicle_types(db)
        seed_emission_factors(db)
        seed_customers(db)
        seed_vehicles(db)
        seed_system_config(db)
        db.commit()
        print("[success] Seed işlemi başarıyla tamamlandı.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[error] Seed işlemi geri alındı: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
