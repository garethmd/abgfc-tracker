from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import Player, SquadMember, UserRole
from app.repositories.club import TeamSeasonRepository
from app.repositories.lookups import PositionRepository
from app.repositories.players import PlayerRepository, SquadRepository
from app.schemas.player import PlayerCreate, PlayerMove, PlayerUpdate, SquadMemberUpsert
from app.services.access import Access


class PlayerService:
    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.repo = PlayerRepository(db)
        self.squad = SquadRepository(db)
        self.team_seasons = TeamSeasonRepository(db)

    def list_visible(self, cohort_id: int | None = None, include_left: bool = True) -> list[Player]:
        if cohort_id is not None:
            self.access.require_cohort(cohort_id)
        return self.repo.list_all(
            include_left=include_left,
            cohort_id=cohort_id,
            cohort_ids=self.access.visible_cohort_ids(),
        )

    def get(self, id: int, minimum: UserRole = UserRole.VIEWER) -> Player:
        player = self.repo.get_or_404(id)
        self.access.require_player(self.db, player, minimum)
        return player

    def create(self, data: PlayerCreate) -> Player:
        ts = None
        cohort_id = data.cohort_id
        if data.team_season_id is not None:
            ts = self._team_season(data.team_season_id, UserRole.COACH)
            cohort_id = cohort_id or ts.club_team.cohort_id
            if cohort_id != ts.club_team.cohort_id:
                raise ValidationError("Player's age group doesn't match the team's")
        if cohort_id is None:
            raise ValidationError("cohort_id or team_season_id is required")
        if ts is None:
            self.access.require_cohort(cohort_id, UserRole.COACH)

        payload = data.model_dump(exclude={"team_season_id", "squad_number", "cohort_id"})
        payload["display_name"] = payload["display_name"] or payload["first_name"]
        if self.repo.get_by_display_name(payload["display_name"], cohort_id):
            raise ConflictError(
                f"A player called '{payload['display_name']}' already exists in this age group"
            )
        player = self.repo.add(Player(cohort_id=cohort_id, **payload))
        if ts is not None:
            self._upsert_member(ts.id, player.id, SquadMemberUpsert(squad_number=data.squad_number))
        self.db.commit()
        return player

    def update(self, id: int, data: PlayerUpdate) -> Player:
        player = self.get(id, UserRole.COACH)
        changes = data.model_dump(exclude_unset=True)
        if "display_name" in changes and not changes["display_name"]:
            changes["display_name"] = changes.get("first_name") or player.first_name
        if "display_name" in changes:
            other = self.repo.get_by_display_name(changes["display_name"], player.cohort_id)
            if other and other.id != id:
                raise ConflictError(f"A player called '{changes['display_name']}' already exists")
        for k, v in changes.items():
            setattr(player, k, v)
        self.db.commit()
        return player

    def memberships(self, player_id: int) -> list[SquadMember]:
        self.get(player_id)
        visible = self.access.visible_team_ids()
        return [
            m
            for m in self.squad.memberships_for_player(player_id)
            if visible is None or m.team_season.club_team_id in visible
        ]

    # --- squad ------------------------------------------------------------------

    def squad_for(self, team_season_id: int) -> list[SquadMember]:
        self._team_season(team_season_id)
        return self.squad.list_for_team_season(team_season_id)

    def upsert_member(
        self, team_season_id: int, player_id: int, data: SquadMemberUpsert
    ) -> SquadMember:
        member = self._upsert_member(team_season_id, player_id, data)
        self.db.commit()
        self.db.refresh(member)
        return member

    def _upsert_member(
        self, team_season_id: int, player_id: int, data: SquadMemberUpsert
    ) -> SquadMember:
        ts = self._team_season(team_season_id, UserRole.COACH)
        player = self.repo.get_or_404(player_id)
        if player.cohort_id != ts.club_team.cohort_id:
            raise ValidationError(f"{player.display_name} is in a different age group")
        if data.primary_position_id is not None:
            PositionRepository(self.db).get_or_404(data.primary_position_id)
        if data.squad_number is not None:
            for m in self.squad.list_for_team_season(team_season_id):
                if m.squad_number == data.squad_number and m.player_id != player_id:
                    raise ConflictError(
                        f"Squad number {data.squad_number} is taken by {m.player.display_name}"
                    )
        member = self.squad.get_member(team_season_id, player_id)
        if member is None:
            member = SquadMember(team_season_id=team_season_id, player_id=player_id)
            self.db.add(member)
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(member, k, v)
        self.db.flush()
        return member

    def remove_member(self, team_season_id: int, player_id: int) -> None:
        self._team_season(team_season_id, UserRole.COACH)
        member = self.squad.get_member(team_season_id, player_id)
        if member is None:
            raise NotFoundError("Player is not in this squad")
        self.squad.delete(member)
        self.db.commit()

    def move(self, player_id: int, data: PlayerMove) -> SquadMember:
        """Age-group coach action: close membership on one team, open it on another."""
        player = self.repo.get_or_404(player_id)
        src = self._team_season(data.from_team_season_id, UserRole.COACH)
        dst = self._team_season(data.to_team_season_id, UserRole.COACH)
        if src.club_team.cohort_id != dst.club_team.cohort_id:
            raise ValidationError("Teams are in different age groups")
        if src.club_team_id != dst.club_team_id:
            self.access.require_cohort(src.club_team.cohort_id, UserRole.COACH)
        member = self.squad.get_member(src.id, player_id)
        if member is None:
            raise NotFoundError(f"{player.display_name} is not in that squad")
        from datetime import date

        member.left_at = data.left_at or date.today()
        new = self._upsert_member(
            dst.id, player_id, SquadMemberUpsert(squad_number=data.squad_number, left_at=None)
        )
        self.db.commit()
        self.db.refresh(new)
        return new

    def _team_season(self, id: int, minimum: UserRole = UserRole.VIEWER):
        ts = self.team_seasons.get(id)
        if ts is None:
            raise NotFoundError(f"Team season {id} not found")
        self.access.require_team_season(ts, minimum)
        return ts
