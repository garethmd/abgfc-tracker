"""The matchday sheet: one page, the right fixture, the squad with appearances, last week's
awards - and only for coaches."""

import re
from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.models import RoleScope, UserRole
from app.services.bootstrap import DemoSeason
from tests.conftest import login_as, make_user

API = "/api/v1"


def _text(pdf: bytes) -> tuple[int, str]:
    """Page count and text with runs of spaces collapsed (PDF text extraction is loose)."""
    reader = PdfReader(BytesIO(pdf))
    text = "\n".join(p.extract_text() for p in reader.pages)
    return len(reader.pages), re.sub(r"[ \t]+", " ", text)


def test_matchday_sheet_for_next_fixture(auth_client: TestClient, demo: DemoSeason):
    r = auth_client.get(f"{API}/team-seasons/{demo.team_season.id}/reports/matchday.pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert (
        r.headers["content-disposition"] == 'attachment; filename="blues-matchday-2026-10-17.pdf"'
    )
    pages, text = _text(r.content)
    assert pages == 1

    # Next scheduled fixture (match 7 v Fleet Spurs) with where and what
    assert "Sat 17 Oct, 10:00" in text and "Fleet Spurs" in text
    assert "Already played them: Drew 2-2 on Sat 12 Sep" in text  # match 2
    # Season record, both scopes, and form
    assert "All P6 W2 D1 L3 GF 12 GA 12" in text
    assert "League P4 W2 D1 L1 GF 11 GA 6" in text
    assert "Last 5 DLWLL" in text
    # Last match (match 6, lost 1-3 v Farnborough) with scorers and both POTMs
    assert "Lost 1-3 v Farnborough Town Youth" in text
    assert "Scorers: Noah (assist Archie)" in text
    assert "Coaches' POTM: Noah" in text and "Parents' POTM: Noah" in text
    # Squad rows: appearances out of matches played, goals, assists
    assert "Archie" in text and "6/6" in text
    assert "Teddy" in text and "2/6" in text
    assert "Shaded = fewest appearances so far" in text


def test_matchday_sheet_for_a_given_fixture(auth_client: TestClient, demo: DemoSeason):
    fx = demo.fixtures[7]  # postponed cup game v Hook
    r = auth_client.get(
        f"{API}/team-seasons/{demo.team_season.id}/reports/matchday.pdf?fixture_id={fx.id}"
    )
    assert r.status_code == 200
    _, text = _text(r.content)
    assert "Hook Juniors" in text and "Won 5-0 on Sat 26 Sep" in text
    assert "Sat 24 Oct" in text


def test_sheet_with_nothing_played_yet(auth_client: TestClient, db, demo: DemoSeason):
    from app.services.bootstrap import seed_club_structure

    reds = seed_club_structure(db)["reds"]
    db.commit()
    r = auth_client.get(f"{API}/team-seasons/{reds.id}/reports/matchday.pdf")
    assert r.status_code == 200
    pages, text = _text(r.content)
    assert pages == 1
    assert "No fixture scheduled" in text and "No matches played yet" in text and "None yet" in text


def test_sheet_is_coaches_only(client: TestClient, db, demo: DemoSeason):
    team_id = demo.team_season.club_team_id
    make_user(db, "viewer", (UserRole.VIEWER, RoleScope.TEAM, team_id))
    make_user(db, "other_coach", (UserRole.COACH, RoleScope.TEAM, team_id + 1))
    db.commit()
    login_as(client, "viewer")
    assert (
        client.get(f"{API}/team-seasons/{demo.team_season.id}/reports/matchday.pdf").status_code
        == 403
    )
    login_as(client, "other_coach")
    assert (
        client.get(f"{API}/team-seasons/{demo.team_season.id}/reports/matchday.pdf").status_code
        == 403
    )


def test_oklch_conversion():
    from app.services.reports import oklch_to_rgb

    r, g, b = oklch_to_rgb("oklch(0.5 0.2 258)")
    assert b > r and b > g  # a blue
    r, g, b = oklch_to_rgb("oklch(0.55 0.2 25)")
    assert r > g and r > b  # a red
    assert oklch_to_rgb(None) == (37, 99, 235)
    assert oklch_to_rgb("#ff0000") == (37, 99, 235)
