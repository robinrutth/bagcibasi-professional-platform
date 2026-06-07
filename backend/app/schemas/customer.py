from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.shipment import ShipmentResponse


class CustomerBase(BaseModel):
    name: str = Field(min_length=2)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = None
    city: str | None = Field(default=None, max_length=80)
    tax_number: str | None = Field(default=None, max_length=40)
    sector: str | None = None
    payment_terms: str = "Vadeli"
    risk_level: str = "Dusuk"
    notes: str | None = None
    is_active: bool = True


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = None
    city: str | None = Field(default=None, max_length=80)
    tax_number: str | None = Field(default=None, max_length=40)
    sector: str | None = None
    payment_terms: str | None = None
    risk_level: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class CustomerResponse(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    skip: int
    limit: int


class CustomerWithShipments(CustomerResponse):
    shipments: list[ShipmentResponse] = Field(default_factory=list)


class CustomerCarbonStats(BaseModel):
    customer_id: UUID
    total_co2_kg: float
    shipment_count: int
    average_co2_kg: float
    by_vehicle: list[dict]
    top_routes: list[dict]
