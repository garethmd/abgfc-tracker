"""Match notes: WhatsApp reports pasted onto a fixture."""

from fastapi.testclient import TestClient

from app.models import RoleScope, UserRole
from app.services.bootstrap import DemoSeason
from tests.conftest import login_as, make_user

API = "/api/v1"

REPORT = """Great performance from the Blues today - 5-0 v Hook.
Archie with a hat-trick, Ayla and Kayson also on the scoresheet.
Parents' POTM: Ayla and Kayson (joint). Well done all! ⚽️"""


def test_add_edit_delete_note(auth_client: TestClient, demo: DemoSeason):
    fx = demo.fixtures[3]
    assert auth_client.get(f"{API}/fixtures/{fx.id}/notes").json() == []

    r = auth_client.post(
        f"{API}/fixtures/{fx.id}/notes",
        json={"body": REPORT, "author": "Stuart", "sent_at": "2026-09-12T12:30:00"},
    )
    assert r.status_code == 201, r.text
    note = r.json()
    assert (
        note["body"] == REPORT and note["author"] == "Stuart" and note["added_by"] == "Club admin"
    )
    assert note["sent_at"] == "2026-09-12T12:30:00"

    r = auth_client.post(f"{API}/fixtures/{fx.id}/notes", json={"body": "  Second message  "})
    assert r.status_code == 201 and r.json()["body"] == "Second message"
    notes = auth_client.get(f"{API}/fixtures/{fx.id}/notes").json()
    assert [n["author"] for n in notes] == ["Stuart", None]

    r = auth_client.patch(f"{API}/fixtures/{fx.id}/notes/{note['id']}", json={"author": "Gareth"})
    assert r.json()["author"] == "Gareth" and r.json()["body"] == REPORT

    assert auth_client.delete(f"{API}/fixtures/{fx.id}/notes/{note['id']}").status_code == 204
    assert len(auth_client.get(f"{API}/fixtures/{fx.id}/notes").json()) == 1
    # Note ids are checked against the fixture they belong to
    other = demo.fixtures[0]
    assert (
        auth_client.delete(f"{API}/fixtures/{other.id}/notes/{notes[1]['id']}").status_code == 404
    )
    assert auth_client.post(f"{API}/fixtures/{fx.id}/notes", json={"body": ""}).status_code == 422


def test_notes_follow_fixture_access(client: TestClient, db, demo: DemoSeason):
    team_id = demo.team_season.club_team_id
    make_user(db, "viewer", (UserRole.VIEWER, RoleScope.TEAM, team_id))
    make_user(db, "outsider", (UserRole.COACH, RoleScope.TEAM, team_id + 1))
    db.commit()
    fx = demo.fixtures[0]
    login_as(client, "viewer")
    assert client.get(f"{API}/fixtures/{fx.id}/notes").status_code == 200
    assert client.post(f"{API}/fixtures/{fx.id}/notes", json={"body": "x"}).status_code == 403
    login_as(client, "outsider")
    assert client.get(f"{API}/fixtures/{fx.id}/notes").status_code == 403


def test_notes_go_with_the_fixture(auth_client: TestClient, demo: DemoSeason):
    fx = demo.fixtures[7]
    auth_client.post(f"{API}/fixtures/{fx.id}/notes", json={"body": "postponed - waterlogged"})
    assert auth_client.delete(f"{API}/fixtures/{fx.id}").status_code == 204
    assert auth_client.get(f"{API}/fixtures/{fx.id}/notes").status_code == 404
