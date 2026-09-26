"""match periods and opposition goals

Periods are the time axis for the match timeline: competitions.period_count (2 = halves,
4 = quarters) with a per-fixture override, fixtures.current_period while a match is live,
and match_events.period stamped on each event. Plus the 'opp_goal' event type, so "they
scored" is a row on the timeline instead of only a number in their_score (we never record
the opposition's player names).

Revision ID: 0e233af3d700
Revises: f6564b0195f1
Create Date: 2026-09-26 23:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0e233af3d700"
down_revision: str | None = "f6564b0195f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_TYPES = "event_type IN ('goal', 'assist', 'own_goal', 'opp_own_goal')"
NEW_TYPES = "event_type IN ('goal', 'assist', 'own_goal', 'opp_own_goal', 'opp_goal')"
OLD_PLAYER = (
    "(event_type = 'opp_own_goal' AND player_id IS NULL) "
    "OR (event_type <> 'opp_own_goal' AND player_id IS NOT NULL)"
)
NEW_PLAYER = (
    "(event_type IN ('opp_own_goal', 'opp_goal') AND player_id IS NULL) "
    "OR (event_type NOT IN ('opp_own_goal', 'opp_goal') AND player_id IS NOT NULL)"
)


def upgrade() -> None:
    with op.batch_alter_table("competitions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("period_count", sa.Integer(), server_default="2", nullable=False)
        )
        batch_op.create_check_constraint("period_count", "period_count BETWEEN 1 AND 4")

    with op.batch_alter_table("fixtures", schema=None) as batch_op:
        batch_op.add_column(sa.Column("period_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("current_period", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "period_count", "period_count IS NULL OR period_count BETWEEN 1 AND 4"
        )
        batch_op.create_check_constraint(
            "current_period", "current_period IS NULL OR current_period >= 1"
        )

    # SQLite can't alter a CHECK; batch mode rebuilds the table around the new one.
    with op.batch_alter_table("match_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("period", sa.Integer(), nullable=True))
        batch_op.drop_constraint("event_type", type_="check")
        batch_op.create_check_constraint("event_type", NEW_TYPES)
        batch_op.drop_constraint("player_required", type_="check")
        batch_op.create_check_constraint("player_required", NEW_PLAYER)


def downgrade() -> None:
    # Opposition goals only exist under the new event type; the score they were counted
    # into is stored on the fixture, so dropping the rows loses nothing derivable.
    op.execute("DELETE FROM match_events WHERE event_type = 'opp_goal'")
    with op.batch_alter_table("match_events", schema=None) as batch_op:
        batch_op.drop_constraint("player_required", type_="check")
        batch_op.create_check_constraint("player_required", OLD_PLAYER)
        batch_op.drop_constraint("event_type", type_="check")
        batch_op.create_check_constraint("event_type", OLD_TYPES)
        batch_op.drop_column("period")

    with op.batch_alter_table("fixtures", schema=None) as batch_op:
        batch_op.drop_constraint("current_period", type_="check")
        batch_op.drop_constraint("period_count", type_="check")
        batch_op.drop_column("current_period")
        batch_op.drop_column("period_count")

    with op.batch_alter_table("competitions", schema=None) as batch_op:
        batch_op.drop_constraint("period_count", type_="check")
        batch_op.drop_column("period_count")
