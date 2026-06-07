"""Add vehicles table

Revision ID: 20260523_01
Revises: 20260522_01
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20260523_01"
down_revision = "20260522_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plate_number", sa.String(), nullable=False),
        sa.Column("vehicle_type", sa.String(), nullable=False),
        sa.Column("capacity_tons", sa.Float(), nullable=False),
        sa.Column("current_load_tons", sa.Float(), nullable=False, server_default="0"),
        sa.Column("driver_name", sa.String(), nullable=True),
        sa.Column("driver_phone", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="Bosta"),
        sa.Column("current_lat", sa.Float(), nullable=True),
        sa.Column("current_lng", sa.Float(), nullable=True),
        sa.Column("current_shipment_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["current_shipment_id"], ["shipments.id"], name="fk_vehicles_current_shipment_id_shipments", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plate_number"),
    )
    op.create_index(op.f("ix_vehicles_current_shipment_id"), "vehicles", ["current_shipment_id"], unique=False)
    op.create_index(op.f("ix_vehicles_is_deleted"), "vehicles", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_vehicles_plate_number"), "vehicles", ["plate_number"], unique=False)
    op.create_index(op.f("ix_vehicles_status"), "vehicles", ["status"], unique=False)
    op.add_column("shipments", sa.Column("vehicle_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_shipments_vehicle_id"), "shipments", ["vehicle_id"], unique=False)
    op.create_foreign_key("fk_shipments_vehicle_id_vehicles", "shipments", "vehicles", ["vehicle_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_shipments_vehicle_id_vehicles", "shipments", type_="foreignkey")
    op.drop_index(op.f("ix_shipments_vehicle_id"), table_name="shipments")
    op.drop_column("shipments", "vehicle_id")
    op.drop_index(op.f("ix_vehicles_status"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_plate_number"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_is_deleted"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_current_shipment_id"), table_name="vehicles")
    op.drop_table("vehicles")
