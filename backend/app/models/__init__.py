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
    TokenPurpose,
    UserRole,
    Venue,
)
from app.models.fixture import Fixture
from app.models.ground import Ground
from app.models.invite import LoginToken
from app.models.lookup import AwardType, Competition, Position
from app.models.match import Appearance, MatchEvent, PlayerStint
from app.models.media import Media, MediaLink
from app.models.note import MatchNote
from app.models.passkey import Passkey, WebAuthnChallenge
from app.models.player import ParentAccessLog, Player, PlayerGuardian, SquadMember
from app.models.season import Season
from app.models.selection import FixtureSelection, GuestPlayer, UnavailablePlayer
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
    "LoginToken",
    "Passkey",
    "WebAuthnChallenge",
    "Player",
    "ParentAccessLog",
    "PlayerGuardian",
    "PlayerStint",
    "Position",
    "PositionCategory",
    "Season",
    "Ground",
    "GuestPlayer",
    "UnavailablePlayer",
    "FixtureSelection",
    "SquadMember",
    "TokenPurpose",
    "Team",
    "User",
    "UserRole",
    "Venue",
]
