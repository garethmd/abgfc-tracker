from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Player, SquadMember
from app.repositories.base import BaseRepository


class PlayerRepository(BaseRepository[Player]):
    model = Player
    label = "Player"

    def list_all(self, include_left: bool = True) -> list[Player]:
        stmt = select(Player).order_by(Player.display_name)
        if not include_left:
            stmt = stmt.where(Player.left_date.is_(None))
        return list(self.db.scalars(stmt))

    def get_by_display_name(self, name: str) -> Player | None:
        return self.db.scalar(select(Player).where(Player.display_name == name))


class SquadRepository(BaseRepository[SquadMember]):
    model = SquadMember
    label = "Squad member"

    def list_for_season(self, season_id: int) -> list[SquadMember]:
        stmt = (
            select(SquadMember)
            .where(SquadMember.season_id == season_id)
            .options(selectinload(SquadMember.player), selectinload(SquadMember.primary_position))
            .join(SquadMember.player)
            .order_by(
                SquadMember.squad_number.is_(None), SquadMember.squad_number, Player.display_name
            )
        )
        return list(self.db.scalars(stmt))

    def get_member(self, season_id: int, player_id: int) -> SquadMember | None:
        return self.db.scalar(
            select(SquadMember).where(
                SquadMember.season_id == season_id, SquadMember.player_id == player_id
            )
        )
