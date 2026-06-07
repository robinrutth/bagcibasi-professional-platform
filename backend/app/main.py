# -*- coding: utf-8 -*-
import re
from datetime import date, datetime, timedelta

from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    require_roles,
    revoke_access_token,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from .calculations import CITIES, calculate_operation, choose_vehicle
from .config import get_settings
from .crud import get_vehicles
from .database import Base, SessionLocal, engine, get_db
from .import_service import import_operations_excel
from .models import RefreshToken, RevokedToken, User
from .repository import create_shipment, dashboard_summary, finance_summary, list_shipments, list_users, seed_database
from .routers import vehicles_router
from .routers.carbon import router as carbon_router
from .routers.customers import router as customers_router
from .routers.documents import router as documents_router
from .routers.exports import imports_router, router as exports_router
from .routers.health import router as health_router
from .routers.notifications import router as notifications_router
from .routers.routing import router as routing_router
from .routers.shipments import router as shipments_router
from .schemas import (
    AiAnalysis,
    AiPrompt,
    DashboardSummary,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    ShipmentCreate,
    ShipmentResponse,
    UserUpdate,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.debug,
    description="Bağcıbaşı Logistics için operasyon, finans, karbon ve AI karar destek API'si.",
)
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(shipments_router, prefix="/api/v1")
app.include_router(vehicles_router, prefix="/api/v1")
app.include_router(carbon_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(exports_router, prefix="/api/v1")
app.include_router(imports_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(routing_router, prefix="/api/v1")
app.include_router(health_router)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_database(db)


@app.post("/api/auth/login", response_model=LoginResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest = Body(...), db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.username == payload.username, User.is_active.is_(True)))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı adı veya şifre hatalı")
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(db, user)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
        },
    }


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
    }


@app.put("/api/auth/me")
def update_me(payload: UserUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    full_name = payload.full_name.strip() if payload.full_name is not None else None
    if full_name is not None:
        if len(full_name) < 2:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ad soyad en az 2 karakter olmalı")
        user.full_name = full_name

    username = payload.username.strip() if payload.username is not None else None
    if username and username != user.username:
        exists = db.scalar(select(User).where(User.username == username, User.id != user.id))
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu kullanıcı adı zaten kullanılıyor")
        user.username = username

    if payload.password:
        if len(payload.password) < 6:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Şifre en az 6 karakter olmalı")
        user.password_hash = hash_password(payload.password)

    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
    }


@app.post("/api/auth/refresh", response_model=LoginResponse)
@limiter.limit("20/minute")
def refresh(request: Request, payload: RefreshRequest = Body(...), db: Session = Depends(get_db)) -> dict:
    user, access_token, refresh_token = rotate_refresh_token(db, payload.refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
        },
    }


@app.post("/api/auth/logout")
@limiter.limit("30/minute")
def logout(request: Request, payload: LogoutRequest = Body(...), db: Session = Depends(get_db)) -> dict:
    revoke_access_token(db, payload.access_token)
    revoke_refresh_token(db, payload.refresh_token)
    return {"status": "ok"}


@app.post("/api/v1/auth/change-password")
@limiter.limit("10/minute")
def change_password(
    request: Request,
    payload: dict = Body(...),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    current_password = str(payload.get("current_password") or "")
    new_password = str(payload.get("new_password") or "")
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mevcut şifre hatalı")
    if len(new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Yeni şifre en az 6 karakter olmalı")
    user.password_hash = hash_password(new_password)
    db.add(user)
    for token_row in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.is_revoked.is_(False))).all():
        token_row.is_revoked = True
        token_row.revoked_at = datetime.utcnow()
        db.add(token_row)
        if not db.scalar(select(RevokedToken).where(RevokedToken.token_jti == token_row.token_jti)):
            db.add(RevokedToken(token_jti=token_row.token_jti, token_type="refresh"))
    db.commit()
    db.refresh(user)
    if authorization and authorization.startswith("Bearer "):
        revoke_access_token(db, authorization.removeprefix("Bearer ").strip())
    return {"status": "ok"}


@app.get("/api/users")
def get_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> list[dict]:
    return list_users(db)


@app.post("/api/import/excel")
@limiter.limit("15/minute")
async def import_excel(
    request: Request,
    file: bytes = File(...),
    filename: str = Form("import.xlsx"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "manager")),
) -> dict:
    if not filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Lütfen .xlsx dosyası yükleyin")
    result = import_operations_excel(db, file)
    return {"uploaded_by": user.username, "filename": filename, **result}


@app.get("/api/dashboard", response_model=DashboardSummary)
def get_dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    return dashboard_summary(db)


@app.get("/api/shipments", response_model=list[ShipmentResponse])
def get_shipments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict]:
    shipments = list_shipments(db)
    if current_user.role == "driver":
        return [item for item in shipments if str(item.get("driver_id")) == str(current_user.id)]
    return shipments


@app.post("/api/shipments", response_model=ShipmentResponse, status_code=201)
def post_shipment(payload: ShipmentCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "manager"))) -> dict:
    return create_shipment(db, payload.model_dump())


@app.post("/api/shipments/quote")
def quote_shipment(payload: ShipmentCreate, _: User = Depends(get_current_user)) -> dict:
    result = calculate_operation(
        payload.origin,
        payload.destination,
        payload.cargo_type,
        payload.tonnage,
        payload.delivery_date,
    )
    return {"customer_name": payload.customer_name, "status": "Teklif", **result}


@app.get("/api/finance")
def get_finance(db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "manager"))) -> dict:
    return finance_summary(db)


@app.get("/api/carbon")
def get_carbon(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    shipments = list_shipments(db)
    total = sum(item["co2_kg"] for item in shipments)
    highest = max(shipments, key=lambda item: item["co2_kg"]) if shipments else None
    return {
        "total_co2_kg": round(total, 2),
        "highest_emission_route": f"{highest['origin']} - {highest['destination']}" if highest else None,
        "optimization_note": "Araç tipi ve alternatif rota seçimiyle %12-18 emisyon azaltımı hedeflenebilir.",
    }


@app.get("/api/live-map")
def get_live_map(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    shipments = list_shipments(db)
    vehicles, _ = get_vehicles(db)
    shipment_lookup = {str(item["id"]): item for item in shipments}
    return {
        "vehicles": [
            {
                "plate": vehicle.plate_number,
                "driver": vehicle.driver_name or "Atanmamış",
                "vehicle_type": vehicle.vehicle_type,
                "status": vehicle.status,
                "route": (
                    f"{shipment_lookup[str(vehicle.current_shipment_id)]['origin']} - {shipment_lookup[str(vehicle.current_shipment_id)]['destination']}"
                    if vehicle.current_shipment_id and str(vehicle.current_shipment_id) in shipment_lookup
                    else "Sevkiyat yok"
                ),
                "progress": 72 if vehicle.status == "Yolda" else 22 if vehicle.status == "Yukleniyor" else 0,
                "lat": vehicle.current_lat,
                "lng": vehicle.current_lng,
                "risk_level": (
                    shipment_lookup[str(vehicle.current_shipment_id)]["risk_level"]
                    if vehicle.current_shipment_id and str(vehicle.current_shipment_id) in shipment_lookup
                    else "Düşük"
                ),
            }
            for vehicle in vehicles
        ],
        "depots": [
            {"name": "Manisa Merkez Depo", "lat": 38.62, "lng": 27.43, "occupancy": 72},
            {"name": "İzmir Aktarma", "lat": 38.42, "lng": 27.14, "occupancy": 41},
            {"name": "İstanbul Teslim Bölgesi", "lat": 41.01, "lng": 28.98, "occupancy": 88},
        ],
        "heatmap": [
            {"city": "İstanbul", "level": "high", "shipments": 12},
            {"city": "İzmir", "level": "medium", "shipments": 7},
            {"city": "Ankara", "level": "low", "shipments": 3},
        ],
        "traffic_note": "İstanbul girişinde orta yoğunluk var. Alternatif rota ile tahmini 22 dakika kazanım mümkün.",
    }


@app.post("/api/ai/analyze", response_model=AiAnalysis)
def analyze_prompt(payload: AiPrompt, _: User = Depends(get_current_user)) -> dict:
    prompt = payload.prompt
    city_names = list(CITIES.keys())
    matched_cities = [city for city in city_names if city.lower() in prompt.lower()]
    origin = matched_cities[0] if matched_cities else "İstanbul"
    destination = matched_cities[1] if len(matched_cities) > 1 else "Ankara"
    tonnage_match = re.search(r"(\d+(?:[,.]\d+)?)\s*ton", prompt, flags=re.IGNORECASE)
    tonnage = float(tonnage_match.group(1).replace(",", ".")) if tonnage_match else 14.0
    cargo_type = "Tekstil" if "tekstil" in prompt.lower() else "Genel Yük"
    result = calculate_operation(origin, destination, cargo_type, tonnage, date.today() + timedelta(days=3))
    vehicle = choose_vehicle(tonnage)

    return {
        "summary": result["ai_recommendation"],
        "suggested_vehicle": vehicle.name,
        "estimated_price": result["invoice_amount"],
        "estimated_profit": result["profit_amount"],
        "estimated_co2_kg": result["co2_kg"],
        "risk_level": result["risk_level"],
    }
