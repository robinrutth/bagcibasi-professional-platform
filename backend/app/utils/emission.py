"""WTW emission calculator based on ISO 14083:2023."""

FUEL_EMISSION_FACTORS = {
    "Dizel": 3.24,      # kg CO2e/litre (WTW, EMEP/EEA 2023)
    "Benzin": 2.87,     # kg CO2e/litre (WTW)
    "Elektrikli": 0.47, # kg CO2e/kWh (TR grid mix 2023)
    "Biyodizel": 1.98,  # kg CO2e/litre (WTW, B100)
}

BASE_CONSUMPTION = {
    "HEAVY_TRUCK": {
        "Euro 3": 34.0,
        "Euro 4": 31.0,
        "Euro 5": 28.5,
        "Euro 6": 26.0,
        "Elektrikli": 120.0,  # kWh/100km
    },
    "LIGHT_COMMERCIAL": {
        "Euro 3": 12.0,
        "Euro 4": 10.5,
        "Euro 5": 9.5,
        "Euro 6": 8.5,
        "Elektrikli": 25.0,  # kWh/100km
    }
}


def get_load_factor(load_tons: float, capacity_tons: float) -> float:
    """
    Returns consumption multiplier based on load ratio.
    Empty = 0.72, Full = 1.28 (linear interpolation)
    Based on ISO 14083:2023 Section 6.3
    """
    ratio = min(load_tons / capacity_tons, 1.0) if capacity_tons > 0 else 0.5
    return 0.72 + (ratio * 0.56)


def calculate_wtw_emissions(
    distance_km: float,
    load_tons: float,
    vehicle_type: str,
    fuel_type: str,
    euro_norm: str = "Euro 6",
    capacity_tons: float = 20.0,
) -> dict:
    """
    Calculate WTW emissions per ISO 14083:2023 standard.
    Returns detailed emission breakdown.
    """
    consumption_map = BASE_CONSUMPTION.get(vehicle_type, BASE_CONSUMPTION["HEAVY_TRUCK"])
    base_consumption = consumption_map.get(euro_norm, consumption_map.get("Euro 6", 26.0))

    load_factor = get_load_factor(load_tons, capacity_tons)
    adjusted_consumption = base_consumption * load_factor

    emission_factor = FUEL_EMISSION_FACTORS.get(fuel_type, FUEL_EMISSION_FACTORS["Dizel"])

    if fuel_type == "Elektrikli":
        fuel_consumed = (adjusted_consumption * distance_km) / 100.0  # kWh
        co2_kg = fuel_consumed * emission_factor
    else:
        fuel_consumed = (adjusted_consumption * distance_km) / 100.0  # litres
        co2_kg = fuel_consumed * emission_factor

    load_ratio = min(load_tons / capacity_tons, 1.0) if capacity_tons > 0 else 0.5
    efficiency_gco2_per_ton_km = (co2_kg * 1000) / (load_tons * distance_km) if load_tons > 0 and distance_km > 0 else 0.0

    return {
        "co2_kg": round(co2_kg, 2),
        "methodology": "ISO 14083:2023",
        "calculation_type": "WTW (Well-to-Wheel)",
        "emission_factor_source": "EMEP/EEA 2023, IPCC AR6",
        "fuel_consumed_liters": round(fuel_consumed, 2),
        "fuel_type": fuel_type,
        "euro_norm": euro_norm,
        "load_factor": round(load_factor, 3),
        "load_ratio_percent": round(load_ratio * 100, 1),
        "efficiency_metric": "gCO2e/ton-km",
        "efficiency_value": round(efficiency_gco2_per_ton_km, 1),
        "distance_km": distance_km,
        "load_tons": load_tons,
    }
