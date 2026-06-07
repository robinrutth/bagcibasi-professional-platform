from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import atan2, cos, radians, sin, sqrt


CITIES: dict[str, tuple[float, float]] = {
    "Manisa": (38.6191, 27.4289),
    "İzmir": (38.4237, 27.1428),
    "Istanbul": (41.0082, 28.9784),
    "İstanbul": (41.0082, 28.9784),
    "Ankara": (39.9334, 32.8597),
    "Bursa": (40.1885, 29.0610),
    "Antalya": (36.8969, 30.7133),
    "Konya": (37.8746, 32.4932),
    "Adana": (37.0000, 35.3213),
    "Gaziantep": (37.0662, 37.3833),
    "Mersin": (36.8121, 34.6415),
}


@dataclass(frozen=True)
class VehicleRule:
    name: str
    max_tonnage: float
    emission_factor: float
    fuel_liter_per_100km: float
    base_cost: float


VEHICLE_RULES = [
    VehicleRule("Kamyonet", 3.5, 0.30, 6.5, 6500),
    VehicleRule("Kamyon", 18.0, 0.60, 12.0, 12000),
    VehicleRule("Tır", 26.0, 0.90, 18.0, 18500),
]


def estimate_distance_km(origin: str, destination: str) -> int:
    start = CITIES.get(origin)
    end = CITIES.get(destination)
    if not start or not end:
        return 100

    radius = 6371
    d_lat = radians(end[0] - start[0])
    d_lon = radians(end[1] - start[1])
    lat1 = radians(start[0])
    lat2 = radians(end[0])
    calc = sin(d_lat / 2) ** 2 + sin(d_lon / 2) ** 2 * cos(lat1) * cos(lat2)
    direct_distance = radius * 2 * atan2(sqrt(calc), sqrt(1 - calc))
    return round(direct_distance * 1.18)


def choose_vehicle(tonnage: float) -> VehicleRule:
    for vehicle in VEHICLE_RULES:
        if tonnage <= vehicle.max_tonnage:
            return vehicle
    return VEHICLE_RULES[-1]


def calculate_operation(
    origin: str,
    destination: str,
    cargo_type: str,
    tonnage: float,
    delivery_date: date,
) -> dict:
    distance_km = estimate_distance_km(origin, destination)
    vehicle = choose_vehicle(tonnage)
    fuel_price = 45
    fuel_cost = distance_km * vehicle.fuel_liter_per_100km * (fuel_price / 100)
    highway_cost = distance_km * (3.2 if distance_km > 250 else 1.2)
    handling_cost = 1800 + tonnage * 220
    cost_amount = round(vehicle.base_cost + fuel_cost + highway_cost + handling_cost, 2)
    margin_multiplier = 1.18 if distance_km > 350 else 1.16
    invoice_amount = round(cost_amount * margin_multiplier, 2)
    profit_amount = round(invoice_amount - cost_amount, 2)
    profit_margin = round(profit_amount / invoice_amount, 4)
    co2_kg = round(distance_km * vehicle.emission_factor * max(1, tonnage / 10), 2)
    risk_level = calculate_risk(delivery_date, profit_margin, distance_km)
    emission_label = classify_emission(co2_kg, distance_km, vehicle.name)
    alternative_vehicle = "Kamyon" if vehicle.name == "Tır" and tonnage <= 18 else vehicle.name

    return {
        "origin": origin,
        "destination": destination,
        "cargo_type": cargo_type,
        "tonnage": tonnage,
        "delivery_date": delivery_date,
        "distance_km": distance_km,
        "vehicle_type": vehicle.name,
        "alternative_vehicle": alternative_vehicle,
        "cost_amount": cost_amount,
        "invoice_amount": invoice_amount,
        "profit_amount": profit_amount,
        "profit_margin": profit_margin,
        "co2_kg": co2_kg,
        "emission_label": emission_label,
        "risk_level": emission_label,
        "ai_recommendation": build_recommendation(
            vehicle.name,
            alternative_vehicle,
            distance_km,
            profit_margin,
            co2_kg,
            risk_level,
        ),
    }


def calculate_risk(delivery_date: date, profit_margin: float, distance_km: int) -> str:
    if delivery_date <= date.today() + timedelta(days=1):
        return "Yüksek"
    if profit_margin < 0.10 or distance_km > 600:
        return "Orta"
    return "Düşük"


def classify_emission(co2_kg: float, distance_km: int, vehicle_type: str) -> str:
    """
    CBAM-compliant emission classification based on ISO 14083
    and GLEC Framework.

    Thresholds per shipment:
    - Düşük (Low):   co2_kg < 100
    - Orta (Medium): co2_kg >= 100 and < 300
    - Yüksek (High): co2_kg >= 300
    """
    if co2_kg < 100:
        return "Düşük"
    if co2_kg < 300:
        return "Orta"
    return "Yüksek"


def build_recommendation(
    vehicle_type: str,
    alternative_vehicle: str,
    distance_km: int,
    profit_margin: float,
    co2_kg: float,
    risk_level: str,
) -> str:
    if alternative_vehicle != vehicle_type:
        return (
            f"Bu yük için {vehicle_type} yerine {alternative_vehicle} daha kârlı olabilir. "
            f"Rota {distance_km} km, kâr marjı %{round(profit_margin * 100)}, "
            f"karbon etkisi {co2_kg} kg CO2 ve risk seviyesi {risk_level}."
        )
    return (
        f"{vehicle_type} bu yük için uygun seçim. Rota {distance_km} km, "
        f"kâr marjı %{round(profit_margin * 100)}, karbon etkisi {co2_kg} kg CO2 "
        f"ve risk seviyesi {risk_level}."
    )
