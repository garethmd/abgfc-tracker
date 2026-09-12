from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    Appearance,
    Award,
    AwardScope,
    EventType,
    Fixture,
    FixtureStatus,
    MatchEvent,
)
from app.repositories.fixtures import FixtureRepository
from app.repositories.lookups import AwardTypeRepository, CompetitionRepository, PositionRepository
from app.repositories.players import PlayerRepository
from app.repositories.seasons import SeasonRepository
from app.repositories.teams import TeamRepository
from app.schemas.fixture import (
    AppearanceRead,
    AwardRead,
    FixtureCreate,
    FixtureDetail,
    FixtureUpdate,
    GoalRead,
    ResultSubmit,
)
from app.schemas.player import PlayerSummary
from app.services.stats import score_warnings


class FixtureService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FixtureRepository(db)

    def list_all(self, season_id=None, competition_id=None, status=None) -> list[Fixture]:
        return self.repo.list_all(season_id=season_id, competition_id=competition_id, status=status)

    def get(self, id: int) -> Fixture:
        return self.repo.get_or_404(id)

    def detail(self, id: int) -> FixtureDetail:
        fixture = self.repo.get_detail(id)
        if fixture is None:
            raise NotFoundError(f"Fixture {id} not found")
        return self._to_detail(fixture)

    def create(self, data: FixtureCreate) -> Fixture:
        SeasonRepository(self.db).get_or_404(data.season_id)
        CompetitionRepository(self.db).get_or_404(data.competition_id)
        TeamRepository(self.db).get_or_404(data.opposition_team_id)
        payload = data.model_dump()
        if payload["match_number"] is None:
            payload["match_number"] = self.repo.next_match_number(data.season_id)
        self._check_match_number(data.season_id, payload["match_number"], None)
        fixture = self.repo.add(Fixture(**payload))
        self.db.commit()
        return self.repo.get_detail(fixture.id)

    def update(self, id: int, data: FixtureUpdate) -> Fixture:
        fixture = self.repo.get_or_404(id)
        changes = data.model_dump(exclude_unset=True)
        if "competition_id" in changes:
            CompetitionRepository(self.db).get_or_404(changes["competition_id"])
        if "opposition_team_id" in changes:
            TeamRepository(self.db).get_or_404(changes["opposition_team_id"])
        if changes.get("match_number") is not None:
            self._check_match_number(fixture.season_id, changes["match_number"], id)
        for k, v in changes.items():
            setattr(fixture, k, v)
        if fixture.status == FixtureStatus.PLAYED and (
            fixture.our_score is None or fixture.their_score is None
        ):
            raise ValidationError("A played fixture needs both scores")
        self.db.commit()
        return self.repo.get_detail(id)

    def delete(self, id: int) -> None:
        fixture = self.repo.get_or_404(id)
        self.repo.delete(fixture)  # appearances/events/awards cascade
        self.db.commit()

    def submit_result(self, id: int, data: ResultSubmit) -> FixtureDetail:
        """Replace the fixture's whole result atomically and mark it played."""
        fixture = self.repo.get_detail(id)
        if fixture is None:
            raise NotFoundError(f"Fixture {id} not found")

        players = PlayerRepository(self.db)
        positions = PositionRepository(self.db)
        award_types = {a.id: a for a in AwardTypeRepository(self.db).list_all()}

        played_ids = {a.player_id for a in data.appearances}
        for a in data.appearances:
            players.get_or_404(a.player_id)
            if a.position_id is not None:
                positions.get_or_404(a.position_id)
        for g in data.goals:
            for pid in (g.scorer_id, g.assisted_by_id):
                if pid is not None and pid not in played_ids:
                    name = players.get_or_404(pid).display_name
                    raise ValidationError(f"{name} is credited with a goal/assist but didn't play")
        for aw in data.awards:
            at = award_types.get(aw.award_type_id)
            if at is None:
                raise NotFoundError(f"Award type {aw.award_type_id} not found")
            if at.scope != AwardScope.MATCH:
                raise ValidationError(f"{at.name} is not a per-match award")
            if aw.player_id not in played_ids:
                name = players.get_or_404(aw.player_id).display_name
                raise ValidationError(f"{name} won {at.name} but didn't play")

        fixture.appearances.clear()
        fixture.events.clear()
        fixture.awards.clear()
        self.db.flush()

        fixture.our_score = data.our_score
        fixture.their_score = data.their_score
        fixture.status = FixtureStatus.PLAYED
        for a in data.appearances:
            fixture.appearances.append(Appearance(**a.model_dump()))

        seq = 0
        for g in data.goals:
            seq += 1
            goal = MatchEvent(
                event_type=EventType(g.event_type),
                player_id=g.scorer_id,
                minute=g.minute,
                sequence=seq,
                notes=g.notes,
            )
            fixture.events.append(goal)
            if g.assisted_by_id is not None:
                seq += 1
                assist = MatchEvent(
                    event_type=EventType.ASSIST,
                    player_id=g.assisted_by_id,
                    minute=g.minute,
                    sequence=seq,
                    related_event=goal,
                )
                fixture.events.append(assist)

        seen: set[tuple[int, int]] = set()
        for aw in data.awards:
            key = (aw.award_type_id, aw.player_id)
            if key in seen:
                continue
            seen.add(key)
            fixture.awards.append(
                Award(
                    award_type_id=aw.award_type_id,
                    season_id=fixture.season_id,
                    player_id=aw.player_id,
                )
            )
        self.db.commit()
        return self.detail(id)

    # --- helpers ----------------------------------------------------------------

    def _check_match_number(self, season_id: int, number: int, exclude_id: int | None) -> None:
        for f in self.repo.list_all(season_id=season_id):
            if f.match_number == number and f.id != exclude_id:
                raise ConflictError(f"Match number {number} is already used this season")

    def _to_detail(self, fixture: Fixture) -> FixtureDetail:
        assists_by_goal = {
            e.related_event_id: e for e in fixture.events if e.event_type == EventType.ASSIST
        }
        goals = []
        for e in fixture.events:
            if e.event_type == EventType.ASSIST:
                continue
            assist = assists_by_goal.get(e.id)
            goals.append(
                GoalRead(
                    id=e.id,
                    event_type=e.event_type,
                    scorer=PlayerSummary.model_validate(e.player) if e.player else None,
                    assisted_by=PlayerSummary.model_validate(assist.player) if assist else None,
                    assist_event_id=assist.id if assist else None,
                    minute=e.minute,
                    sequence=e.sequence,
                    notes=e.notes,
                )
            )
        return FixtureDetail(
            **{
                k: getattr(fixture, k)
                for k in (
                    "id",
                    "season_id",
                    "competition",
                    "opposition",
                    "match_number",
                    "kickoff_at",
                    "venue",
                    "venue_notes",
                    "status",
                    "our_score",
                    "their_score",
                    "duration_minutes",
                    "notes",
                )
            },
            appearances=[AppearanceRead.model_validate(a) for a in fixture.appearances],
            goals=goals,
            awards=[AwardRead.model_validate(a) for a in fixture.awards],
            warnings=score_warnings(fixture),
        )
