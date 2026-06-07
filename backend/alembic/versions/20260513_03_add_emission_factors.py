"""Add emission factors

Revision ID: 20260513_03
Revises: 20260513_02
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260513_03"
down_revision = "20260513_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emission_factors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vehicle_type", sa.String(), nullable=False),
        sa.Column("co2_per_km", sa.Float(), nullable=False),
        sa.Column("co2_per_kg_km", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vehicle_type", name="uq_emission_factors_vehicle_type"),
    )
    op.create_index(op.f("ix_emission_factors_vehicle_type"), "emission_factors", ["vehicle_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_emission_factors_vehicle_type"), table_name="emission_factors")
    op.drop_table("emission_factors")
