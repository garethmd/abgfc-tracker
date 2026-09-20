from fastapi import APIRouter

from app.api.deps import DB, Access
from app.schemas.imports import ImportApply, ImportPasteRequest, ImportPreview, ImportResult
from app.services.imports import FixtureImportService

router = APIRouter(tags=["imports"])


@router.post("/team-seasons/{team_season_id}/fixtures/import/preview", response_model=ImportPreview)
def preview_import(team_season_id: int, data: ImportPasteRequest, db: DB, access: Access):
    """Classify fixtures pasted from FA Full-Time against what's already entered.
    Writes nothing."""
    return FixtureImportService(db, access).preview(team_season_id, data.text, data.html)


@router.post("/team-seasons/{team_season_id}/fixtures/import", response_model=ImportResult)
def apply_import(team_season_id: int, data: ImportApply, db: DB, access: Access):
    """Apply the coach's decisions from the preview."""
    return FixtureImportService(db, access).apply(team_season_id, data)
