"""Initial immutable PostgreSQL schema."""

from alembic import op
import importlib.util
from pathlib import Path

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def snapshot():
    spec = importlib.util.spec_from_file_location(
        "schema_v1", Path(__file__).with_name("schema_v1.snapshot")
    )
    # Use a SourceFileLoader because the immutable snapshot is intentionally not a migration module.
    from importlib.machinery import SourceFileLoader

    loader = SourceFileLoader(
        "schema_v1", str(Path(__file__).with_name("schema_v1.snapshot"))
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module.metadata


def upgrade():
    snapshot().create_all(op.get_bind())


def downgrade():
    snapshot().drop_all(op.get_bind())
