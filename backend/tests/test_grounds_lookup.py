"""Placing a ground on a map, without hitting OpenStreetMap in the tests."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.models import Ground
from app.services import grounds as grounds_module

API = "/api/v1"


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(grounds_module.time, "sleep", lambda _: None)


@pytest.fixture
def osm(monkeypatch):
    """Stand in for Nominatim, counting calls so the cache can be proved."""
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"]["q"])
        q = kwargs["params"]["q"]
        hits = (
            [
                {
                    "lat": "51.2339023",
                    "lon": "-0.7416946",
                    "display_name": "Aldershot Park, Hampshire",
                }
            ]
            if "aldershot" in q
            else []
        )
        return httpx.Response(200, json=hits, request=httpx.Request("GET", url))

    monkeypatch.setattr(grounds_module.httpx, "get", fake_get)
    return calls


def test_a_ground_is_looked_up_once(auth_client: TestClient, db, osm):
    r = auth_client.get(f"{API}/grounds/lookup", params={"q": "Aldershot Park"})
    assert r.status_code == 200, r.text
    assert r.json()["found"] is True
    assert r.json()["lat"] == pytest.approx(51.2339023)

    # The pitch is dropped before searching, and the same place in another guise is a hit
    # on the cache rather than another request.
    again = auth_client.get(f"{API}/grounds/lookup", params={"q": "Aldershot Park 3"})
    assert again.json()["found"] is True
    assert osm == ["aldershot park"], "looked up twice"
    assert db.query(Ground).count() == 1


def test_a_postcode_rescues_an_abbreviated_name(auth_client: TestClient, osm, monkeypatch):
    """ "Grayshott Rec, GU26 6LS" defeats the geocoder; the postcode on its own does not."""
    monkeypatch.setattr(grounds_module.time, "sleep", lambda _: None)

    def fake_get(url, **kwargs):
        q = kwargs["params"]["q"]
        osm.append(q)
        hits = (
            [{"lat": "51.11223", "lon": "-0.76118", "display_name": "GU26 6LS, Grayshott"}]
            if q == "gu26 6ls"
            else []
        )
        return httpx.Response(200, json=hits, request=httpx.Request("GET", url))

    monkeypatch.setattr(grounds_module.httpx, "get", fake_get)
    r = auth_client.get(f"{API}/grounds/lookup", params={"q": "Grayshott Rec, GU26 6LS"})
    assert r.json()["found"] is True and r.json()["lat"] == pytest.approx(51.11223)
    assert osm == ["grayshott rec, gu26 6ls", "gu26 6ls"], "should stop at the first hit"


def test_a_ground_nobody_can_place(auth_client: TestClient, db, osm):
    r = auth_client.get(f"{API}/grounds/lookup", params={"q": "Zebon Copse Centre Pitch 1 - 5v5"})
    assert r.json() == {
        "query": "Zebon Copse Centre Pitch 1 - 5v5",
        "found": False,
        "display_name": None,
        "lat": None,
        "lon": None,
    }
    # The miss is remembered, so a page view doesn't ask again every time.
    auth_client.get(f"{API}/grounds/lookup", params={"q": "Zebon Copse Centre Pitch 1 - 5v5"})
    # Tried the name then the name without its trailing word, once, and remembered the miss.
    assert osm == ["zebon copse centre", "zebon copse"]


def test_the_geocoder_being_down_is_not_an_error(auth_client: TestClient, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectTimeout("nope")

    monkeypatch.setattr(grounds_module.httpx, "get", boom)
    r = auth_client.get(f"{API}/grounds/lookup", params={"q": "Aldershot Park"})
    assert r.status_code == 200 and r.json()["found"] is False


def test_what_gets_tried(auth_client: TestClient):
    """The shapes coaches actually write, and what makes each of them findable."""
    from app.services.grounds import candidates

    # A bracketed wing and a pitch nickname: only the plain school name lands.
    assert "south camberley primary school" in candidates(
        "South Camberley Primary School (Junior Campus) La Bombonera"
    )
    # A postcode is tried on its own, ahead of picking the name apart.
    assert candidates("Grayshott Rec, GU26 6LS")[1] == "gu26 6ls"
    # A plain name is one request, not four.
    assert candidates("Aldershot Park") == ["aldershot park"]


def test_the_search_is_bounded_to_the_area(auth_client: TestClient, monkeypatch):
    """Unbounded, a shortened name finds its namesake anywhere - "Kennels Lane" is a road
    in Leeds. Every ground the age group plays at is within an hour of Aldershot."""
    sent = {}

    def fake_get(url, **kwargs):
        sent.update(kwargs["params"])
        return httpx.Response(200, json=[], request=httpx.Request("GET", url))

    monkeypatch.setattr(grounds_module.httpx, "get", fake_get)
    auth_client.get(f"{API}/grounds/lookup", params={"q": "Kennels Lane #3"})
    assert sent["bounded"] == 1 and sent["viewbox"] == grounds_module.VIEWBOX
    assert sent["countrycodes"] == "gb"


def test_lookup_needs_a_login(client: TestClient, osm):
    assert client.get(f"{API}/grounds/lookup", params={"q": "Aldershot Park"}).status_code == 401
