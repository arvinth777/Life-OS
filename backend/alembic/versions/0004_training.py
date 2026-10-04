"""Optional workout timing; old sessions keep unknown duration."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('workouts', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('workouts', sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_workouts_started_at', 'workouts', ['started_at'])
    op.create_index('ix_workouts_ended_at', 'workouts', ['ended_at'])
    op.create_check_constraint('workout_time_order', 'workouts', 'ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at)')
    op.create_index('one_active_workout', 'workouts', [sa.text('(true)')], unique=True,
                    postgresql_where=sa.text('started_at IS NOT NULL AND ended_at IS NULL'))

def downgrade():
    op.drop_index('one_active_workout', table_name='workouts')
    op.drop_constraint('workout_time_order', 'workouts', type_='check')
    op.drop_index('ix_workouts_ended_at', table_name='workouts')
    op.drop_index('ix_workouts_started_at', table_name='workouts')
    op.drop_column('workouts', 'ended_at')
    op.drop_column('workouts', 'started_at')
