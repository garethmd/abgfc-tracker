"""Player profile photos: private storage, stripped metadata, scoped access."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.models import Media, MediaLink, RoleScope, UserRole
from app.services.bootstrap import DemoSeason
from tests.conftest import login_as, make_user

API = "/api/v1"


@pytest.fixture(autouse=True)
def media_dir(tmp_path, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "media_dir", tmp_path / "media")
    return tmp_path / "media"


def _jpeg(w=1600, h=900, with_exif=True) -> bytes:
    img = Image.new("RGB", (w, h), (30, 90, 200))
    buf = io.BytesIO()
    if with_exif:
        exif = img.getexif()
        exif[0x0112] = 6  # orientation: rotate 90 - must be applied then dropped
        exif[0x010F] = "iPhone"  # any metadata must be gone after upload
        img.save(buf, "JPEG", exif=exif)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


def test_upload_serve_replace_delete(auth_client: TestClient, demo: DemoSeason, db, media_dir):
    archie = demo.players["Archie"].id
    assert auth_client.get(f"{API}/players/{archie}/photo").status_code == 404
    assert auth_client.get(f"{API}/players/{archie}").json()["photo_key"] is None

    r = auth_client.put(
        f"{API}/players/{archie}/photo", files={"file": ("me.jpg", _jpeg(), "image/jpeg")}
    )
    assert r.status_code == 200, r.text
    photo_key = r.json()["photo_key"]
    assert photo_key

    # Stored privately, two sizes, no EXIF, orientation applied (1600x900 rotated -> portrait)
    files = sorted(p.name for p in (media_dir / "players" / str(archie)).iterdir())
    assert len(files) == 2 and all(f.endswith(".jpg") for f in files)
    r = auth_client.get(f"{API}/players/{archie}/photo")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "private, max-age=86400"
    full = Image.open(io.BytesIO(r.content))
    assert full.size == (675, 1200) and not full.getexif()
    thumb = Image.open(
        io.BytesIO(auth_client.get(f"{API}/players/{archie}/photo?size=thumb").content)
    )
    assert thumb.size == (256, 256)
    assert auth_client.get(f"{API}/players/{archie}/photo?size=huge").status_code == 422

    # Shows up on the squad list and summaries
    squad = auth_client.get(f"{API}/team-seasons/{demo.team_season.id}/squad").json()
    assert next(m for m in squad if m["player"]["id"] == archie)["player"]["photo_key"] == photo_key

    # Replace: old files and media row gone, one link remains
    r = auth_client.put(
        f"{API}/players/{archie}/photo", files={"file": ("new.png", _png(), "image/png")}
    )
    assert r.status_code == 200 and r.json()["photo_key"] != photo_key
    assert len(list((media_dir / "players" / str(archie)).iterdir())) == 2
    assert db.query(Media).count() == 1 and db.query(MediaLink).count() == 1

    assert auth_client.delete(f"{API}/players/{archie}/photo").status_code == 204
    assert auth_client.get(f"{API}/players/{archie}/photo").status_code == 404
    assert not list((media_dir / "players" / str(archie)).iterdir())
    assert db.query(Media).count() == 0


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (300, 300), (255, 0, 0, 128)).save(buf, "PNG")
    return buf.getvalue()


def test_rejects_non_images_and_huge_files(auth_client: TestClient, demo: DemoSeason):
    archie = demo.players["Archie"].id
    r = auth_client.put(
        f"{API}/players/{archie}/photo", files={"file": ("x.jpg", b"not an image", "image/jpeg")}
    )
    assert r.status_code == 422 and "image" in r.json()["detail"]
    r = auth_client.put(
        f"{API}/players/{archie}/photo",
        files={"file": ("x.jpg", b"0" * (15 * 1024 * 1024 + 1), "image/jpeg")},
    )
    assert r.status_code == 422 and "large" in r.json()["detail"]


def test_photo_access_is_scoped(client: TestClient, auth_client: TestClient, db, demo: DemoSeason):
    from app.services.bootstrap import seed_club_structure

    ts = seed_club_structure(db)
    team_id = demo.team_season.club_team_id
    make_user(db, "viewer", (UserRole.VIEWER, RoleScope.TEAM, team_id))
    make_user(db, "reds", (UserRole.COACH, RoleScope.TEAM, ts["reds"].club_team_id))
    other_cohort = auth_client.post(
        f"{API}/cohorts", json={"name": "Born 2014/15", "birth_year_start": 2014}
    ).json()
    other_team = auth_client.post(
        f"{API}/club-teams", json={"cohort_id": other_cohort["id"], "name": "U12"}
    ).json()
    make_user(db, "u12", (UserRole.COACH, RoleScope.TEAM, other_team["id"]))
    db.commit()
    archie = demo.players["Archie"].id
    auth_client.put(
        f"{API}/players/{archie}/photo", files={"file": ("me.jpg", _jpeg(), "image/jpeg")}
    )

    login_as(client, "viewer")  # same team: can see, can't change
    assert client.get(f"{API}/players/{archie}/photo").status_code == 200
    assert (
        client.put(
            f"{API}/players/{archie}/photo", files={"file": ("me.jpg", _jpeg(), "image/jpeg")}
        ).status_code
        == 403
    )
    assert client.delete(f"{API}/players/{archie}/photo").status_code == 403
    login_as(client, "reds")  # same cohort, other team: can see (squad pool), can't change
    assert client.get(f"{API}/players/{archie}/photo").status_code == 200
    assert client.delete(f"{API}/players/{archie}/photo").status_code == 403
    login_as(client, "u12")  # other age group: nothing
    assert client.get(f"{API}/players/{archie}/photo").status_code == 403
