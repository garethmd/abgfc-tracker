"""Turning a ground's name into a point on a map.

Grounds are recorded as the coach writes them ("Hook Junior School 7v7"), so to show a map
we ask OpenStreetMap's Nominatim where that is. OSM rather than Google: no API key, no
billing account and no third-party trackers loaded into an app full of children's names.

Nominatim asks callers to identify themselves and not to hammer it, so every answer -
including "no idea" - is cached in `grounds` and a name is looked up once, ever.
"""

import re
import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ground
from app.services.fixtures import map_query

NOMINATIM = "https://nominatim.openstreetmap.org/search"
# A UK postcode anywhere in the text. Coaches write them into the ground ("Grayshott Rec,
# GU26 6LS") and they are by far the most reliable thing to search for.
POSTCODE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b", re.I)
USER_AGENT = "abgfc-tracker (https://abgfc.neuralaspect.com)"
TIMEOUT = 5.0


def normalise(name: str) -> str:
    return " ".join(name.split()).lower()


def candidates(name: str) -> list[str]:
    """What to try, best first. Nominatim is good at a real place name and excellent at a
    postcode, but gives up on an abbreviation glued to one ("Grayshott Rec, GU26 6LS") or
    on a trailing generic word ("Zebon Copse Centre"). So: the name as written, then the
    postcode on its own, then the name with the postcode and finally its last word removed."""
    full = normalise(map_query(name))
    tries = [full]
    m = POSTCODE.search(name)
    if m:
        tries.append(normalise(f"{m.group(1)} {m.group(2)}"))
    without = normalise(POSTCODE.sub("", full).strip().strip(",").strip())
    if without and without != full:
        tries.append(without)
    words = (without or full).split()
    if len(words) >= 3:
        tries.append(" ".join(words[:-1]))
    seen: list[str] = []
    for t in tries:
        if t and t not in seen:
            seen.append(t)
    return seen[:3]  # three requests at most, and only ever once per ground


class GroundService:
    """Read-through cache over Nominatim. Never raises for a lookup failure: a map is a
    nicety, and a fixture page must not break because a geocoder is down."""

    def __init__(self, db: Session):
        self.db = db

    def lookup(self, name: str) -> Ground | None:
        query = normalise(map_query(name))
        if not query:
            return None
        cached = self.db.scalar(select(Ground).where(Ground.query == query))
        if cached is not None:
            return cached
        found = {"display_name": None, "lat": None, "lon": None}
        for i, attempt in enumerate(candidates(name)):
            if i:
                time.sleep(1)  # Nominatim asks for no more than one request a second
            found = self._ask_osm(attempt)
            if found["lat"] is not None:
                break
        ground = Ground(query=query, **found)
        self.db.add(ground)
        self.db.commit()
        return ground

    def _ask_osm(self, query: str) -> dict:
        try:
            r = httpx.get(
                NOMINATIM,
                params={"q": query, "countrycodes": "gb", "format": "json", "limit": 1},
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            hits = r.json()
        except (httpx.HTTPError, ValueError):
            # Down, slow or gibberish: cache nothing, so it can be tried again later.
            return {"display_name": None, "lat": None, "lon": None}
        if not hits:
            return {"display_name": None, "lat": None, "lon": None}  # cached as "not found"
        hit = hits[0]
        return {
            "display_name": hit.get("display_name"),
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
        }
