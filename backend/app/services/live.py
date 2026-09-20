"""Live match entry: the same result as PUT /fixtures/{id}/result, written one tap at a
time from the side of the pitch.

A fixture moves scheduled -> live on kick-off and live -> played on finish. While live,
appearances, events and the score sit in their usual columns, so viewers see the running
score through the ordinary fixture endpoints and the stats engine ignores it (only
'played' counts). Nothing here touches FixtureService.submit_result beyond its guard
against writing over a match that is being tracked live.
"""

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import Appearance, EventType, Fixture, FixtureStatus, MatchEvent, UserRole
from app.repositories.players import PlayerRepository
from app.schemas.fixture import FixtureDetail, LiveGoal, LiveSquad
from app.services.access import Access
from app.services.fixtures import FixtureService


class LiveMatchService:
    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.fixtures = FixtureService(db, access)

    # --- lifecycle -------------------------------------------------------------

    def start(self, fixture_id: int, data: LiveSquad) -> FixtureDetail:
        fixture = self.fixtures.get(fixture_id, UserRole.COACH)
        if fixture.status == FixtureStatus.LIVE:
            raise ConflictError("This match is already being tracked live")
        if fixture.status != FixtureStatus.SCHEDULED:
            raise ConflictError("Only a scheduled fixture can be started")
        if fixture.appearances or fixture.events or fixture.awards:
            # A scheduled fixture shouldn't have a result on it; if one does (someone
            # PATCHed a played match back), never throw it away from here.
            raise ConflictError("This fixture already has a result recorded - use Enter result")
        self._check_players(data.player_ids)

        fixture.status = FixtureStatus.LIVE
        fixture.our_score = 0
        fixture.their_score = 0
        for pid in data.player_ids:
            fixture.appearances.append(Appearance(player_id=pid, started=True))
        self.db.commit()
        return self.fixtures.detail(fixture_id)

    def set_squad(self, fixture_id: int, data: LiveSquad) -> FixtureDetail:
        """Late arrival or a no-show. Anyone with a goal or assist stays."""
        fixture = self._live(fixture_id)
        self._check_players(data.player_ids)
        keep = set(data.player_ids)
        for e in fixture.events:
            if e.player_id is not None and e.player_id not in keep:
                raise ValidationError(f"{e.player.display_name} has a goal or assist recorded")
        current = {a.player_id: a for a in fixture.appearances}
        for pid, a in current.items():
            if pid not in keep:
                fixture.appearances.remove(a)
        for pid in data.player_ids:
            if pid not in current:
                fixture.appearances.append(Appearance(player_id=pid, started=True))
        self.db.commit()
        return self.fixtures.detail(fixture_id)

    def finish(self, fixture_id: int) -> FixtureDetail:
        fixture = self._live(fixture_id)
        fixture.status = FixtureStatus.PLAYED
        self.db.commit()
        return self.fixtures.detail(fixture_id)

    def abandon(self, fixture_id: int) -> None:
        """Started by mistake: back to scheduled with nothing recorded."""
        fixture = self._live(fixture_id)
        fixture.appearances.clear()
        fixture.events.clear()
        fixture.awards.clear()
        fixture.our_score = None
        fixture.their_score = None
        fixture.status = FixtureStatus.SCHEDULED
        self.db.commit()

    # --- goals -----------------------------------------------------------------

    def add_goal(self, fixture_id: int, data: LiveGoal) -> FixtureDetail:
        fixture = self._live(fixture_id)
        existing = next((e for e in fixture.events if e.sequence == data.sequence), None)
        if existing is not None:
            if self._same_goal(existing, fixture, data):
                return self.fixtures.detail(fixture_id)  # a retry; already recorded
            raise ConflictError("Another goal was recorded in the meantime - refresh and try again")
        played = {a.player_id: a.player for a in fixture.appearances}
        for pid in (data.scorer_id, data.assisted_by_id):
            if pid is not None and pid not in played:
                name = PlayerRepository(self.db).get_or_404(pid).display_name
                raise ValidationError(f"{name} isn't playing")

        event_type = EventType(data.event_type)
        goal = MatchEvent(
            event_type=event_type,
            player_id=data.scorer_id,
            minute=data.minute,
            sequence=data.sequence,
            notes=data.notes,
        )
        fixture.events.append(goal)
        if data.assisted_by_id is not None:
            fixture.events.append(
                MatchEvent(
                    event_type=EventType.ASSIST,
                    player_id=data.assisted_by_id,
                    minute=data.minute,
                    sequence=data.sequence + 1,
                    related_event=goal,
                )
            )
        if event_type == EventType.OWN_GOAL:
            fixture.their_score = (fixture.their_score or 0) + 1
        else:
            fixture.our_score = (fixture.our_score or 0) + 1
        self.db.commit()
        return self.fixtures.detail(fixture_id)

    def remove_goal(self, fixture_id: int, event_id: int) -> FixtureDetail:
        """Undo: drops the goal and its assist and takes it off the score."""
        fixture = self._live(fixture_id)
        goal = next(
            (e for e in fixture.events if e.id == event_id and e.event_type != EventType.ASSIST),
            None,
        )
        if goal is None:
            raise NotFoundError(f"Goal {event_id} not found on this fixture")
        for e in [e for e in fixture.events if e.related_event_id == goal.id]:
            fixture.events.remove(e)
        fixture.events.remove(goal)
        if goal.event_type == EventType.OWN_GOAL:
            fixture.their_score = max(0, (fixture.their_score or 0) - 1)
        else:
            fixture.our_score = max(0, (fixture.our_score or 0) - 1)
        self.db.commit()
        return self.fixtures.detail(fixture_id)

    def goal_against(self, fixture_id: int) -> FixtureDetail:
        """Opposition goals have no event; they are just the score."""
        fixture = self._live(fixture_id)
        fixture.their_score = (fixture.their_score or 0) + 1
        self.db.commit()
        return self.fixtures.detail(fixture_id)

    def remove_goal_against(self, fixture_id: int) -> FixtureDetail:
        fixture = self._live(fixture_id)
        own_goals = sum(1 for e in fixture.events if e.event_type == EventType.OWN_GOAL)
        if (fixture.their_score or 0) <= own_goals:
            raise ValidationError("No opposition goal to remove")
        fixture.their_score = (fixture.their_score or 0) - 1
        self.db.commit()
        return self.fixtures.detail(fixture_id)

    # --- helpers ---------------------------------------------------------------

    def _live(self, fixture_id: int) -> Fixture:
        fixture = self.fixtures.get(fixture_id, UserRole.COACH)
        if fixture.status != FixtureStatus.LIVE:
            raise ConflictError("This match isn't being tracked live")
        return fixture

    def _check_players(self, player_ids: list[int]) -> None:
        players = PlayerRepository(self.db)
        for pid in player_ids:
            players.get_or_404(pid)

    @staticmethod
    def _same_goal(existing: MatchEvent, fixture: Fixture, data: LiveGoal) -> bool:
        if existing.event_type != data.event_type or existing.player_id != data.scorer_id:
            return False
        assist = next((e for e in fixture.events if e.related_event_id == existing.id), None)
        return (assist.player_id if assist else None) == data.assisted_by_id
