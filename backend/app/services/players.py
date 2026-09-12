from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import Player, SquadMember
from app.repositories.lookups import PositionRepository
from app.repositories.players import PlayerRepository, SquadRepository
from app.repositories.seasons import SeasonRepository
from app.schemas.player import PlayerCreate, PlayerUpdate, SquadMemberUpsert


class PlayerService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PlayerRepository(db)
        self.squad = SquadRepository(db)

    def list_all(self, include_left: bool = True) -> list[Player]:
        return self.repo.list_all(include_left=include_left)

    def get(self, id: int) -> Player:
        return self.repo.get_or_404(id)

    def create(self, data: PlayerCreate) -> Player:
        payload = data.model_dump(exclude={"season_id", "squad_number"})
        payload["display_name"] = payload["display_name"] or payload["first_name"]
        if self.repo.get_by_display_name(payload["display_name"]):
            raise ConflictError(f"A player called '{payload['display_name']}' already exists")
        player = self.repo.add(Player(**payload))
        if data.season_id is not None:
            self._upsert_member(
                data.season_id, player.id, SquadMemberUpsert(squad_number=data.squad_number)
            )
        self.db.commit()
        return player

    def update(self, id: int, data: PlayerUpdate) -> Player:
        player = self.repo.get_or_404(id)
        changes = data.model_dump(exclude_unset=True)
        if "display_name" in changes and not changes["display_name"]:
            changes["display_name"] = changes.get("first_name") or player.first_name
        if "display_name" in changes:
            other = self.repo.get_by_display_name(changes["display_name"])
            if other and other.id != id:
                raise ConflictError(f"A player called '{changes['display_name']}' already exists")
        for k, v in changes.items():
            setattr(player, k, v)
        self.db.commit()
        return player

    # --- squad ------------------------------------------------------------------

    def squad_for(self, season_id: int) -> list[SquadMember]:
        SeasonRepository(self.db).get_or_404(season_id)
        return self.squad.list_for_season(season_id)

    def upsert_member(self, season_id: int, player_id: int, data: SquadMemberUpsert) -> SquadMember:
        member = self._upsert_member(season_id, player_id, data)
        self.db.commit()
        self.db.refresh(member)
        return member

    def _upsert_member(
        self, season_id: int, player_id: int, data: SquadMemberUpsert
    ) -> SquadMember:
        SeasonRepository(self.db).get_or_404(season_id)
        self.repo.get_or_404(player_id)
        if data.primary_position_id is not None:
            PositionRepository(self.db).get_or_404(data.primary_position_id)
        if data.squad_number is not None:
            for m in self.squad.list_for_season(season_id):
                if m.squad_number == data.squad_number and m.player_id != player_id:
                    raise ConflictError(
                        f"Squad number {data.squad_number} is taken by {m.player.display_name}"
                    )
        member = self.squad.get_member(season_id, player_id)
        if member is None:
            member = SquadMember(season_id=season_id, player_id=player_id)
            self.db.add(member)
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(member, k, v)
        self.db.flush()
        return member

    def remove_member(self, season_id: int, player_id: int) -> None:
        member = self.squad.get_member(season_id, player_id)
        if member is None:
            raise NotFoundError("Player is not in this season's squad")
        self.squad.delete(member)
        self.db.commit()
