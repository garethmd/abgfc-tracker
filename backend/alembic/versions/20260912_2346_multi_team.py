"""club teams, cohorts, team seasons, user roles

Everything that was per-season becomes per-team-per-season. Existing data is remapped:
each season -> a Blues team-season in a "Born 2016/17" cohort; each user -> club admin.

Revision ID: 06919a849b32
Revises: 34de72645897
Create Date: 2026-09-12 23:46:57.345719
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "06919a849b32"
down_revision: str | None = "34de72645897"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMPS = [
    sa.Column(
        "created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False
    ),
    sa.Column(
        "updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False
    ),
]

# Remapped tables: (table, old index/constraint names to drop, new ones to create)
REMAP = ["squad_members", "fixtures", "awards"]


def upgrade() -> None:
    # --- new tables --------------------------------------------------------------
    op.create_table(
        "cohorts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("birth_year_start", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        *TIMESTAMPS,
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cohorts")),
        sa.UniqueConstraint("name", name=op.f("uq_cohorts_name")),
    )
    op.create_table(
        "club_teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cohort_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("colour", sa.String(length=30), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        *TIMESTAMPS,
        sa.ForeignKeyConstraint(
            ["cohort_id"],
            ["cohorts.id"],
            name=op.f("fk_club_teams_cohort_id_cohorts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_teams")),
        sa.UniqueConstraint("cohort_id", "name", name=op.f("uq_club_teams_cohort_id_name")),
        sa.UniqueConstraint("slug", name=op.f("uq_club_teams_slug")),
    )
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(scope_type = 'club' AND scope_id IS NULL) OR (scope_type <> 'club' AND scope_id IS NOT NULL)",
            name=op.f("ck_user_roles_scope_id_presence"),
        ),
        sa.CheckConstraint("role IN ('viewer', 'coach', 'admin')", name=op.f("ck_user_roles_role")),
        sa.CheckConstraint(
            "scope_type IN ('club', 'cohort', 'team')", name=op.f("ck_user_roles_scope_type")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.UniqueConstraint(
            "user_id",
            "scope_type",
            "scope_id",
            name=op.f("uq_user_roles_user_id_scope_type_scope_id"),
        ),
    )
    with op.batch_alter_table("user_roles", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_user_roles_user_id"), ["user_id"], unique=False)
    op.create_table(
        "team_seasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("club_team_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("age_group", sa.String(length=10), nullable=True),
        sa.Column("format", sa.String(length=10), nullable=True),
        sa.Column("match_minutes", sa.Integer(), server_default="50", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="0", nullable=False),
        *TIMESTAMPS,
        sa.ForeignKeyConstraint(
            ["club_team_id"],
            ["club_teams.id"],
            name=op.f("fk_team_seasons_club_team_id_club_teams"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
            name=op.f("fk_team_seasons_season_id_seasons"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_seasons")),
        sa.UniqueConstraint(
            "club_team_id", "season_id", name=op.f("uq_team_seasons_club_team_id_season_id")
        ),
    )

    # --- data: existing seasons become Blues team-seasons ------------------------------
    conn = op.get_bind()
    seasons = conn.execute(
        sa.text("SELECT id, start_date, match_minutes, is_current FROM seasons")
    ).fetchall()
    if seasons:
        conn.execute(
            sa.text("INSERT INTO cohorts (name, birth_year_start) VALUES ('Born 2016/17', 2016)")
        )
        cohort_id = conn.execute(
            sa.text("SELECT id FROM cohorts WHERE name = 'Born 2016/17'")
        ).scalar_one()
        conn.execute(
            sa.text(
                "INSERT INTO club_teams (cohort_id, name, slug, colour, sort_order) VALUES (:c, 'Blues', 'blues', 'oklch(0.5 0.2 258)', 0)"
            ),
            {"c": cohort_id},
        )
        team_id = conn.execute(
            sa.text("SELECT id FROM club_teams WHERE slug = 'blues'")
        ).scalar_one()
        for s in seasons:
            start_year = int(str(s.start_date)[:4]) if s.start_date else None
            age_group = f"U{start_year - 2016}" if start_year else None
            conn.execute(
                sa.text(
                    "INSERT INTO team_seasons (club_team_id, season_id, age_group, format, match_minutes, is_current) "
                    "VALUES (:t, :s, :ag, '7v7', :mm, :cur)"
                ),
                {
                    "t": team_id,
                    "s": s.id,
                    "ag": age_group,
                    "mm": s.match_minutes,
                    "cur": s.is_current,
                },
            )

    # --- remap season_id -> team_season_id on squad_members / fixtures / awards ---------------
    for table in REMAP:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("team_season_id", sa.Integer(), nullable=True))
        conn.execute(
            sa.text(
                f"UPDATE {table} SET team_season_id = "
                f"(SELECT ts.id FROM team_seasons ts WHERE ts.season_id = {table}.season_id)"
            )
        )

    with op.batch_alter_table("squad_members", schema=None) as batch_op:
        batch_op.alter_column("team_season_id", nullable=False)
        batch_op.drop_constraint(batch_op.f("uq_squad_members_season_id_player_id"), type_="unique")
        batch_op.drop_index(
            batch_op.f("uq_squad_members_season_id_squad_number"),
            sqlite_where=sa.text("squad_number IS NOT NULL"),
        )
        batch_op.create_unique_constraint(
            batch_op.f("uq_squad_members_team_season_id_player_id"), ["team_season_id", "player_id"]
        )
        batch_op.create_index(
            "uq_squad_members_team_season_id_squad_number",
            ["team_season_id", "squad_number"],
            unique=True,
            sqlite_where=sa.text("squad_number IS NOT NULL"),
        )
        batch_op.drop_constraint(
            batch_op.f("fk_squad_members_season_id_seasons"), type_="foreignkey"
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_squad_members_team_season_id_team_seasons"),
            "team_seasons",
            ["team_season_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_column("season_id")

    with op.batch_alter_table("fixtures", schema=None) as batch_op:
        batch_op.alter_column("team_season_id", nullable=False)
        batch_op.drop_index(batch_op.f("ix_fixtures_season_id_kickoff_at"))
        batch_op.drop_constraint(batch_op.f("uq_fixtures_season_id_match_number"), type_="unique")
        batch_op.create_index(
            "ix_fixtures_team_season_id_kickoff_at", ["team_season_id", "kickoff_at"], unique=False
        )
        batch_op.create_unique_constraint(
            batch_op.f("uq_fixtures_team_season_id_match_number"),
            ["team_season_id", "match_number"],
        )
        batch_op.drop_constraint(batch_op.f("fk_fixtures_season_id_seasons"), type_="foreignkey")
        batch_op.create_foreign_key(
            batch_op.f("fk_fixtures_team_season_id_team_seasons"),
            "team_seasons",
            ["team_season_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_column("season_id")

    with op.batch_alter_table("awards", schema=None) as batch_op:
        batch_op.alter_column("team_season_id", nullable=False)
        batch_op.drop_index(batch_op.f("ix_awards_season_id_award_type_id"))
        batch_op.create_index(
            "ix_awards_team_season_id_award_type_id",
            ["team_season_id", "award_type_id"],
            unique=False,
        )
        batch_op.drop_constraint(batch_op.f("fk_awards_season_id_seasons"), type_="foreignkey")
        batch_op.create_foreign_key(
            batch_op.f("fk_awards_team_season_id_team_seasons"),
            "team_seasons",
            ["team_season_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_column("season_id")

    # --- the rest ------------------------------------------------------------------
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cohort_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_players_cohort_id"), ["cohort_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_players_cohort_id_cohorts"),
            "cohorts",
            ["cohort_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    if seasons:
        conn.execute(
            sa.text(
                "UPDATE players SET cohort_id = (SELECT id FROM cohorts WHERE name = 'Born 2016/17')"
            )
        )

    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.drop_column("match_minutes")
        batch_op.drop_column("is_current")

    with op.batch_alter_table("award_types", schema=None) as batch_op:
        batch_op.add_column(sa.Column("club_team_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_award_types_club_team_id"), ["club_team_id"], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_award_types_club_team_id_club_teams"),
            "club_teams",
            ["club_team_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("teams", schema=None) as batch_op:
        batch_op.add_column(sa.Column("club_team_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_teams_club_team_id_club_teams"),
            "club_teams",
            ["club_team_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(length=100), nullable=True))
    conn.execute(
        sa.text(
            "INSERT INTO user_roles (user_id, role, scope_type, scope_id) SELECT id, 'admin', 'club', NULL FROM users"
        )
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_users_role"), type_="check")
        batch_op.drop_column("role")


def downgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.VARCHAR(length=20), nullable=False, server_default="coach")
        )
        batch_op.create_check_constraint(op.f("ck_users_role"), "role IN ('coach', 'admin')")
        batch_op.drop_column("display_name")
    conn.execute(
        sa.text(
            "UPDATE users SET role = 'admin' WHERE id IN (SELECT user_id FROM user_roles WHERE role = 'admin' AND scope_type = 'club')"
        )
    )

    with op.batch_alter_table("teams", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_teams_club_team_id_club_teams"), type_="foreignkey")
        batch_op.drop_column("club_team_id")

    with op.batch_alter_table("award_types", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_award_types_club_team_id_club_teams"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_award_types_club_team_id"))
        batch_op.drop_column("club_team_id")

    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_current", sa.BOOLEAN(), server_default=sa.text("'0'"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("match_minutes", sa.INTEGER(), server_default=sa.text("'50'"), nullable=False)
        )
    # Only one team's data can survive a downgrade; take the first club team.
    conn.execute(
        sa.text(
            "UPDATE seasons SET match_minutes = COALESCE((SELECT ts.match_minutes FROM team_seasons ts WHERE ts.season_id = seasons.id ORDER BY ts.id LIMIT 1), 50), "
            "is_current = COALESCE((SELECT ts.is_current FROM team_seasons ts WHERE ts.season_id = seasons.id ORDER BY ts.id LIMIT 1), 0)"
        )
    )

    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_players_cohort_id_cohorts"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_players_cohort_id"))
        batch_op.drop_column("cohort_id")

    for table in REMAP:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("season_id", sa.Integer(), nullable=True))
        conn.execute(
            sa.text(
                f"UPDATE {table} SET season_id = (SELECT ts.season_id FROM team_seasons ts WHERE ts.id = {table}.team_season_id)"
            )
        )

    with op.batch_alter_table("awards", schema=None) as batch_op:
        batch_op.alter_column("season_id", nullable=False)
        batch_op.drop_constraint(
            batch_op.f("fk_awards_team_season_id_team_seasons"), type_="foreignkey"
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_awards_season_id_seasons"),
            "seasons",
            ["season_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_index("ix_awards_team_season_id_award_type_id")
        batch_op.create_index(
            batch_op.f("ix_awards_season_id_award_type_id"),
            ["season_id", "award_type_id"],
            unique=False,
        )
        batch_op.drop_column("team_season_id")

    with op.batch_alter_table("fixtures", schema=None) as batch_op:
        batch_op.alter_column("season_id", nullable=False)
        batch_op.drop_constraint(
            batch_op.f("fk_fixtures_team_season_id_team_seasons"), type_="foreignkey"
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_fixtures_season_id_seasons"),
            "seasons",
            ["season_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_constraint(
            batch_op.f("uq_fixtures_team_season_id_match_number"), type_="unique"
        )
        batch_op.drop_index("ix_fixtures_team_season_id_kickoff_at")
        batch_op.create_unique_constraint(
            batch_op.f("uq_fixtures_season_id_match_number"), ["season_id", "match_number"]
        )
        batch_op.create_index(
            batch_op.f("ix_fixtures_season_id_kickoff_at"),
            ["season_id", "kickoff_at"],
            unique=False,
        )
        batch_op.drop_column("team_season_id")

    with op.batch_alter_table("squad_members", schema=None) as batch_op:
        batch_op.alter_column("season_id", nullable=False)
        batch_op.drop_constraint(
            batch_op.f("fk_squad_members_team_season_id_team_seasons"), type_="foreignkey"
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_squad_members_season_id_seasons"),
            "seasons",
            ["season_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_index(
            "uq_squad_members_team_season_id_squad_number",
            sqlite_where=sa.text("squad_number IS NOT NULL"),
        )
        batch_op.drop_constraint(
            batch_op.f("uq_squad_members_team_season_id_player_id"), type_="unique"
        )
        batch_op.create_index(
            batch_op.f("uq_squad_members_season_id_squad_number"),
            ["season_id", "squad_number"],
            unique=True,
            sqlite_where=sa.text("squad_number IS NOT NULL"),
        )
        batch_op.create_unique_constraint(
            batch_op.f("uq_squad_members_season_id_player_id"), ["season_id", "player_id"]
        )
        batch_op.drop_column("team_season_id")

    op.drop_table("team_seasons")
    with op.batch_alter_table("user_roles", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_roles_user_id"))
    op.drop_table("user_roles")
    op.drop_table("club_teams")
    op.drop_table("cohorts")
