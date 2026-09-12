"""Read-only aggregate queries feeding services/stats.py."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Appearance, Award, MatchEvent, PlayerStint
from app.repositories.base import BaseRepository


class StatsRepository(BaseRepository[Appearance]):
    model = Appearance

    def appearances_for(self, fixture_ids: Sequence[int]) -> list[Appearance]:
        if not fixture_ids:
            return []
        stmt = (
            select(Appearance)
            .where(Appearance.fixture_id.in_(fixture_ids))
            .options(selectinload(Appearance.player), selectinload(Appearance.stints))
        )
        return list(self.db.scalars(stmt))

    def events_for(self, fixture_ids: Sequence[int]) -> list[MatchEvent]:
        if not fixture_ids:
            return []
        stmt = select(MatchEvent).where(MatchEvent.fixture_id.in_(fixture_ids))
        return list(self.db.scalars(stmt))

    def match_awards_for(self, fixture_ids: Sequence[int]) -> list[Award]:
        if not fixture_ids:
            return []
        stmt = select(Award).where(Award.fixture_id.in_(fixture_ids))
        return list(self.db.scalars(stmt))

    def appearances_for_player(
        self, player_id: int, fixture_ids: Sequence[int]
    ) -> list[Appearance]:
        if not fixture_ids:
            return []
        stmt = (
            select(Appearance)
            .where(Appearance.player_id == player_id, Appearance.fixture_id.in_(fixture_ids))
            .options(selectinload(Appearance.stints).selectinload(PlayerStint.position))
        )
        return list(self.db.scalars(stmt))
