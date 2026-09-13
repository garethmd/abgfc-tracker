from fastapi import APIRouter, Response

from app.api.deps import DB, Access
from app.services.reports import matchday_sheet

router = APIRouter(tags=["reports"])


@router.get(
    "/team-seasons/{team_season_id}/reports/matchday.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The matchday sheet"}},
)
def matchday_pdf(team_season_id: int, db: DB, access: Access, fixture_id: int | None = None):
    """One-page printable sheet for the next (or given) fixture: fixture details, season
    record, last match and awards, squad with appearances and tick boxes. Coaches only."""
    pdf, filename = matchday_sheet(db, access, team_season_id, fixture_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
