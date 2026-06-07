import json

from sqlalchemy import select
import pytest
from urllib.error import URLError

from app.models import EmissionFactor
from app.routers import carbon as carbon_router
from app.services import carbon_service
from app.services.carbon_service import calculate_distance_km, calculate_emission, get_coordinates, get_route_info, haversine_distance_km, seed_default_emission_factors


class _FakeNominatimResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self):
        return self.payload


def _reset_geocode_state():
    carbon_service._GEOCODE_CACHE.clear()
    carbon_service._LAST_GEOCODE_REQUEST_AT = 0


def test_calculate_emission_accuracy(client, db_session, auth_headers):
    response = client.post(
        "/api/v1/carbon/calculate",
        json={"vehicle_type": "truck", "distance_km": 100, "weight_kg": 1000},
        headers=auth_headers("admin"),
    )
    assert response.status_code == 200
    assert response.json()["carbon_emission"] == 42
    assert response.json()["benchmark"]["label"] == "yüksek"
    assert calculate_emission(db_session, "truck", 100, 1000) == 42


def test_logistics_calculate_uses_desi_and_factors(client, auth_headers):
    response = client.post(
        "/api/v1/carbon/logistics-calculate",
        json={
            "distance_km": 100,
            "weight_kg": 50,
            "desi": 30,
            "vehicle_type": "Kamyonet",
            "fuel_type": "Elektrikli",
        },
        headers=auth_headers("admin"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chargeable_weight"] == {"value_kg": 90, "basis": "desi"}
    assert payload["pricing"]["total_cost"] == 10710
    assert payload["pricing"]["applied_factors"] == {"vehicle": 0.7, "fuel": 0.85}
    assert payload["sustainability"]["total_emission_co2e"] == 378
    assert payload["sustainability"]["applied_factors"] == {"vehicle": 0.7, "fuel": 0.4}


def test_carbon_summary_breakdowns_trend_and_shipment_detail(client, auth_headers, sample_shipments):
    response = client.get("/api/v1/carbon/summary?start_date=2026-05-01&end_date=2026-05-31", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert response.json()["total_co2"] == 434

    response = client.get("/api/v1/carbon/by-vehicle", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert response.json()[0] == {"vehicle_type": "truck", "co2": 434}

    response = client.get("/api/v1/carbon/trend?period=daily", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert response.json() == [{"period": "2026-05-20", "co2": 434}]

    response = client.get("/api/v1/carbon/trend?period=monthly", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert response.json() == [{"period": "2026-05", "co2": 434}]

    response = client.get("/api/v1/carbon/top-routes", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert response.json()[0]["origin"] == "Manisa"
    assert response.json()[0]["co2"] == 320

    response = client.get(f"/api/v1/carbon/shipment/{sample_shipments[0].id}", headers=auth_headers("viewer"))
    assert response.status_code == 200
    assert response.json()["carbon_emission"] == 42

    response = client.get("/api/v1/carbon/summary")
    assert response.status_code == 401


def test_carbon_boundary_values(client, auth_headers):
    response = client.post(
        "/api/v1/carbon/calculate",
        json={"vehicle_type": "truck", "distance_km": 0, "weight_kg": 1000},
        headers=auth_headers("admin"),
    )
    assert response.status_code == 200
    assert response.json()["carbon_emission"] == 0
    assert response.json()["benchmark"]["deviation_percent"] == 0

    response = client.post(
        "/api/v1/carbon/calculate",
        json={"vehicle_type": "truck", "distance_km": 100, "weight_kg": 0},
        headers=auth_headers("admin"),
    )
    assert response.status_code == 200
    assert response.json()["carbon_emission"] == 27

    response = client.post(
        "/api/v1/carbon/calculate",
        json={"vehicle_type": "truck", "distance_km": -1, "weight_kg": 1000},
        headers=auth_headers("admin"),
    )
    assert response.status_code == 422


def test_seeded_emission_factors_are_idempotent(db_session):
    seed_default_emission_factors(db_session)
    seed_default_emission_factors(db_session)
    db_session.commit()
    rows = db_session.scalars(select(EmissionFactor).order_by(EmissionFactor.vehicle_type)).all()
    assert [row.vehicle_type for row in rows] == ["bicycle", "electric", "minivan", "motorcycle", "truck"]
    assert db_session.scalar(select(EmissionFactor).where(EmissionFactor.vehicle_type == "truck")).co2_per_km == 0.27


def test_geocode_finds_manisa_coordinates(monkeypatch):
    _reset_geocode_state()

    def fake_urlopen(request, timeout=5):
        assert request.get_header("User-agent") == carbon_service.NOMINATIM_USER_AGENT
        return _FakeNominatimResponse(b'[{"lat":"38.6140","lon":"27.4296"}]')

    monkeypatch.setattr(carbon_service, "urlopen", fake_urlopen)

    coords = get_coordinates("Manisa")
    assert coords == {"lat": 38.614, "lon": 27.4296}
    assert get_coordinates("Manisa") == coords


def test_manisa_istanbul_distance_is_reasonable(monkeypatch):
    _reset_geocode_state()
    coords = {
        "manisa": {"lat": 38.614, "lon": 27.4296},
        "istanbul": {"lat": 41.0082, "lon": 28.9784},
        "i̇stanbul": {"lat": 41.0082, "lon": 28.9784},
    }
    monkeypatch.setattr(carbon_service, "get_coordinates", lambda location: coords.get(location.strip().lower()))

    distance = calculate_distance_km("Manisa", "İstanbul")
    assert distance is not None
    assert 300 <= distance <= 500


def test_geocode_returns_none_when_location_is_missing(monkeypatch):
    _reset_geocode_state()
    monkeypatch.setattr(carbon_service, "urlopen", lambda *_, **__: _FakeNominatimResponse(b"[]"))

    assert get_coordinates("Bulunmayan Yer") is None


def test_haversine_calculation_is_correct():
    distance = haversine_distance_km({"lat": 38.614, "lon": 27.4296}, {"lat": 41.0082, "lon": 28.9784})
    assert 295 <= distance <= 300


def test_geocode_rate_limit_waits_between_requests(monkeypatch):
    _reset_geocode_state()
    sleeps = []
    responses = iter(
        [
            _FakeNominatimResponse(b'[{"lat":"38.6140","lon":"27.4296"}]'),
            _FakeNominatimResponse(b'[{"lat":"41.0082","lon":"28.9784"}]'),
        ]
    )
    times = iter([10.0, 10.0, 10.2, 10.2])

    monkeypatch.setattr(carbon_service, "urlopen", lambda *_, **__: next(responses))
    monkeypatch.setattr(carbon_service.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(carbon_service.time, "sleep", lambda seconds: sleeps.append(seconds))

    assert get_coordinates("Manisa") is not None
    assert get_coordinates("İstanbul") is not None
    assert sleeps == [pytest.approx(0.8)]


def test_route_endpoint_returns_ors_route(client, auth_headers, monkeypatch):
    origin = {"lat": 38.614, "lon": 27.4296}
    destination = {"lat": 41.0082, "lon": 28.9784}
    geometry = {"type": "LineString", "coordinates": [[27.4296, 38.614], [28.9784, 41.0082]]}

    monkeypatch.setattr(carbon_router, "get_coordinates", lambda location: origin if location == "Manisa" else destination)
    monkeypatch.setattr(
        carbon_router,
        "get_route_info",
        lambda *_: {"distance_km": 432.4, "duration_minutes": 252.0, "geometry": geometry},
    )

    response = client.get("/api/v1/carbon/route?origin=Manisa&destination=Istanbul", headers=auth_headers("viewer"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["distance_km"] == 432.4
    assert payload["duration_minutes"] == 252.0
    assert payload["geometry"] == geometry
    assert payload["origin_coords"] == origin
    assert payload["destination_coords"] == destination


def test_route_info_falls_back_to_haversine_when_ors_fails(monkeypatch):
    monkeypatch.setenv("ORS_API_KEY", "test-key")
    monkeypatch.setattr(carbon_service, "urlopen", lambda *_, **__: (_ for _ in ()).throw(URLError("ORS down")))

    route = get_route_info({"lat": 38.614, "lon": 27.4296}, {"lat": 41.0082, "lon": 28.9784})

    assert route is not None
    assert 300 <= route["distance_km"] <= 500
    assert route["duration_minutes"] is not None
    assert route["geometry"]["type"] == "LineString"


def test_route_info_returns_geometry_from_ors(monkeypatch):
    monkeypatch.setenv("ORS_API_KEY", "test-key")
    payload = {
        "routes": [
            {
                "summary": {"distance": 342000, "duration": 15120},
                "geometry": {"type": "LineString", "coordinates": [[27.4296, 38.614], [28.9784, 41.0082]]},
            }
        ]
    }

    monkeypatch.setattr(carbon_service, "urlopen", lambda *_, **__: _FakeNominatimResponse(json.dumps(payload).encode("utf-8")))

    route = get_route_info({"lat": 38.614, "lon": 27.4296}, {"lat": 41.0082, "lon": 28.9784})

    assert route == {
        "distance_km": 342.0,
        "duration_minutes": 252.0,
        "geometry": {"type": "LineString", "coordinates": [[27.4296, 38.614], [28.9784, 41.0082]]},
    }
