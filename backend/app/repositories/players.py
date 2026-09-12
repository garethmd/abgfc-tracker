from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Player, SquadMember
from app.repositories.base import BaseRepository


class PlayerRepository(BaseRepository[Player]):
    model = Player
    label = "Player"

    def list_all(
        self,
        include_left: bool = True,
        cohort_id: int | None = None,
        cohort_ids: set[int] | None = None,
    ) -> list[Player]:
        stmt = select(Player).order_by(Player.display_name)
        if not include_left:
            stmt = stmt.where(Player.left_date.is_(None))
        if cohort_id is not None:
            stmt = stmt.where(Player.cohort_id == cohort_id)
        if cohort_ids is not None:
            stmt = stmt.where(Player.cohort_id.in_(cohort_ids))
        return list(self.db.scalars(stmt))

    def get_by_display_name(self, name: str, cohort_id: int | None) -> Player | None:
        stmt = select(Player).where(Player.display_name == name)
        if cohort_id is not None:
            stmt = stmt.where(Player.cohort_id == cohort_id)
        return self.db.scalar(stmt)


class SquadRepository(BaseRepository[SquadMember]):
    model = SquadMember
    label = "Squad member"

    def list_for_team_season(self, team_season_id: int) -> list[SquadMember]:
        stmt = (
            select(SquadMember)
            .where(SquadMember.team_season_id == team_season_id)
            .options(selectinload(SquadMember.player), selectinload(SquadMember.primary_position))
            .join(SquadMember.player)
            .order_by(
                SquadMember.squad_number.is_(None), SquadMember.squad_number, Player.display_name
            )
        )
        return list(self.db.scalars(stmt))

    def get_member(self, team_season_id: int, player_id: int) -> SquadMember | None:
        return self.db.scalar(
            select(SquadMember).where(
                SquadMember.team_season_id == team_season_id, SquadMember.player_id == player_id
            )
        )

    def memberships_for_player(self, player_id: int) -> list[SquadMember]:
        from app.models import TeamSeason

        stmt = (
            select(SquadMember)
            .where(SquadMember.player_id == player_id)
            .options(
                selectinload(SquadMember.team_season).selectinload(TeamSeason.club_team),
                selectinload(SquadMember.team_season).selectinload(TeamSeason.season),
            )
        )
        return list(self.db.scalars(stmt))
