"""password reset tokens

Adds 'reset' to the login_tokens.purpose CHECK. Parents now have a password; email is
used only to recover one, which is what NIST permits. Accounts created before this keep
their 'signin' links until they set a password, so nobody is locked out.

Revision ID: e26bd5aab690
Revises: 1a84c4fcd9c0
Create Date: 2026-10-17 23:29:11.073130
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e26bd5aab690"
down_revision: str | None = "1a84c4fcd9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_PURPOSE = "purpose IN ('invite', 'signin')"
NEW_PURPOSE = "purpose IN ('invite', 'signin', 'reset')"

# A reset token names a user and no player, like a signin one.
OLD_TARGET = (
    "(purpose = 'invite' AND player_id IS NOT NULL AND user_id IS NULL) "
    "OR (purpose = 'signin' AND user_id IS NOT NULL)"
)
NEW_TARGET = (
    "(purpose = 'invite' AND player_id IS NOT NULL AND user_id IS NULL) "
    "OR (purpose IN ('signin', 'reset') AND user_id IS NOT NULL)"
)


def _swap(purpose_sql: str, target_sql: str) -> None:
    # SQLite can't alter a CHECK; batch mode rebuilds the table. Constraint names are
    # deterministic (naming convention in db/base.py), so these resolve.
    with op.batch_alter_table("login_tokens", schema=None) as batch_op:
        batch_op.drop_constraint("purpose", type_="check")
        batch_op.drop_constraint("purpose_target", type_="check")
        batch_op.create_check_constraint("purpose", purpose_sql)
        batch_op.create_check_constraint("purpose_target", target_sql)


def upgrade() -> None:
    _swap(NEW_PURPOSE, NEW_TARGET)


def downgrade() -> None:
    op.execute("DELETE FROM login_tokens WHERE purpose = 'reset'")
    _swap(OLD_PURPOSE, OLD_TARGET)
