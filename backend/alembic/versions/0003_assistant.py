"""Private assistant connection and learning records; immutable schema snapshot."""
from alembic import op
from importlib.machinery import SourceFileLoader
import importlib.util
from pathlib import Path
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None
NAMES = {'assistant_oauth', 'assistant_batches', 'learning_topics', 'learning_sessions', 'exams'}
def tables():
    loader = SourceFileLoader('schema_v3', str(Path(__file__).with_name('schema_v3.snapshot')))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return [t for t in module.metadata.sorted_tables if t.name in NAMES]
def upgrade():
    for table in tables():
        table.create(op.get_bind())
def downgrade():
    for table in reversed(tables()):
        table.drop(op.get_bind())
