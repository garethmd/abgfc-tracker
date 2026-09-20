from enum import StrEnum


class CompetitionType(StrEnum):
    LEAGUE = "league"
    CUP = "cup"
    FRIENDLY = "friendly"
    TOURNAMENT = "tournament"


class Venue(StrEnum):
    HOME = "home"
    AWAY = "away"
    NEUTRAL = "neutral"


class FixtureStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"  # being recorded at the side of the pitch; becomes PLAYED on finish
    PLAYED = "played"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"


class SelectionStatus(StrEnum):
    """A player's availability for an upcoming match (a plan, not who played)."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class EventType(StrEnum):
    """Match events. Goals are the addressable thing (media attaches to them);
    an ASSIST row points at its GOAL via related_event_id."""

    GOAL = "goal"  # our player scores
    ASSIST = "assist"  # our player assists; related_event_id -> goal
    OWN_GOAL = "own_goal"  # our player, into our own net (counts for them)
    OPP_OWN_GOAL = "opp_own_goal"  # opposition own goal (counts for us, no player)


class AwardScope(StrEnum):
    MATCH = "match"
    MONTH = "month"
    SEASON = "season"


class PositionCategory(StrEnum):
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"


class MediaKind(StrEnum):
    YOUTUBE = "youtube"
    PHOTO = "photo"
    FILE = "file"


class UserRole(StrEnum):
    """Ordered: viewer < coach < admin."""

    VIEWER = "viewer"  # read only (parents, later)
    COACH = "coach"  # enter results, manage squad
    ADMIN = "admin"  # plus manage users, teams, seasons within the scope

    @property
    def level(self) -> int:
        return ["viewer", "coach", "admin"].index(self.value)


class RoleScope(StrEnum):
    CLUB = "club"
    COHORT = "cohort"
    TEAM = "team"


def check_in(column: str, enum: type[StrEnum]) -> str:
    """SQL fragment for a CHECK constraint restricting a column to an enum's values."""
    values = ", ".join(f"'{v.value}'" for v in enum)
    return f"{column} IN ({values})"
