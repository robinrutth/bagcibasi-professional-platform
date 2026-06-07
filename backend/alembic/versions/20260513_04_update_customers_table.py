"""Update customers table

Revision ID: 20260513_04
Revises: 20260513_03
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260513_04"
down_revision = "20260513_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("email", sa.String(), nullable=True))
    op.add_column("customers", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("customers", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("city", sa.String(), nullable=True))
    op.add_column("customers", sa.Column("tax_number", sa.String(), nullable=True))
    op.add_column("customers", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("customers", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE customers SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("customers", "updated_at", nullable=False)
    op.create_index(op.f("ix_customers_email"), "customers", ["email"], unique=True)
    op.create_index(op.f("ix_customers_city"), "customers", ["city"], unique=False)
    op.create_index(op.f("ix_customers_tax_number"), "customers", ["tax_number"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_customers_tax_number"), table_name="customers")
    op.drop_index(op.f("ix_customers_city"), table_name="customers")
    op.drop_index(op.f("ix_customers_email"), table_name="customers")
    op.drop_column("customers", "updated_at")
    op.drop_column("customers", "is_active")
    op.drop_column("customers", "tax_number")
    op.drop_column("customers", "city")
    op.drop_column("customers", "address")
    op.drop_column("customers", "phone")
    op.drop_column("customers", "email")
