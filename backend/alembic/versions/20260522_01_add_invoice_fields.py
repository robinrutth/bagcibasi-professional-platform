"""Add invoice fields to shipments

Revision ID: 20260522_01
Revises: 20260513_04
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa
from uuid import uuid4


revision = "20260522_01"
down_revision = "20260513_04"
branch_labels = None
depends_on = None


FACTORS = {
    "panelvan": (0.15, 0.00008, "Panelvan light commercial delivery estimate."),
    "kamyonet": (0.18, 0.00010, "Kamyonet urban and regional delivery estimate."),
    "kamyon": (0.27, 0.00015, "Kamyon heavy-duty road freight estimate."),
    "tir": (0.32, 0.00018, "Tir long-haul freight estimate."),
    "elektrikli": (0.05, 0.00002, "Elektrikli arac grid-adjusted operational emissions estimate."),
}


def upgrade() -> None:
    op.add_column("shipments", sa.Column("desi", sa.Float(), nullable=True))
    op.add_column("shipments", sa.Column("invoice", sa.Float(), nullable=True))
    op.add_column("shipments", sa.Column("cost", sa.Float(), nullable=True))
    op.add_column("shipments", sa.Column("profit", sa.Float(), nullable=True))
    op.execute("UPDATE shipments SET invoice = invoice_amount, cost = cost_amount, profit = profit_amount")
    op.execute(
        """
        UPDATE shipments
        SET vehicle_type = CASE vehicle_type
            WHEN 'truck' THEN 'kamyon'
            WHEN 'minivan' THEN 'kamyonet'
            WHEN 'electric' THEN 'elektrikli'
            WHEN 'motorcycle' THEN 'panelvan'
            WHEN 'bicycle' THEN 'elektrikli'
            ELSE vehicle_type
        END
        """
    )

    op.execute("DELETE FROM emission_factors WHERE vehicle_type IN ('truck', 'minivan', 'motorcycle', 'electric', 'bicycle')")
    for vehicle_type, (co2_per_km, co2_per_kg_km, description) in FACTORS.items():
        op.execute(
            sa.text(
                """
                INSERT INTO emission_factors (id, vehicle_type, co2_per_km, co2_per_kg_km, description)
                VALUES (CAST(:id AS uuid), :vehicle_type, :co2_per_km, :co2_per_kg_km, :description)
                ON CONFLICT (vehicle_type) DO UPDATE SET
                    co2_per_km = EXCLUDED.co2_per_km,
                    co2_per_kg_km = EXCLUDED.co2_per_kg_km,
                    description = EXCLUDED.description
                """
            ).bindparams(
                id=str(uuid4()),
                vehicle_type=vehicle_type,
                co2_per_km=co2_per_km,
                co2_per_kg_km=co2_per_kg_km,
                description=description,
            )
        )


def downgrade() -> None:
    op.drop_column("shipments", "profit")
    op.drop_column("shipments", "cost")
    op.drop_column("shipments", "invoice")
    op.drop_column("shipments", "desi")
