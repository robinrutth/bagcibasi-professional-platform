from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class EmissionVehicleType(str, Enum):
    panelvan = "panelvan"
    kamyonet = "kamyonet"
    kamyon = "kamyon"
    tir = "tir"
    elektrikli = "elektrikli"


class VehicleStatus(str, Enum):
    Bosta = "Bosta"
    Yukleniyor = "Yukleniyor"
    Yolda = "Yolda"
    Bakimda = "Bakimda"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String, index=True)
    tax_number: Mapped[str | None] = mapped_column(String, index=True)
    sector: Mapped[str | None] = mapped_column(String)
    payment_terms: Mapped[str] = mapped_column(String, default="Vadeli")
    risk_level: Mapped[str] = mapped_column(String, default="Düşük")
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="customer")


class Shipment(Base):
    __tablename__ = "shipments"

    # Shipment records power operation tracking, pricing, carbon, and role-scoped API access.
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    customer_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=True)
    driver_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True, index=True)
    vehicle_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_name: Mapped[str] = mapped_column(String, nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    destination: Mapped[str] = mapped_column(String, nullable=False)
    cargo_type: Mapped[str] = mapped_column(String, nullable=False)
    tonnage: Mapped[float] = mapped_column(Float, nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    desi: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="Hazırlanıyor")
    invoice: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_amount: Mapped[float] = mapped_column(Float, nullable=False)
    invoice_amount: Mapped[float] = mapped_column(Float, nullable=False)
    profit_amount: Mapped[float] = mapped_column(Float, nullable=False)
    profit_margin: Mapped[float] = mapped_column(Float, nullable=False)
    co2_kg: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String, nullable=False)
    ai_recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    customer: Mapped[Customer | None] = relationship(back_populates="shipments")

    @property
    def carbon_emission(self) -> float:
        return self.co2_kg


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    plate_number: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    vehicle_type: Mapped[str] = mapped_column(String, nullable=False)
    capacity_tons: Mapped[float] = mapped_column(Float, nullable=False)
    current_load_tons: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    driver_name: Mapped[str | None] = mapped_column(String)
    driver_phone: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default=VehicleStatus.Bosta.value, index=True)
    current_lat: Mapped[float | None] = mapped_column(Float)
    current_lng: Mapped[float | None] = mapped_column(Float)
    current_shipment_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("shipments.id", ondelete="SET NULL", use_alter=True, name="fk_vehicles_current_shipment_id_shipments"),
        nullable=True,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmissionFactor(Base):
    __tablename__ = "emission_factors"
    __table_args__ = (UniqueConstraint("vehicle_type", name="uq_emission_factors_vehicle_type"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    vehicle_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    co2_per_km: Mapped[float] = mapped_column(Float, nullable=False)
    co2_per_kg_km: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class CashMovement(Base):
    __tablename__ = "cash_movements"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    description: Mapped[str] = mapped_column(String, nullable=False)
    movement_type: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_type: Mapped[str] = mapped_column(String, default="Peşin")
    movement_date: Mapped[date] = mapped_column(Date, default=date.today)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="operation")
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_jti: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    token_jti: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    token_type: Mapped[str] = mapped_column(String, nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
