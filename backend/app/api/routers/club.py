from fastapi import APIRouter

from app.api.deps import DB, Access
from app.schemas.club import (
    ClubTeamCreate,
    ClubTeamRead,
    ClubTeamUpdate,
    CohortCreate,
    CohortRead,
    CohortUpdate,
    TeamSeasonRead,
    TeamSeasonStart,
    TeamSeasonUpdate,
)
from app.schemas.player import SquadMemberRead, SquadMemberUpsert
from app.schemas.stats import CohortOverview, Leaderboard, SeasonSummary
from app.services.club import ClubTeamService, CohortService, TeamSeasonService
from app.services.players import PlayerService
from app.services.stats import StatsService

router = APIRouter(tags=["club"])


# --- cohorts (age groups) ------------------------------------------------------------


@router.get("/cohorts", response_model=list[CohortRead])
def list_cohorts(db: DB, access: Access):
    return CohortService(db, access).list_visible()


@router.post("/cohorts", response_model=CohortRead, status_code=201)
def create_cohort(data: CohortCreate, db: DB, access: Access):
    return CohortService(db, access).create(data)


@router.patch("/cohorts/{cohort_id}", response_model=CohortRead)
def update_cohort(cohort_id: int, data: CohortUpdate, db: DB, access: Access):
    return CohortService(db, access).update(cohort_id, data)


@router.get("/cohorts/{cohort_id}/overview", response_model=CohortOverview)
def cohort_overview(cohort_id: int, season_id: int, db: DB, access: Access):
    """Every team in the age group side by side, and each player's game time across them."""
    return StatsService(db, access).cohort_overview(cohort_id, season_id)


# --- club teams ---------------------------------------------------------------------


@router.get("/club-teams", response_model=list[ClubTeamRead])
def list_club_teams(db: DB, access: Access, cohort_id: int | None = None):
    return ClubTeamService(db, access).list_visible(cohort_id=cohort_id)


@router.post("/club-teams", response_model=ClubTeamRead, status_code=201)
def create_club_team(data: ClubTeamCreate, db: DB, access: Access):
    return ClubTeamService(db, access).create(data)


@router.get("/club-teams/by-slug/{slug}", response_model=ClubTeamRead)
def get_club_team_by_slug(slug: str, db: DB, access: Access):
    return ClubTeamService(db, access).get_by_slug(slug)


@router.get("/club-teams/{team_id}", response_model=ClubTeamRead)
def get_club_team(team_id: int, db: DB, access: Access):
    return ClubTeamService(db, access).get(team_id)


@router.patch("/club-teams/{team_id}", response_model=ClubTeamRead)
def update_club_team(team_id: int, data: ClubTeamUpdate, db: DB, access: Access):
    return ClubTeamService(db, access).update(team_id, data)


@router.get("/club-teams/{team_id}/seasons", response_model=list[TeamSeasonRead])
def list_team_seasons(team_id: int, db: DB, access: Access):
    return TeamSeasonService(db, access).list_for_team(team_id)


@router.post("/club-teams/{team_id}/seasons", response_model=TeamSeasonRead, status_code=201)
def start_team_season(team_id: int, data: TeamSeasonStart, db: DB, access: Access):
    """Roll the team into a season - optionally copying last season's squad forward."""
    return TeamSeasonService(db, access).start(team_id, data)


# --- team seasons -----------------------------------------------------------------


@router.get("/team-seasons/{team_season_id}", response_model=TeamSeasonRead)
def get_team_season(team_season_id: int, db: DB, access: Access):
    return TeamSeasonService(db, access).get(team_season_id)


@router.patch("/team-seasons/{team_season_id}", response_model=TeamSeasonRead)
def update_team_season(team_season_id: int, data: TeamSeasonUpdate, db: DB, access: Access):
    return TeamSeasonService(db, access).update(team_season_id, data)


@router.post("/team-seasons/{team_season_id}/make-current", response_model=TeamSeasonRead)
def make_current(team_season_id: int, db: DB, access: Access):
    return TeamSeasonService(db, access).make_current(team_season_id)


@router.get("/team-seasons/{team_season_id}/squad", response_model=list[SquadMemberRead])
def list_squad(team_season_id: int, db: DB, access: Access):
    return PlayerService(db, access).squad_for(team_season_id)


@router.put("/team-seasons/{team_season_id}/squad/{player_id}", response_model=SquadMemberRead)
def upsert_squad_member(
    team_season_id: int, player_id: int, data: SquadMemberUpsert, db: DB, access: Access
):
    return PlayerService(db, access).upsert_member(team_season_id, player_id, data)


@router.delete("/team-seasons/{team_season_id}/squad/{player_id}", status_code=204)
def remove_squad_member(team_season_id: int, player_id: int, db: DB, access: Access):
    PlayerService(db, access).remove_member(team_season_id, player_id)


@router.get("/team-seasons/{team_season_id}/stats/summary", response_model=SeasonSummary)
def season_summary(team_season_id: int, db: DB, access: Access):
    return StatsService(db, access).season_summary(team_season_id)


@router.get("/team-seasons/{team_season_id}/stats/leaderboard", response_model=Leaderboard)
def season_leaderboard(
    team_season_id: int, db: DB, access: Access, competition_type: str | None = None
):
    return StatsService(db, access).leaderboard(team_season_id, competition_type)
