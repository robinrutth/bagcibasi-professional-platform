from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ShipmentBase(BaseModel):
    # API shipment schema shared by create, update, and response models.
    customer_id: UUID | None = None
    driver_id: UUID | None = None
    vehicle_id: UUID | None = None
    customer_name: str = Field(min_length=2)
    origin: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    cargo_type: str = Field(min_length=2)
    tonnage: float = Field(gt=0, le=26)
    weight_kg: float | None = Field(default=None, gt=0)
    desi: float | None = Field(default=None, ge=0)
    distance_km: float | None = Field(default=None, ge=0)
    vehicle_type: str | None = None
    delivery_date: date
    status: str = "Hazırlanıyor"


class ShipmentCreate(ShipmentBase):
    invoice_amount: float | None = None
    profit_amount: float | None = None
    co2_kg: float | None = None


class ShipmentUpdate(BaseModel):
    customer_id: UUID | None = None
    driver_id: UUID | None = None
    vehicle_id: UUID | None = None
    customer_name: str | None = Field(default=None, min_length=2)
    origin: str | None = Field(default=None, min_length=2)
    destination: str | None = Field(default=None, min_length=2)
    cargo_type: str | None = Field(default=None, min_length=2)
    tonnage: float | None = Field(default=None, gt=0, le=26)
    weight_kg: float | None = Field(default=None, gt=0)
    desi: float | None = Field(default=None, ge=0)
    delivery_date: date | None = None
    distance_km: float | None = Field(default=None, ge=0)
    vehicle_type: str | None = None
    status: str | None = None
    invoice: float | None = Field(default=None, ge=0)
    cost: float | None = Field(default=None, ge=0)
    profit: float | None = None
    cost_amount: float | None = Field(default=None, ge=0)
    invoice_amount: float | None = Field(default=None, ge=0)
    profit_amount: float | None = None
    profit_margin: float | None = None
    co2_kg: float | None = Field(default=None, ge=0)
    carbon_emission: float | None = Field(default=None, ge=0)
    risk_level: str | None = None
    ai_recommendation: str | None = None


class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID | None = None
    driver_id: UUID | None = None
    vehicle_id: UUID | None = None
    customer_name: str
    origin: str
    destination: str
    cargo_type: str
    tonnage: float
    weight_kg: float | None = None
    desi: float | None = None
    delivery_date: date
    distance_km: float
    vehicle_type: str
    status: str
    invoice: float | None = None
    cost: float | None = None
    profit: float | None = None
    cost_amount: float
    invoice_amount: float
    profit_amount: float
    profit_margin: float
    co2_kg: float
    carbon_emission: float
    risk_level: str
    ai_recommendation: str
    created_at: datetime
    updated_at: datetime


class ShipmentListResponse(BaseModel):
    items: list[ShipmentResponse]
    total: int
    skip: int
    limit: int
