from datetime import date, datetime
from typing import Optional

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ShipmentCreate(BaseModel):
    vehicle_id: UUID | None = None
    customer_name: str = Field(default="Yeni Müşteri", min_length=2)
    origin: str
    destination: str
    cargo_type: str
    tonnage: float = Field(gt=0, le=26)
    delivery_date: date


class ShipmentResponse(BaseModel):
    id: str | None = None
    vehicle_id: UUID | None = None
    customer_name: str
    origin: str
    destination: str
    cargo_type: str
    tonnage: float
    delivery_date: date
    distance_km: float
    vehicle_type: str
    status: str
    cost_amount: float
    invoice_amount: float
    profit_amount: float
    profit_margin: float
    co2_kg: float
    risk_level: str
    ai_recommendation: str
    created_at: datetime | None = None


class DashboardSummary(BaseModel):
    total_revenue: float
    total_profit: float
    active_operations: int
    delivery_success_rate: float
    total_co2_kg: float
    risky_operations: int


class AiPrompt(BaseModel):
    prompt: str = Field(min_length=5)


class AiAnalysis(BaseModel):
    summary: str
    suggested_vehicle: str
    estimated_price: float
    estimated_profit: float
    estimated_co2_kg: float
    risk_level: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserSummary(BaseModel):
    username: str
    full_name: str
    role: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserSummary


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    access_token: str
    refresh_token: str


class VehicleBase(BaseModel):
    plate_number: str = Field(min_length=3)
    vehicle_type: str = Field(min_length=2)
    capacity_tons: float = Field(gt=0)
    current_load_tons: float = Field(default=0, ge=0)
    driver_name: str | None = None
    driver_phone: str | None = None
    status: str = "Bosta"
    current_lat: float | None = Field(default=None, ge=-90, le=90)
    current_lng: float | None = Field(default=None, ge=-180, le=180)
    current_shipment_id: UUID | None = None
    notes: str | None = None


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    plate_number: str | None = Field(default=None, min_length=3)
    vehicle_type: str | None = Field(default=None, min_length=2)
    capacity_tons: float | None = Field(default=None, gt=0)
    current_load_tons: float | None = Field(default=None, ge=0)
    driver_name: str | None = None
    driver_phone: str | None = None
    status: str | None = None
    current_lat: float | None = Field(default=None, ge=-90, le=90)
    current_lng: float | None = Field(default=None, ge=-180, le=180)
    current_shipment_id: UUID | None = None
    notes: str | None = None


class VehicleResponse(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime


class VehicleListResponse(BaseModel):
    items: list[VehicleResponse]
    total: int


class VehicleStatusUpdate(BaseModel):
    status: str


class VehicleAssign(BaseModel):
    shipment_id: UUID
    load_tons: float = Field(gt=0)


class VehicleLocationUpdate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
