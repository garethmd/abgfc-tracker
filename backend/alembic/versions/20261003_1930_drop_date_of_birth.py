"""Stop storing children's dates of birth

The app collected a date of birth on every player and never read it: nothing
displayed it, no report or export carried it, and age-group eligibility is decided
by the cohort's birth-year window, not per child. Children's PII with no purpose,
so it goes - the 22 dates on record are erased with the column.

Deliberately NOT a batch operation. Seven tables carry foreign keys to players
(appearances, awards, match_events, squad_members, media_links and the two
selection tables); batch mode would rebuild the table by copy-drop-rename, which
is a great deal of risk for one unused column. SQLite has supported native
ALTER TABLE ... DROP COLUMN since 3.35 and the droplet runs well past that.

Revision ID: a1d0b17hdrop
Revises: 39581085fe8b
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1d0b17hdrop"
down_revision: str | None = "39581085fe8b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("players", "date_of_birth")


def downgrade() -> None:
    # The column comes back empty: the dates themselves are gone for good, which is
    # the point of the change.
    op.add_column("players", sa.Column("date_of_birth", sa.Date(), nullable=True))
