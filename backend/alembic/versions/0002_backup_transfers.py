"""Durable, encrypted backup transport for request-limited hosts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "backup_transfers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("owners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.Text, nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("chunks", JSONB, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("direction IN ('download', 'upload')"),
        sa.CheckConstraint("size > 0 AND size <= 25000000"),
    )
    for column in ("created_at", "updated_at", "owner_id", "expires_at"):
        op.create_index("ix_backup_transfers_" + column, "backup_transfers", [column])


def downgrade():
    op.drop_table("backup_transfers")
