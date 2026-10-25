"""parent_access_log, and no more ghost parent accounts

A parent account is now exactly its links to children: removing the last child removes
the account (`services/invites.py`), and close/reopen are gone. That leaves one thing to
keep - the record of who could see which child - so it moves into an append-only table
whose rows have no foreign key to `users` and therefore survive the account.

Also clears up any account the old `unlink` had already stranded: no guardian links, no
roles, and a username that is an email address, which only a parent's ever is (a coach's
username is validated against `^[a-zA-Z0-9._-]+$`, so it can never contain '@').

Revision ID: b3c71f4a92d1
Revises: e26bd5aab690
"""

import sqlalchemy as sa

from alembic import op

revision = "b3c71f4a92d1"
down_revision = "e26bd5aab690"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parent_access_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("parent_name", sa.String(length=100), nullable=True),
        sa.Column("parent_email", sa.String(length=255), nullable=True),
        sa.Column("by_user_id", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name=op.f("fk_parent_access_log_player_id_players"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parent_access_log")),
    )
    op.create_index(op.f("ix_parent_access_log_user_id"), "parent_access_log", ["user_id"])
    op.create_index(op.f("ix_parent_access_log_player_id"), "parent_access_log", ["player_id"])

    # Backfill a 'granted' line for everyone who can see a child today, so the log starts
    # out telling the truth rather than starting empty.
    op.execute(
        """
        INSERT INTO parent_access_log (user_id, parent_name, parent_email, player_id, action, at)
        SELECT g.user_id, u.display_name, u.email, g.player_id, 'granted',
               COALESCE(g.created_at, CURRENT_TIMESTAMP)
        FROM player_guardians g JOIN users u ON u.id = g.user_id
        """
    )

    # Parents the old unlink stranded: unreachable through the API, yet holding an email
    # address that could never be invited again.
    op.execute(
        """
        DELETE FROM users
        WHERE username LIKE '%@%'
          AND id NOT IN (SELECT user_id FROM player_guardians)
          AND id NOT IN (SELECT user_id FROM user_roles)
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_parent_access_log_player_id"), table_name="parent_access_log")
    op.drop_index(op.f("ix_parent_access_log_user_id"), table_name="parent_access_log")
    op.drop_table("parent_access_log")
