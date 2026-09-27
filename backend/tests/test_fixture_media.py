"""YouTube videos on a fixture: media + media_links, no new tables."""

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ValidationError
from app.models import RoleScope, UserRole
from app.services.bootstrap import DemoSeason, seed_club_structure
from app.services.fixture_media import parse_youtube_id
from tests.conftest import login_as, make_user

API = "/api/v1"
VIDEO = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VIDEO}",
        f"https://www.youtube.com/watch?v={VIDEO}&t=42s",
        f"https://m.youtube.com/watch?app=desktop&v={VIDEO}",
        f"https://youtu.be/{VIDEO}",
        f"https://youtu.be/{VIDEO}?si=abcdef",
        f"https://www.youtube.com/shorts/{VIDEO}",
        f"https://www.youtube.com/embed/{VIDEO}",
        f"https://www.youtube.com/live/{VIDEO}",
        f"  https://youtu.be/{VIDEO}  ",
        VIDEO,
    ],
)
def test_parse_youtube_id_accepts_every_shape_a_coach_pastes(url: str):
    assert parse_youtube_id(url) == VIDEO


@pytest.mark.parametrize(
    "url",
    ["https://vimeo.com/12345", "https://example.com/watch?v=dQw4w9WgXcQ", "not a url", ""],
)
def test_parse_youtube_id_rejects_everything_else(url: str):
    with pytest.raises(ValidationError):
        parse_youtube_id(url)


def test_video_crud(auth_client: TestClient, demo: DemoSeason):
    fixture = demo.fixtures[0]
    url = f"{API}/fixtures/{fixture.id}/media"

    assert auth_client.get(url).json() == []

    r = auth_client.post(url, json={"url": f"https://youtu.be/{VIDEO}?si=x", "title": "First half"})
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["video_id"] == VIDEO
    assert v["url"] == f"https://www.youtube.com/watch?v={VIDEO}"  # stored canonical
    assert (v["title"], v["sort_order"], v["fixture_id"]) == ("First half", 0, fixture.id)

    # A second video sorts after the first.
    second = auth_client.post(url, json={"url": "https://www.youtube.com/watch?v=aBcDeFgHiJk"})
    assert second.status_code == 201 and second.json()["sort_order"] == 1
    assert [x["video_id"] for x in auth_client.get(url).json()] == [VIDEO, "aBcDeFgHiJk"]

    # The same video twice is a mistake, not two videos.
    r = auth_client.post(url, json={"url": f"https://www.youtube.com/embed/{VIDEO}"})
    assert r.status_code == 422 and "already" in r.json()["detail"]

    # Rubbish is refused while pasting, not when the card fails to play.
    assert auth_client.post(url, json={"url": "https://vimeo.com/12345"}).status_code == 422

    r = auth_client.patch(f"{url}/{v['id']}", json={"title": "Full match"})
    assert r.status_code == 200 and r.json()["title"] == "Full match"

    assert auth_client.delete(f"{url}/{v['id']}").status_code == 204
    assert [x["video_id"] for x in auth_client.get(url).json()] == ["aBcDeFgHiJk"]
    # Gone for good, and a second delete says so.
    assert auth_client.delete(f"{url}/{v['id']}").status_code == 404


def test_videos_go_with_the_fixture(auth_client: TestClient, demo: DemoSeason, db):
    """Deleting a fixture takes its videos with it - no orphaned media rows."""
    from app.models import Media

    fixture = demo.fixtures[0]
    auth_client.post(
        f"{API}/fixtures/{fixture.id}/media", json={"url": f"https://youtu.be/{VIDEO}"}
    )
    assert db.query(Media).count() == 1
    assert auth_client.delete(f"{API}/fixtures/{fixture.id}").status_code == 204
    db.expire_all()
    assert db.query(Media).count() == 0


def test_video_scoping(client: TestClient, db, demo: DemoSeason):
    """Anyone who can see the fixture can watch; only coaches can add or remove."""
    ts = seed_club_structure(db)
    make_user(db, "blues_coach", (UserRole.COACH, RoleScope.TEAM, ts["blues"].club_team_id))
    make_user(db, "reds_coach", (UserRole.COACH, RoleScope.TEAM, ts["reds"].club_team_id))
    make_user(db, "viewer", (UserRole.VIEWER, RoleScope.TEAM, ts["blues"].club_team_id))
    db.commit()
    fixture = demo.fixtures[0]
    url = f"{API}/fixtures/{fixture.id}/media"
    body = {"url": f"https://youtu.be/{VIDEO}"}

    login_as(client, "blues_coach")
    r = client.post(url, json=body)
    assert r.status_code == 201
    media_id = r.json()["id"]

    login_as(client, "viewer")
    assert len(client.get(url).json()) == 1  # viewers watch
    assert client.post(url, json={"url": "https://youtu.be/aBcDeFgHiJk"}).status_code == 403
    assert client.patch(f"{url}/{media_id}", json={"title": "x"}).status_code == 403
    assert client.delete(f"{url}/{media_id}").status_code == 403

    login_as(client, "reds_coach")  # another team can't even look
    assert client.get(url).status_code == 403
    assert client.post(url, json=body).status_code == 403
