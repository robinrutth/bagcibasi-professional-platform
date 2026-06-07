"""Update shipments table

Revision ID: 20260513_02
Revises: 20260513_01
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260513_02"
down_revision = "20260513_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shipments", sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("shipments", sa.Column("weight_kg", sa.Float(), nullable=True))
    op.add_column("shipments", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("shipments", sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.execute("UPDATE shipments SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("shipments", "updated_at", nullable=False)
    op.create_index(op.f("ix_shipments_driver_id"), "shipments", ["driver_id"], unique=False)
    op.create_foreign_key("fk_shipments_driver_id_users", "shipments", "users", ["driver_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_shipments_driver_id_users", "shipments", type_="foreignkey")
    op.drop_index(op.f("ix_shipments_driver_id"), table_name="shipments")
    op.drop_column("shipments", "is_deleted")
    op.drop_column("shipments", "updated_at")
    op.drop_column("shipments", "weight_kg")
    op.drop_column("shipments", "driver_id")
