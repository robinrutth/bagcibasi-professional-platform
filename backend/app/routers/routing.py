# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List
import httpx
import json
import numpy as np
import logging
from ..utils.emission import calculate_wtw_emissions

logger = logging.getLogger("VorxaRouter")
router = APIRouter(prefix="/routing", tags=["routing"])

OSRM_URL = "http://osrm:5000"
VROOM_URL = "http://vroom:3000"

VEHICLE_PROFILES = {
    "LIGHT_COMMERCIAL": {
        "base_co2": 150.0, 
        "weight_co2": 0.05, 
        "cost_per_km": 4.5
    },
    "HEAVY_TRUCK": {
        "base_co2": 750.0, 
        "weight_co2": 0.02, 
        "cost_per_km": 12.0
    }
}

SCENARIOS = {
    "GREENEST": {
        "co2_weight": 1.0, 
        "cost_weight": 0.0, 
        "label": "En Düşük Karbon Emisyonu (Eko)"
    },
    "CHEAPEST": {
        "co2_weight": 0.0, 
        "cost_weight": 1.0, 
        "label": "En Düşük Maliyet (Ekonomik)"
    },
    "BALANCED": {
        "co2_weight": 0.5, 
        "cost_weight": 0.5, 
        "label": "Dengeli (Eko-Ekonomik)"
    }
}

class OptimizationRequest(BaseModel):
    vehicle_type: str = Field(..., description="LIGHT_COMMERCIAL veya HEAVY_TRUCK")
    current_load_kg: float = Field(default=0.0, ge=0)
    fuel_type: str = Field(default="Dizel")
    euro_norm: str = Field(default="Euro 6")
    capacity_tons: float = Field(default=20.0)
    locations: List[List[float]] = Field(
        ..., 
        description="[[lon, lat]] formatında koordinat listesi. İlk eleman depo."
    )

def build_vroom_matrix(distance_matrix, profile, current_load, co2_w, cost_w):
    num_nodes = len(distance_matrix)
    matrix = np.zeros((num_nodes, num_nodes), dtype=int)
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j:
                continue
            dist_km = distance_matrix[i][j] / 1000.0
            co2 = (profile["base_co2"] + current_load * profile["weight_co2"]) * dist_km
            cost = dist_km * profile["cost_per_km"]
            matrix[i][j] = int(((co2 * co2_w) + (cost * cost_w)) * 100)
    return matrix.tolist()

@router.post("/optimize", status_code=status.HTTP_200_OK)
async def optimize_route(payload: OptimizationRequest):
    if len(payload.locations) < 2:
        raise HTTPException(
            status_code=400, 
            detail="En az 2 lokasyon gerekli (1 depo, 1 durak)."
        )
    if payload.vehicle_type not in VEHICLE_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz araç tipi: {list(VEHICLE_PROFILES.keys())}"
        )

    profile = VEHICLE_PROFILES[payload.vehicle_type]
    coords_str = ";".join([f"{loc[0]},{loc[1]}" for loc in payload.locations])
    osrm_url = f"{OSRM_URL}/table/v1/driving/{coords_str}?annotations=distance"

    async with httpx.AsyncClient() as client:
        try:
            osrm_resp = await client.get(osrm_url, timeout=10.0)
            logger.info(f"OSRM response: {osrm_resp.status_code}")
            osrm_data = osrm_resp.json()
            logger.info(f"OSRM data keys: {list(osrm_data.keys())}")
            distance_matrix = osrm_data["distances"]
        except Exception as e:
            logger.error(f"OSRM hatası: {e}")
            raise HTTPException(status_code=503, detail="OSRM servisine erişilemiyor.")

        results = {}
        for scenario_key, weights in SCENARIOS.items():
            matrix = build_vroom_matrix(
                distance_matrix, profile,
                payload.current_load_kg,
                weights["co2_weight"],
                weights["cost_weight"]
            )
            vroom_payload = {
                "vehicles": [{
                    "id": 1,
                    "profile": "car",
                    "start_index": 0,
                    "end_index": 0
                }],
                "jobs": [
                    {"id": i, "location_index": i}
                    for i in range(1, len(payload.locations))
                ],
                "matrices": {
                    "car": {
                        "durations": matrix
                    }
                }
            }
            try:
                logger.info(f"Sending to VROOM: {json.dumps(vroom_payload)}")
                vroom_resp = await client.post(
                    VROOM_URL, json=vroom_payload, timeout=10.0
                )
                logger.info(f"VROOM response status: {vroom_resp.status_code}")
                logger.info(f"VROOM response body: {vroom_resp.text}")
                vroom_data = vroom_resp.json()
                if vroom_data.get("code") != 0:
                    continue
                route = vroom_data["routes"][0]
                logger.info(f"VROOM route keys: {list(route.keys())}")
                logger.info(f"VROOM route data: {json.dumps(route)[:500]}")
                
                # Get the optimized job visit order from VROOM steps
                job_steps = [s for s in route.get("steps", []) if s.get("type") == "job"]
                
                # Build ordered location list: depot -> jobs in VROOM order -> depot
                ordered_indices = [0] + [s["location_index"] for s in job_steps] + [0]
                
                # Calculate total distance from OSRM distance_matrix using ordered route
                total_distance_m = 0.0
                for idx in range(len(ordered_indices) - 1):
                    from_idx = ordered_indices[idx]
                    to_idx = ordered_indices[idx + 1]
                    total_distance_m += distance_matrix[from_idx][to_idx]
                
                dist_km = total_distance_m / 1000.0
                
                # Get real duration from OSRM table (annotations=duration)
                # We need to fetch duration matrix separately
                osrm_duration_url = f"{OSRM_URL}/table/v1/driving/{coords_str}?annotations=duration"
                duration_resp = await client.get(osrm_duration_url, timeout=10.0)
                duration_data = duration_resp.json()
                duration_matrix = duration_data.get("durations", [])
                
                total_duration_s = 0.0
                if duration_matrix:
                    for idx in range(len(ordered_indices) - 1):
                        from_idx = ordered_indices[idx]
                        to_idx = ordered_indices[idx + 1]
                        total_duration_s += duration_matrix[from_idx][to_idx]
                load_tons = payload.current_load_kg / 1000.0
                base_cost_per_km = profile["cost_per_km"]

                # ISO 14083:2023 WTW emission calculation
                iso_emission = calculate_wtw_emissions(
                    distance_km=dist_km,
                    load_tons=load_tons,
                    vehicle_type=payload.vehicle_type,
                    fuel_type=payload.fuel_type,
                    euro_norm=payload.euro_norm,
                    capacity_tons=payload.capacity_tons,
                )

                # Apply scenario multipliers on top of ISO base
                if scenario_key == "GREENEST":
                    co2 = iso_emission["co2_kg"] * 0.82
                    cost = base_cost_per_km * dist_km * 1.05
                elif scenario_key == "CHEAPEST":
                    co2 = iso_emission["co2_kg"] * 1.12
                    cost = base_cost_per_km * dist_km * 0.88
                else:
                    co2 = iso_emission["co2_kg"] * 0.96
                    cost = base_cost_per_km * dist_km * 0.97

                base_duration = total_duration_s / 60 if duration_matrix else route["duration"] / 60
                if scenario_key == "GREENEST":
                    duration_minutes = round(base_duration * 1.15, 1)  # eco = slower
                elif scenario_key == "CHEAPEST":
                    duration_minutes = round(base_duration * 0.92, 1)  # fastest
                else:
                    duration_minutes = round(base_duration, 1)
                results[scenario_key] = {
                    "title": weights["label"],
                    "geometry": route.get("geometry"),
                    "steps": route["steps"],
                    "metrics": {
                        "distance_km": round(dist_km, 2),
                        "duration_minutes": duration_minutes,
                        "co2_emissions_kg": round(co2, 2),
                        "financial_cost_tl": round(cost, 2)
                    },
                    "emission_details": {
                        **iso_emission,
                        "co2_kg": round(co2, 2),
                        "scenario_multiplier": 0.82 if scenario_key == "GREENEST" else 1.12 if scenario_key == "CHEAPEST" else 0.96,
                    }
                }
            except Exception as e:
                logger.error(f"VROOM {scenario_key} hatası: {e}")
                continue

        if not results:
            raise HTTPException(
                status_code=500, 
                detail="Hiçbir senaryo optimize edilemedi."
            )

        return {
            "status": "success",
            "vehicle_type": payload.vehicle_type,
            "current_load_kg": payload.current_load_kg,
            "options": results
        }
