from datetime import date, datetime

from pydantic import BaseModel, Field


class ShipmentCreate(BaseModel):
    customer_name: str = Field(default="Yeni Müşteri", min_length=2)
    origin: str
    destination: str
    cargo_type: str
    tonnage: float = Field(gt=0, le=26)
    distance_km: float | None = Field(default=None, ge=0)
    delivery_date: date


class ShipmentResponse(BaseModel):
    id: str | None = None
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
    username: str | None = None
    full_name: str | None = None
    password: str | None = None


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
