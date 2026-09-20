"""live fixture status

Adds 'live' to the fixtures.status CHECK: a fixture being recorded at the side of the
pitch (POST /fixtures/{id}/live/start) sits in this state until it is finished.

Revision ID: 3f1c2a9d7b4e
Revises: 80ec87bd57d9
Create Date: 2026-09-20 11:27:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "3f1c2a9d7b4e"
down_revision: str | None = "80ec87bd57d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = "status IN ('scheduled', 'played', 'postponed', 'cancelled', 'abandoned')"
NEW = "status IN ('scheduled', 'live', 'played', 'postponed', 'cancelled', 'abandoned')"


def _swap_check(new_sql: str) -> None:
    # SQLite can't alter a CHECK; batch mode rebuilds the table. The constraint name is
    # deterministic (naming convention in db/base.py), so "status" resolves to ck_fixtures_status.
    with op.batch_alter_table("fixtures", schema=None) as batch_op:
        batch_op.drop_constraint("status", type_="check")
        batch_op.create_check_constraint("status", new_sql)


def upgrade() -> None:
    _swap_check(NEW)


def downgrade() -> None:
    op.execute("UPDATE fixtures SET status = 'scheduled' WHERE status = 'live'")
