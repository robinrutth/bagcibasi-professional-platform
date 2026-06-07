# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.crud.shipment import get_shipment
from app.database import get_db
from app.models import User
from app.services.carbon_service import (
    calculate_distance_km,
    calculate_emission,
    compare_with_benchmark,
    get_carbon_summary,
    get_coordinates,
    get_route_info,
    get_top_routes_from_shipments,
    get_trend_from_shipments,
    get_vehicle_distribution_from_shipments,
)


router = APIRouter(prefix="/carbon", tags=["carbon"])


class CarbonCalculationRequest(BaseModel):
    vehicle_type: str = Field(min_length=2)
    distance_km: float = Field(ge=0)
    weight_kg: float = Field(ge=0)


# Komple Arac (FTL) Turkiye Spot Piyasa KM Oranlari
KOMPLE_ARAC_BASE_KM_RATE = {
    "Panelvan": 25.0,
    "Kamyonet": 32.0,
    "Kamyon": 48.0,
    "Tır": 65.0,
}

# Araclarin KM Basina Urettigi SAF CO2 Emisyon Standartlari (KG/km)
VEHICLE_BASE_EMISSION_PER_KM = {
    "Panelvan": 0.22,
    "Kamyonet": 0.35,
    "Kamyon": 0.65,
    "Tır": 0.85,
}

MIN_SHIPPING_FEE = 2500.0
DESI_TO_KG_RATIO = 3.0

# Parsiyel (LTL) icin Km ve Desi basina dusen kademeli baz oranlar
DESI_TIER_RATES = [
    {"max_desi": 50, "rate_per_km_per_desi": 0.12},
    {"max_desi": 150, "rate_per_km_per_desi": 0.09},
    {"max_desi": 300, "rate_per_km_per_desi": 0.07},
    {"max_desi": 1000, "rate_per_km_per_desi": 0.02},
    {"max_desi": float("inf"), "rate_per_km_per_desi": 0.015},
]

KOMPLE_ARAC_ESIGI = {
    "Panelvan": 300,
    "Kamyonet": 600,
    "Kamyon": 1500,
    "Tır": 3000,
}

VEHICLE_AVG_SPEED_KMH = {
    "Panelvan": 85,
    "Kamyonet": 80,
    "Kamyon": 75,
    "Tır": 70,
}

LTL_TIME_MULTIPLIER = 1.8

VEHICLE_MAX_DESI = {
    "Panelvan": 300,
    "Kamyonet": 600,
    "Kamyon": 1500,
    "Tır": 3000,
}

FUEL_COST_FACTORS = {"Dizel": 1.0, "Benzin": 1.1, "Elektrikli": 0.70, "Biyodizel": 0.9}
FUEL_EMISSION_FACTORS = {"Dizel": 1.0, "Benzin": 1.12, "Elektrikli": 0.15, "Biyodizel": 0.65}


class LogisticsCalculationRequest(BaseModel):
    distance_km: float = Field(..., gt=0, description="Mesafe 0'dan buyuk olmalidir")
    weight_kg: float = Field(..., gt=0, description="Fiziksel agirlik 0'dan buyuk olmalidir")
    desi: float = Field(..., gt=0, description="Desi degeri 0'dan buyuk olmalidir")
    vehicle_type: Literal["Panelvan", "Kamyonet", "Kamyon", "Tır"] = "Kamyon"
    fuel_type: Literal["Dizel", "Benzin", "Elektrikli", "Biyodizel"] = "Dizel"
    shipment_type: Optional[str] = "LTL"


def _date_filters(start_date: date | None, end_date: date | None) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="start_date end_date değerinden büyük olamaz.")
    return {"start_date": start_date, "end_date": end_date}


@router.get("/summary", dependencies=[Depends(require_roles("manager"))])
def summary_endpoint(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return get_carbon_summary(db, _date_filters(start_date, end_date))


@router.get("/by-vehicle", dependencies=[Depends(require_roles("manager"))])
def by_vehicle_endpoint(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    summary = get_carbon_summary(db, _date_filters(start_date, end_date))
    return get_vehicle_distribution_from_shipments([]) if summary["total_co2"] == 0 else summary["by_vehicle"]


@router.get("/trend", dependencies=[Depends(require_roles("manager"))])
def trend_endpoint(
    period: Literal["daily", "weekly", "monthly"] = Query("daily"),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    summary = get_carbon_summary(db, _date_filters(start_date, end_date), period=period)
    return get_trend_from_shipments([], period) if summary["total_co2"] == 0 else summary["trend"]


@router.get("/top-routes", dependencies=[Depends(require_roles("manager"))])
def top_routes_endpoint(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    summary = get_carbon_summary(db, _date_filters(start_date, end_date))
    return get_top_routes_from_shipments([]) if summary["total_co2"] == 0 else summary["top_routes"]


@router.get("/distance", dependencies=[Depends(require_roles("operation", "manager"))])
def distance_endpoint(
    origin: str = Query(min_length=2),
    destination: str = Query(min_length=2),
    _: User = Depends(get_current_user),
) -> dict:
    distance_km = calculate_distance_km(origin, destination)
    origin_coords = get_coordinates(origin)
    destination_coords = get_coordinates(destination)
    return {
        "origin": origin,
        "destination": destination,
        "distance_km": distance_km,
        "origin_coords": origin_coords,
        "destination_coords": destination_coords,
    }


@router.get("/route", dependencies=[Depends(require_roles("operation", "manager"))])
def route_endpoint(
    origin: str = Query(min_length=2),
    destination: str = Query(min_length=2),
    _: User = Depends(get_current_user),
) -> dict:
    origin_coords = get_coordinates(origin)
    destination_coords = get_coordinates(destination)
    route_info = get_route_info(origin_coords, destination_coords) if origin_coords and destination_coords else None
    return {
        "origin": origin,
        "destination": destination,
        "distance_km": route_info["distance_km"] if route_info else None,
        "duration_minutes": route_info["duration_minutes"] if route_info else None,
        "geometry": route_info["geometry"] if route_info else None,
        "origin_coords": origin_coords,
        "destination_coords": destination_coords,
    }


@router.get("/geocode", dependencies=[Depends(require_roles("operation", "manager"))])
def geocode_endpoint(
    location: str = Query(min_length=2),
    _: User = Depends(get_current_user),
) -> dict:
    coords = get_coordinates(location)
    return {
        "location": location,
        "lat": coords["lat"] if coords else None,
        "lon": coords["lon"] if coords else None,
    }


@router.post("/calculate", dependencies=[Depends(require_roles("operation", "manager"))])
def calculate_endpoint(
    payload: CarbonCalculationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    co2 = calculate_emission(db, payload.vehicle_type, payload.distance_km, payload.weight_kg)
    return {
        "vehicle_type": payload.vehicle_type,
        "distance_km": payload.distance_km,
        "weight_kg": payload.weight_kg,
        "carbon_emission": co2,
        "benchmark": compare_with_benchmark(co2, payload.distance_km),
    }


@router.post("/logistics-calculate", dependencies=[Depends(require_roles("operation", "manager"))])
def logistics_calculate_endpoint(
    payload: LogisticsCalculationRequest,
    _: User = Depends(get_current_user),
) -> dict:
    desi_as_kg = payload.desi * DESI_TO_KG_RATIO
    if desi_as_kg > payload.weight_kg:
        chargeable_weight = desi_as_kg
        chargeable_basis = "desi"
    else:
        chargeable_weight = payload.weight_kg
        chargeable_basis = "weight"

    safe_vehicle = payload.vehicle_type or "Kamyon"
    safe_fuel = payload.fuel_type or "Dizel"

    vehicle_threshold = KOMPLE_ARAC_ESIGI.get(safe_vehicle, 1000)
    if payload.shipment_type == "FTL":
        pricing_type = "FTL"
        calculated_cost = payload.distance_km * KOMPLE_ARAC_BASE_KM_RATE.get(safe_vehicle, 15.0)
    else:
        pricing_type = "LTL"
        selected_rate = 0.05
        for tier in DESI_TIER_RATES:
            if payload.desi <= tier["max_desi"]:
                selected_rate = tier["rate_per_km_per_desi"]
                break
        calculated_cost = payload.distance_km * payload.desi * selected_rate

    min_fee_applied = False
    if calculated_cost < MIN_SHIPPING_FEE:
        calculated_cost = MIN_SHIPPING_FEE
        min_fee_applied = True

    cost_f_factor = FUEL_COST_FACTORS.get(safe_fuel, 1.0)

    if pricing_type == "FTL":
        final_cost = calculated_cost * cost_f_factor
        vehicle_cost_factor = 1.0
    else:
        vehicle_cost_factor = {"Panelvan": 0.6, "Kamyonet": 0.8, "Kamyon": 1.2, "Tır": 1.6}.get(safe_vehicle, 1.0)
        ltl_cost = calculated_cost * vehicle_cost_factor * cost_f_factor
        ftl_cost = payload.distance_km * KOMPLE_ARAC_BASE_KM_RATE.get(safe_vehicle, 15.0) * cost_f_factor
        final_cost = min(ltl_cost, ftl_cost)

    base_veh_emission = VEHICLE_BASE_EMISSION_PER_KM.get(safe_vehicle, 0.65)
    weight_ton = chargeable_weight / 1000.0
    emission_f_factor = FUEL_EMISSION_FACTORS.get(safe_fuel, 1.0)
    total_emission = (payload.distance_km * base_veh_emission) * (1 + (weight_ton * 0.15)) * emission_f_factor
    if pricing_type == "LTL":
        load_ratio = min(payload.desi / VEHICLE_MAX_DESI.get(safe_vehicle, 1500), 1.0)
        total_emission = total_emission * load_ratio

    calculated_minutes = int((payload.distance_km / 85.0) * 60)

    return {
        "status": "success",
        "pricing_type": "FTL (Komple Araç)" if pricing_type == "FTL" else "LTL (Parsiyel / Parça)",
        "min_fee_applied": min_fee_applied,
        "estimated_duration": {
            "minutes": calculated_minutes,
        },
        "chargeable_weight": {
            "value_kg": chargeable_weight,
            "basis": chargeable_basis,
        },
        "pricing": {
            "total_cost": round(final_cost, 2),
            "applied_factors": {"vehicle": 1.0 if pricing_type == "FTL" else vehicle_cost_factor, "fuel": cost_f_factor},
        },
        "sustainability": {
            "total_emission_co2e": round(total_emission, 6),
            "applied_factors": {"vehicle": base_veh_emission, "fuel": emission_f_factor},
        },
    }


@router.get("/shipment/{shipment_id}", dependencies=[Depends(require_roles("manager"))])
def shipment_carbon_endpoint(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    shipment = get_shipment(db, shipment_id)
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sevkiyat bulunamadı")
    return {
        "shipment_id": str(shipment.id),
        "vehicle_type": shipment.vehicle_type,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "distance_km": shipment.distance_km,
        "weight_kg": shipment.weight_kg,
        "carbon_emission": shipment.co2_kg,
        "benchmark": compare_with_benchmark(shipment.co2_kg, shipment.distance_km),
    }
