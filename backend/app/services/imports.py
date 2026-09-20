"""Import fixtures pasted from FA Full-Time.

The FA site blocks automated fetching (Cloudflare), so a coach copies the fixtures table
from the page and pastes it here. We accept the clipboard's HTML (which keeps the
`displayFixture.html?id=` links, i.e. stable FA fixture ids) and fall back to the plain
tab-separated text. Nothing is written until the coach confirms a preview in which every
row is classified: `existing` (same team, same date - only blanks get filled),
`create`, `conflict` (same date, different opponent - needs a decision) or `skip`
(another team's fixture).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html.parser import HTMLParser

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.models import (
    ClubTeam,
    Competition,
    CompetitionType,
    Fixture,
    FixtureStatus,
    Team,
    TeamSeason,
    UserRole,
    Venue,
)
from app.repositories.club import ClubTeamRepository, TeamSeasonRepository
from app.repositories.fixtures import FixtureRepository
from app.repositories.lookups import CompetitionRepository
from app.repositories.teams import TeamRepository
from app.schemas.imports import (
    ImportApply,
    ImportPreview,
    ImportResult,
    ImportRow,
    Suggestion,
)
from app.services.access import Access

DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{2,4})(?:\s+(\d{2}):(\d{2}))?$")
AGE_TOKEN = re.compile(r"^u\d{1,2}[a-z]?$")


# --- parsing -----------------------------------------------------------------------


@dataclass
class ParsedFixture:
    date: date
    time: str | None
    home: str
    away: str
    venue: str | None
    competition: str | None
    note: str | None
    external_id: str | None = None
    line: int = 0


class _TableParser(HTMLParser):
    """Rows of cell texts plus the first displayFixture id found in the row."""

    def __init__(self):
        super().__init__()
        self.rows: list[tuple[list[str], str | None]] = []
        self._cells: list[str] | None = None
        self._cell: list[str] | None = None
        self._id: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._cells, self._id = [], None
        elif tag in ("td", "th") and self._cells is not None:
            self._cell = []
        elif tag == "a" and self._cells is not None:
            href = dict(attrs).get("href") or ""
            m = re.search(r"displayFixture\.html\?id=(\d+)", href)
            if m and not self._id:
                self._id = m.group(1)
        elif tag == "img" and self._cell is not None:
            alt = dict(attrs).get("alt")
            if alt:
                self._cell.append(alt)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._cells is not None:
            self._cells.append(" ".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._cells is not None:
            if any(self._cells):
                self.rows.append((self._cells, self._id))
            self._cells = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data.strip())


def _cells_to_fixture(cells: list[str], external_id: str | None, line: int) -> ParsedFixture | None:
    cells = [c.strip() for c in cells if c and c.strip()]
    # locate the date cell; everything before it is the "Type" column
    idx = next((i for i, c in enumerate(cells) if DATE_RE.match(c)), None)
    if idx is None:
        return None
    m = DATE_RE.match(cells[idx])
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    y = y + 2000 if y < 100 else y
    when = date(y, mo, d)
    time = f"{m.group(4)}:{m.group(5)}" if m.group(4) else None
    rest = cells[idx + 1 :]
    # Team names appear twice (name + logo alt) around a "VS" cell: drop consecutive
    # duplicates, then home is the cell before VS and away the cell after it.
    deduped: list[str] = []
    for c in rest:
        if not deduped or c != deduped[-1]:
            deduped.append(c)
    vs = next((i for i, c in enumerate(deduped) if c.upper() in ("VS", "V")), None)
    if vs is None or vs == 0 or vs + 1 >= len(deduped):
        return None
    names = [deduped[vs - 1], deduped[vs + 1]]
    tail = deduped[vs + 2 :]
    # After both teams: venue, competition, optional status/notes
    venue = tail[0] if len(tail) > 0 else None
    competition = tail[1] if len(tail) > 1 else None
    note = " ".join(tail[2:]) if len(tail) > 2 else None
    return ParsedFixture(
        when, time, names[0], names[1], venue, competition, note, external_id, line
    )


def parse_fa_fixtures(text: str | None, html: str | None) -> list[ParsedFixture]:
    """Prefer the clipboard HTML (carries FA ids); fall back to tab-separated text."""
    out: list[ParsedFixture] = []
    if html and "<tr" in html.lower():
        p = _TableParser()
        p.feed(html)
        for i, (cells, ext) in enumerate(p.rows, start=1):
            f = _cells_to_fixture(cells, ext, i)
            if f:
                out.append(f)
    if not out and text:
        for i, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            cells = line.split("\t") if "\t" in line else re.split(r"\s{2,}", line)
            f = _cells_to_fixture(cells, None, i)
            if f:
                out.append(f)
    return out


# --- matching ---------------------------------------------------------------------


def norm(name: str) -> str:
    """Lower-case, drop age tokens (U10M, U9), punctuation and extra spaces."""
    tokens = re.sub(r"[^\w&\s]", " ", name.lower()).split()
    tokens = [t for t in tokens if not AGE_TOKEN.match(t)]
    return " ".join(tokens)


def similarity(a: str, b: str) -> float:
    """1.0 for the same normalised name, 0.9 when one's tokens are all in the other
    ("Hook Tigers" ⊂ "Hook U10M Tigers"), else the token-set overlap (Jaccard) - so
    "Haslemere Town Harriers" v "Haslemere Town Panthers" is 0.5, not a near-match."""
    na, nb = norm(a), norm(b)
    if na == nb:
        return 1.0
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return 0.0
    if ta <= tb or tb <= ta:
        return 0.9
    return len(ta & tb) / len(ta | tb)


def best_match(
    name: str, candidates: list[tuple[int, str]], threshold: float = 0.8
) -> Suggestion | None:
    scored = sorted(
        ((similarity(name, cname), cid, cname) for cid, cname in candidates), reverse=True
    )
    if scored and scored[0][0] >= threshold:
        score, cid, cname = scored[0]
        return Suggestion(id=cid, name=cname, confidence=round(score, 2))
    return None


def is_our_team(name: str, club_team: ClubTeam) -> bool:
    n = norm(name)
    return "aldershot" in n and club_team.name.lower() in n.split()


def which_club_team(name: str, club_teams: list[ClubTeam]) -> ClubTeam | None:
    return next((t for t in club_teams if is_our_team(name, t)), None)


def strip_age(name: str) -> str:
    """'Mytchett Athletic U10M Kestrels' -> 'Mytchett Athletic Kestrels' (U11M next year)."""
    return " ".join(t for t in name.split() if not AGE_TOKEN.match(t.lower())).strip()


def tidy_venue(v: str | None) -> str | None:
    if not v:
        return None
    return " ".join(w if not w.isupper() or len(w) <= 2 else w.title() for w in v.split())


# --- preview -----------------------------------------------------------------------


@dataclass
class _Ctx:
    ts: TeamSeason
    club_teams: list[ClubTeam]
    teams: list[Team]
    competitions: list[Competition]
    existing: dict[date, list[Fixture]] = field(default_factory=dict)
    by_external: dict[str, Fixture] = field(default_factory=dict)


class FixtureImportService:
    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access

    def _ctx(self, team_season_id: int) -> _Ctx:
        ts = TeamSeasonRepository(self.db).get(team_season_id)
        if ts is None:
            raise NotFoundError(f"Team season {team_season_id} not found")
        self.access.require_team_season(ts, UserRole.COACH)
        fixtures = FixtureRepository(self.db).list_all(team_season_id=ts.id)
        ctx = _Ctx(
            ts=ts,
            club_teams=ClubTeamRepository(self.db).list_all(),
            teams=TeamRepository(self.db).list_all(),
            competitions=CompetitionRepository(self.db).list_all(),
        )
        for f in fixtures:
            ctx.existing.setdefault(f.kickoff_at.date(), []).append(f)
            if f.external_id:
                ctx.by_external[f.external_id] = f
        return ctx

    def preview(self, team_season_id: int, text: str | None, html: str | None) -> ImportPreview:
        ctx = self._ctx(team_season_id)
        parsed = parse_fa_fixtures(text, html)
        if not parsed:
            raise ValidationError(
                "Couldn't find any fixtures in that - copy the whole fixtures table from Full-Time"
            )
        rows = [self._classify(ctx, p) for p in parsed]
        counts = {
            k: sum(1 for r in rows if r.action == k)
            for k in ("create", "existing", "conflict", "skip")
        }
        return ImportPreview(team_season_id=ctx.ts.id, rows=rows, counts=counts)

    def _classify(self, ctx: _Ctx, p: ParsedFixture) -> ImportRow:
        club_team = ctx.ts.club_team
        if is_our_team(p.home, club_team):
            venue, opp_name = Venue.HOME, p.away
        elif is_our_team(p.away, club_team):
            venue, opp_name = Venue.AWAY, p.home
        else:
            return ImportRow(
                line=p.line,
                date=p.date,
                time=p.time,
                home=p.home,
                away=p.away,
                venue_notes=tidy_venue(p.venue),
                competition_raw=p.competition,
                external_id=p.external_id,
                action="skip",
                reason=f"Not a {club_team.name} fixture",
            )

        # Is the opponent one of our own teams (a derby)?
        derby = which_club_team(opp_name, [t for t in ctx.club_teams if t.id != club_team.id])
        opp_candidates = [(t.id, t.name) for t in ctx.teams]
        opp = best_match(opp_name, opp_candidates)
        if derby is not None:
            linked = next((t for t in ctx.teams if t.club_team_id == derby.id), None)
            if linked is not None:
                opp = Suggestion(id=linked.id, name=linked.name, confidence=1.0)
        comp = (
            best_match(p.competition or "", [(c.id, c.name) for c in ctx.competitions], 0.75)
            if p.competition
            else None
        )

        base = dict(
            line=p.line,
            date=p.date,
            time=p.time,
            home=p.home,
            away=p.away,
            our_venue=venue,
            opposition_raw=opp_name,
            opposition=opp,
            derby_club_team_id=derby.id if derby else None,
            competition_raw=p.competition,
            competition=comp,
            venue_notes=tidy_venue(p.venue),
            external_id=p.external_id,
            status=_status_from_note(p.note),
        )

        # Already imported (same FA id) or already entered by hand (same date)?
        existing = ctx.by_external.get(p.external_id) if p.external_id else None
        if existing is None:
            same_day = ctx.existing.get(p.date, [])
            for f in same_day:
                if similarity(opp_name, f.opposition.name) >= 0.8 or (
                    derby and f.opposition.club_team_id == derby.id
                ):
                    existing = f
                    break
            if existing is None and same_day:
                f = same_day[0]
                return ImportRow(
                    **base,
                    action="conflict",
                    existing_fixture_id=f.id,
                    reason=(
                        f"Already have a fixture that day v {f.opposition.name} - "
                        "rearranged, or a different match?"
                    ),
                )
        if existing is not None:
            fills = [
                k
                for k, v in (("ground", existing.venue_notes), ("FA id", existing.external_id))
                if not v
            ]
            return ImportRow(
                **base,
                action="existing",
                existing_fixture_id=existing.id,
                reason=("Already entered; will fill in " + ", ".join(fills))
                if fills
                else "Already entered; nothing to change",
            )
        return ImportRow(**base, action="create", reason=None)

    # --- apply -----------------------------------------------------------------------

    def apply(self, team_season_id: int, data: ImportApply) -> ImportResult:
        ctx = self._ctx(team_season_id)
        fixtures = FixtureRepository(self.db)
        teams = TeamRepository(self.db)
        comps = CompetitionRepository(self.db)
        created = updated = skipped = 0
        new_teams: dict[str, Team] = {}
        new_comps: dict[str, Competition] = {}

        for row in data.rows:
            if row.action == "skip":
                skipped += 1
                continue
            if row.action == "update":
                f = fixtures.get_or_404(row.existing_fixture_id or 0)
                if f.team_season_id != ctx.ts.id:
                    raise ValidationError("Fixture belongs to another team")
                if not f.venue_notes and row.venue_notes:
                    f.venue_notes = row.venue_notes
                if not f.external_id and row.external_id:
                    f.external_id = row.external_id
                updated += 1
                continue
            # create
            if row.opposition_team_id is not None:
                opp = teams.get_or_404(row.opposition_team_id)
            else:
                name = strip_age((row.new_opposition_name or "").strip())
                if not name:
                    raise ValidationError(
                        f"Line {row.line}: choose an opposition team or give a name"
                    )
                opp = new_teams.get(norm(name)) or teams.get_by_name(name)
                if opp is None:
                    opp = Team(name=name, club_team_id=row.derby_club_team_id)
                    self.db.add(opp)
                    self.db.flush()
                    new_teams[norm(name)] = opp
            if row.competition_id is not None:
                comp = comps.get_or_404(row.competition_id)
            else:
                cname = (row.new_competition_name or "").strip()
                if not cname:
                    raise ValidationError(f"Line {row.line}: choose a competition or give a name")
                comp = new_comps.get(norm(cname)) or comps.get_by_name(cname)
                if comp is None:
                    comp = Competition(
                        name=cname, type=row.new_competition_type or CompetitionType.LEAGUE
                    )
                    self.db.add(comp)
                    self.db.flush()
                    new_comps[norm(cname)] = comp
            hh, mm = (row.time or "10:00").split(":")
            kickoff = datetime.combine(row.date, datetime.min.time()) + timedelta(
                hours=int(hh), minutes=int(mm)
            )
            f = Fixture(
                team_season_id=ctx.ts.id,
                competition_id=comp.id,
                opposition_team_id=opp.id,
                match_number=fixtures.next_match_number(ctx.ts.id),
                kickoff_at=kickoff,
                venue=row.our_venue or Venue.HOME,
                venue_notes=row.venue_notes,
                status=row.status or FixtureStatus.SCHEDULED,
                external_id=row.external_id,
            )
            self.db.add(f)
            self.db.flush()
            created += 1
        self.db.commit()
        return ImportResult(
            created=created,
            updated=updated,
            skipped=skipped,
            new_teams=[t.name for t in new_teams.values()],
            new_competitions=[c.name for c in new_comps.values()],
        )


def _status_from_note(note: str | None) -> FixtureStatus | None:
    if not note:
        return None
    n = note.lower()
    if "postpone" in n:
        return FixtureStatus.POSTPONED
    if "cancel" in n:
        return FixtureStatus.CANCELLED
    if "abandon" in n:
        return FixtureStatus.ABANDONED
    return None
