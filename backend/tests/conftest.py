from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import CashMovement, Customer, Shipment, User
from app.services.carbon_service import seed_default_emission_factors


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        seed_default_emission_factors(session)
        _seed_summary_rows(session)
        session.commit()
        yield session
        session.rollback()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def users(db_session: Session) -> dict[str, User]:
    rows = {
        "admin": User(username="admin", full_name="Admin User", role="admin", password_hash=hash_password("secret"), is_active=True),
        "manager": User(username="manager", full_name="Manager User", role="manager", password_hash=hash_password("secret"), is_active=True),
        "driver": User(username="driver", full_name="Driver User", role="driver", password_hash=hash_password("secret"), is_active=True),
        "viewer": User(username="viewer", full_name="Viewer User", role="viewer", password_hash=hash_password("secret"), is_active=True),
    }
    db_session.add_all(rows.values())
    db_session.commit()
    for user in rows.values():
        db_session.refresh(user)
    return rows


@pytest.fixture()
def admin_user(users: dict[str, User]) -> User:
    return users["admin"]


@pytest.fixture()
def manager_user(users: dict[str, User]) -> User:
    return users["manager"]


@pytest.fixture()
def driver_user(users: dict[str, User]) -> User:
    return users["driver"]


@pytest.fixture()
def viewer_user(users: dict[str, User]) -> User:
    return users["viewer"]


@pytest.fixture()
def auth_tokens(users: dict[str, User]) -> dict[str, str]:
    return {role: create_access_token(user) for role, user in users.items()}


@pytest.fixture()
def auth_headers(auth_tokens: dict[str, str]):
    def _headers(role: str = "admin") -> dict[str, str]:
        return {"Authorization": f"Bearer {auth_tokens[role]}"}

    return _headers


@pytest.fixture()
def sample_customer(db_session: Session) -> Customer:
    customer = Customer(
        name="Api Customer",
        email="api.customer@example.com",
        phone="+90 555 000 00 00",
        city="Manisa",
        tax_number="5550001111",
        sector="Test",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture()
def sample_shipments(db_session: Session, sample_customer: Customer, driver_user: User) -> list[Shipment]:
    other_driver = User(
        username="other-driver",
        full_name="Other Driver",
        role="driver",
        password_hash=hash_password("secret"),
        is_active=True,
    )
    db_session.add(other_driver)
    db_session.commit()
    db_session.refresh(other_driver)

    rows = [
        _shipment(customer=sample_customer, driver=driver_user, customer_name="Api Customer", destination="Ankara", status="Yolda", co2_kg=42),
        _shipment(customer=sample_customer, driver=driver_user, customer_name="Api Customer", destination="Izmir", status="Teslim Edildi", co2_kg=12),
        _shipment(customer=sample_customer, driver=other_driver, customer_name="Api Customer", destination="Bursa", status="Planlandi", co2_kg=20),
    ]
    db_session.add_all(rows)
    db_session.commit()
    for row in rows:
        db_session.refresh(row)
    return rows


def _shipment(
    *,
    customer: Customer | None = None,
    driver: User | None = None,
    customer_name: str = "A",
    origin: str = "Manisa",
    destination: str = "Ankara",
    status: str = "Yolda",
    cost_amount: float = 10000,
    invoice_amount: float = 12000,
    profit_amount: float = 2000,
    co2_kg: float = 40,
) -> Shipment:
    return Shipment(
        customer_id=customer.id if customer else None,
        driver_id=driver.id if driver else None,
        customer_name=customer_name,
        origin=origin,
        destination=destination,
        cargo_type="Tekstil",
        tonnage=10,
        weight_kg=10000,
        delivery_date=date(2026, 5, 20),
        distance_km=100,
        vehicle_type="truck",
        status=status,
        cost_amount=cost_amount,
        invoice_amount=invoice_amount,
        profit_amount=profit_amount,
        profit_margin=0.1667,
        co2_kg=co2_kg,
        risk_level="Dusuk",
        ai_recommendation="ok",
    )


def _seed_summary_rows(session: Session) -> None:
    session.add_all(
        [
            CashMovement(description="open", movement_type="in", amount=550000, payment_type="cash"),
            CashMovement(description="income", movement_type="in", amount=30000, payment_type="cash"),
            CashMovement(description="out", movement_type="out", amount=70000, payment_type="bank"),
            CashMovement(description="pending", movement_type="pending", amount=63000, payment_type="credit"),
        ]
    )
    session.add_all(
        [
            _shipment(
                customer_name="A",
                origin="Manisa",
                destination="Izmir",
                status="Teslim Edildi",
                co2_kg=40,
            ),
            _shipment(
                customer_name="B",
                origin="Manisa",
                destination="Istanbul",
                status="Yolda",
                cost_amount=30000,
                invoice_amount=36000,
                profit_amount=6000,
                co2_kg=320,
            ),
        ]
    )
