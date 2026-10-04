"""Personal experiments and reversible task shelving."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = '0005'
down_revision = '0004'
branch_labels = depends_on = None

def base():
    return [sa.Column('id', UUID(as_uuid=True), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]

def upgrade():
    op.add_column('tasks', sa.Column('archived', sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column('tasks', sa.Column('focus_after', sa.Date, nullable=True))
    op.create_table('experiments', *base(),
        sa.Column('title', sa.Text, nullable=False), sa.Column('hypothesis', sa.Text, nullable=False),
        sa.Column('action', sa.Text, nullable=False), sa.Column('starts_on', sa.Date, nullable=False),
        sa.Column('ends_on', sa.Date, nullable=False), sa.Column('status', sa.Text, nullable=False),
        sa.Column('conclusion', sa.Text, nullable=False),
        sa.CheckConstraint('ends_on >= starts_on'), sa.CheckConstraint("status IN ('active', 'keep', 'change', 'stop')"))
    op.create_table('experiment_checkins', *base(),
        sa.Column('experiment_id', UUID(as_uuid=True), sa.ForeignKey('experiments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('on_date', sa.Date, nullable=False), sa.Column('tried', sa.Boolean, nullable=False),
        sa.Column('feeling', sa.Integer, nullable=True), sa.Column('note', sa.Text, nullable=False),
        sa.UniqueConstraint('experiment_id', 'on_date'), sa.CheckConstraint('feeling IS NULL OR feeling BETWEEN 1 AND 5'))
    for name in ('experiments', 'experiment_checkins'):
        for column in ('created_at', 'updated_at'):
            op.create_index(f'ix_{name}_{column}', name, [column])
    op.create_index('ix_experiment_checkins_experiment_id', 'experiment_checkins', ['experiment_id'])

def downgrade():
    op.drop_table('experiment_checkins')
    op.drop_table('experiments')
    op.drop_column('tasks', 'focus_after')
    op.drop_column('tasks', 'archived')
