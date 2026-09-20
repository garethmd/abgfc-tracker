"""Import every model so SQLAlchemy can resolve string relationship targets."""

from app.models.award import Award
from app.models.club import ClubTeam, Cohort, TeamSeason
from app.models.enums import (
    AwardScope,
    CompetitionType,
    EventType,
    FixtureStatus,
    MediaKind,
    PositionCategory,
    RoleScope,
    SelectionStatus,
    UserRole,
    Venue,
)
from app.models.fixture import Fixture
from app.models.lookup import AwardType, Competition, Position
from app.models.match import Appearance, MatchEvent, PlayerStint
from app.models.media import Media, MediaLink
from app.models.note import MatchNote
from app.models.player import Player, SquadMember
from app.models.season import Season
from app.models.selection import FixtureSelection, SelectionPlayer
from app.models.team import Team
from app.models.user import User
from app.models.user import UserRole as UserRoleAssignment

__all__ = [
    "ClubTeam",
    "MatchNote",
    "Cohort",
    "RoleScope",
    "TeamSeason",
    "UserRoleAssignment",
    "Appearance",
    "Award",
    "AwardScope",
    "AwardType",
    "Competition",
    "CompetitionType",
    "EventType",
    "Fixture",
    "FixtureStatus",
    "MatchEvent",
    "Media",
    "MediaKind",
    "MediaLink",
    "Player",
    "PlayerStint",
    "Position",
    "PositionCategory",
    "Season",
    "SelectionPlayer",
    "SelectionStatus",
    "FixtureSelection",
    "SquadMember",
    "Team",
    "User",
    "UserRole",
    "Venue",
]
