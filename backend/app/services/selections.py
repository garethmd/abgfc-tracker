"""Pre-match availability: who can play in an upcoming fixture and who can't.

A plan, not a record. `appearances` (who played) are only ever written by the result
flows; this never touches them. The selection is one aggregate - a header row with the
coaching/notes text and one row per player - replaced whole on every save, so a retried
PUT is harmless.
"""

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    Fixture,
    FixtureSelection,
    FixtureStatus,
    SelectionPlayer,
    SelectionStatus,
    UserRole,
)
from app.repositories.players import PlayerRepository, SquadRepository
from app.schemas.player import PlayerSummary
from app.schemas.selection import (
    ParentsMessage,
    SelectionPlayerRead,
    SelectionRead,
    SelectionSubmit,
)
from app.services.access import Access
from app.services.fixtures import FixtureService
from app.services.messages import MessageInput, arrival_time, parents_message

EDITABLE = {FixtureStatus.SCHEDULED, FixtureStatus.POSTPONED}


class SelectionService:
    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.fixtures = FixtureService(db, access)

    def get(self, fixture_id: int) -> SelectionRead | None:
        fixture = self.fixtures.get(fixture_id)  # viewer access
        if fixture.selection is None:
            return None
        return self._read(fixture)

    def put(self, fixture_id: int, data: SelectionSubmit) -> SelectionRead:
        fixture = self.fixtures.get(fixture_id, UserRole.COACH)
        if fixture.status not in EDITABLE:
            raise ConflictError("Availability can only be set before the match is played")
        self._check_players(fixture, [p.player_id for p in data.players])

        selection = fixture.selection
        if selection is None:
            selection = FixtureSelection(created_by_user_id=self.access.user.id)
            fixture.selection = selection
        selection.coaching = _clean(data.coaching)
        selection.notes = _clean(data.notes)
        selection.players.clear()
        self.db.flush()
        for p in data.players:
            selection.players.append(
                SelectionPlayer(player_id=p.player_id, status=SelectionStatus(p.status))
            )
        self.db.commit()
        self.db.refresh(fixture)
        return self._read(fixture)

    def delete(self, fixture_id: int) -> None:
        fixture = self.fixtures.get(fixture_id, UserRole.COACH)
        if fixture.selection is None:
            raise NotFoundError("No availability has been recorded for this fixture")
        fixture.selection = None
        self.db.commit()

    def message(self, fixture_id: int, *, date_line: bool) -> ParentsMessage:
        """The parents' message listing the available players (coaches - it names children)."""
        fixture = self.fixtures.get(fixture_id, UserRole.COACH)
        if fixture.selection is None:
            raise NotFoundError("Record who's available first")
        sel = self._read(fixture)
        text = parents_message(
            MessageInput(
                team_name=fixture.team_season.club_team.name,
                venue=fixture.venue,
                opposition=fixture.opposition.name,
                kickoff=fixture.kickoff_at,
                ground=fixture.venue_notes,
                arrival=sel.arrival_at,
                coaching=sel.coaching,
                squad=[p.player.display_name for p in sel.available],
                notes=sel.notes,
            ),
            date_line=date_line,
        )
        return ParentsMessage(text=text)

    # --- helpers ---------------------------------------------------------------

    def _check_players(self, fixture: Fixture, player_ids: list[int]) -> None:
        """Only children in this team's cohort (which includes its squad) can be picked."""
        players = PlayerRepository(self.db)
        cohort_id = fixture.team_season.club_team.cohort_id
        for pid in player_ids:
            p = players.get_or_404(pid)
            if p.cohort_id != cohort_id:
                raise ValidationError(f"{p.display_name} isn't in this team's age group")

    def _read(self, fixture: Fixture) -> SelectionRead:
        sel = fixture.selection
        assert sel is not None
        numbers = {
            m.player_id: m.squad_number
            for m in SquadRepository(self.db).list_for_team_season(fixture.team_season_id)
        }
        rows = sorted(
            sel.players,
            key=lambda r: (
                numbers.get(r.player_id) is None,
                numbers.get(r.player_id) or 0,
                r.player.display_name,
            ),
        )

        def group(status: SelectionStatus) -> list[SelectionPlayerRead]:
            return [
                SelectionPlayerRead(
                    player=PlayerSummary.model_validate(r.player),
                    squad_number=numbers.get(r.player_id),
                    status=r.status,
                )
                for r in rows
                if r.status == status
            ]

        lead = fixture.team_season.arrival_lead_minutes
        return SelectionRead(
            fixture_id=fixture.id,
            available=group(SelectionStatus.AVAILABLE),
            unavailable=group(SelectionStatus.UNAVAILABLE),
            arrival_at=arrival_time(fixture.kickoff_at, lead),
            arrival_lead_minutes=lead,
            coaching=sel.coaching,
            notes=sel.notes,
            updated_at=sel.updated_at,
        )


def _clean(s: str | None) -> str | None:
    s = (s or "").strip()
    return s or None
