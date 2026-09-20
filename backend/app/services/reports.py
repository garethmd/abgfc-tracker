"""Printable reports. Today: the one-page matchday sheet a coach takes to the pitch.

Pure Python (fpdf2) so the API image needs no system packages. Data comes from the same
services the UI uses; this module only lays it out.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import CompetitionType, Fixture, FixtureStatus, TeamSeason, UserRole
from app.repositories.club import TeamSeasonRepository
from app.repositories.fixtures import FixtureRepository
from app.schemas.fixture import FixtureDetail
from app.schemas.stats import PlayerStatsRow
from app.services.access import Access
from app.services.fixtures import FixtureService
from app.services.stats import StatsService, form, outcome, team_record

CREST = Path(__file__).resolve().parent.parent / "assets" / "crest.png"

# --- colour ------------------------------------------------------------------------


def oklch_to_rgb(value: str | None, fallback=(37, 99, 235)) -> tuple[int, int, int]:
    """'oklch(0.5 0.2 258)' -> sRGB 8-bit. Team colours are stored as CSS oklch."""
    if not value:
        return fallback
    m = re.match(r"oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)", value)
    if not m:
        return fallback
    L, C, H = float(m.group(1)), float(m.group(2)), math.radians(float(m.group(3)))
    a, b = C * math.cos(H), C * math.sin(H)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l3, m3, s3 = l_**3, m_**3, s_**3
    r = 4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3
    g = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3
    bl = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3

    def gamma(x: float) -> int:
        x = max(0.0, min(1.0, x))
        x = 1.055 * x ** (1 / 2.4) - 0.055 if x > 0.0031308 else 12.92 * x
        return round(max(0.0, min(1.0, x)) * 255)

    return gamma(r), gamma(g), gamma(bl)


# --- data --------------------------------------------------------------------------


@dataclass
class MatchdayData:
    team_season: TeamSeason
    fixture: Fixture | None  # the fixture the sheet is for (usually the next one)
    previous_meetings: list[Fixture]  # played fixtures v the same opposition this season
    played: list[Fixture]
    last_match: FixtureDetail | None
    rows: list[PlayerStatsRow]
    generated_at: datetime


def gather(
    db: Session, access: Access, team_season_id: int, fixture_id: int | None
) -> MatchdayData:
    ts = TeamSeasonRepository(db).get(team_season_id)
    if ts is None:
        raise NotFoundError(f"Team season {team_season_id} not found")
    access.require_team_season(ts, UserRole.COACH)  # coaches only - it names children

    fixtures = FixtureRepository(db)
    all_fixtures = fixtures.list_all(team_season_id=ts.id)
    played = [f for f in all_fixtures if f.status == FixtureStatus.PLAYED]
    if fixture_id is not None:
        fixture = next((f for f in all_fixtures if f.id == fixture_id), None)
        if fixture is None:
            raise NotFoundError(f"Fixture {fixture_id} not in this team season")
    else:
        upcoming = [
            f for f in all_fixtures if f.status in (FixtureStatus.SCHEDULED, FixtureStatus.LIVE)
        ]
        fixture = upcoming[0] if upcoming else None

    previous = (
        [
            f
            for f in played
            if f.opposition_team_id == fixture.opposition_team_id and f.id != fixture.id
        ]
        if fixture
        else []
    )
    last = FixtureService(db, access).detail(played[-1].id) if played else None
    rows = StatsService(db, access).leaderboard(ts.id).rows
    return MatchdayData(ts, fixture, previous, played, last, rows, datetime.now())


# --- layout ------------------------------------------------------------------------

INK = (23, 23, 23)
MUTED = (110, 110, 110)
RULE = (225, 225, 225)
TINT = (243, 244, 246)


def _fmt_day(d: datetime | date) -> str:
    return d.strftime("%a %-d %b")


def _fmt_time(d: datetime) -> str:
    return d.strftime("%H:%M")


class Sheet(FPDF):
    def __init__(self, accent: tuple[int, int, int]):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.accent = accent
        self.set_margins(12, 12, 12)
        self.set_auto_page_break(auto=False)

    def text_line(self, s: str, size: float, style: str = "", colour=INK, h: float | None = None):
        self.set_font("Helvetica", style, size)
        self.set_text_color(*colour)
        self.cell(0, h or size * 0.45, s, new_x="LMARGIN", new_y="NEXT")

    def label(self, s: str):
        self.set_font("Helvetica", "B", 7.5)
        self.set_text_color(*MUTED)
        self.cell(0, 4, s.upper(), new_x="LMARGIN", new_y="NEXT")

    def rule(self, y: float | None = None):
        y = self.get_y() if y is None else y
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.line(self.l_margin, y, self.w - self.r_margin, y)


def _record_line(fixtures: list[Fixture]) -> str:
    r = team_record(fixtures)
    if r.played == 0:
        return "No matches played yet"
    return f"P{r.played}  W{r.won}  D{r.drawn}  L{r.lost}   GF {r.goals_for}  GA {r.goals_against}"


def _award_winners(last: FixtureDetail, code: str) -> str:
    names = [a.player.display_name for a in last.awards if a.award_type.code == code]
    return " & ".join(names) if names else "-"


def render(data: MatchdayData) -> bytes:
    ts = data.team_season
    team = ts.club_team
    pdf = Sheet(oklch_to_rgb(team.colour))
    pdf.set_title(f"ABGFC {team.name} - matchday sheet")
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin

    # --- header -----------------------------------------------------------------
    top = pdf.get_y()
    if CREST.exists():
        pdf.image(str(CREST), x=pdf.l_margin, y=top, h=16)
    pdf.set_xy(pdf.l_margin + 20, top)
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, f"ABGFC {team.name}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(pdf.l_margin + 20)
    bits = [
        "Matchday sheet",
        ts.age_group,
        ts.season.name,
        f"printed {_fmt_day(data.generated_at)}",
    ]
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, "  ·  ".join(b for b in bits if b), new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(top + 20)
    pdf.set_draw_color(*pdf.accent)
    pdf.set_line_width(0.8)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)

    # --- next fixture -------------------------------------------------------------
    f = data.fixture
    pdf.label("Next match" if f and f.status == FixtureStatus.SCHEDULED else "Fixture")
    if f is None:
        pdf.text_line("No fixture scheduled - add one in the app.", 11, colour=MUTED, h=7)
    else:
        venue = {"home": "Home", "away": "Away", "neutral": "Neutral"}[f.venue]
        pdf.text_line(
            f"{_fmt_day(f.kickoff_at)}, {_fmt_time(f.kickoff_at)}  v  {f.opposition.name}",
            15,
            "B",
            h=8,
        )
        where = f"{venue}{' · ' + f.venue_notes if f.venue_notes else ''}"
        meta = [where, f.competition.name, f"Match {f.match_number}" if f.match_number else None]
        pdf.text_line("  ·  ".join(m for m in meta if m), 9.5, colour=MUTED, h=5)
        if data.previous_meetings:
            parts = []
            for p in data.previous_meetings:
                res = {"W": "Won", "D": "Drew", "L": "Lost"}[outcome(p.our_score, p.their_score)]
                parts.append(f"{res} {p.our_score}-{p.their_score} on {_fmt_day(p.kickoff_at)}")
            pdf.text_line("Already played them: " + "; ".join(parts), 9, colour=INK, h=5)
        if f.notes:
            pdf.text_line(f.notes.replace("\n", " "), 9, "I", colour=MUTED, h=5)
    pdf.ln(3)

    # --- season so far | last match (two columns) -----------------------------------
    col_y = pdf.get_y()
    col_w = W / 2 - 3
    pdf.label("Season so far")
    league = [p for p in data.played if p.competition.type == CompetitionType.LEAGUE]
    pdf.text_line("All   " + _record_line(data.played), 9, h=5)
    pdf.text_line("League   " + _record_line(league), 9, h=5)
    f5 = "".join(x.result for x in form(data.played)) or "-"
    pdf.text_line(f"Last 5   {f5}", 9, h=5)
    left_end = pdf.get_y()

    pdf.set_xy(pdf.l_margin + col_w + 6, col_y)
    right_x = pdf.l_margin + col_w + 6
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(col_w, 4, "LAST MATCH", new_x="LEFT", new_y="NEXT")
    last = data.last_match
    if last is None:
        pdf.set_x(right_x)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(col_w, 5, "None yet", new_x="LEFT", new_y="NEXT")
    else:
        res = {"W": "Won", "D": "Drew", "L": "Lost"}[outcome(last.our_score, last.their_score)]
        headline = (
            f"{res} {last.our_score}-{last.their_score} v {last.opposition.name}, "
            f"{_fmt_day(last.kickoff_at)}"
        )
        lines = [(headline, "B", INK)]
        scorers = [
            g.scorer.display_name
            + (f" (assist {g.assisted_by.display_name})" if g.assisted_by else "")
            for g in last.goals
            if g.scorer and g.event_type == "goal"
        ]
        if scorers:
            lines.append(("Scorers: " + ", ".join(scorers), "", INK))
        lines.append((f"Coaches' POTM: {_award_winners(last, 'coaches_potm')}", "", INK))
        lines.append((f"Parents' POTM: {_award_winners(last, 'parents_potm')}", "", INK))
        for text, style, colour in lines:
            pdf.set_x(right_x)
            pdf.set_font("Helvetica", style, 9)
            pdf.set_text_color(*colour)
            pdf.multi_cell(col_w, 5, text, new_x="LEFT", new_y="NEXT")
    pdf.set_y(max(left_end, pdf.get_y()) + 3)
    pdf.rule()
    pdf.ln(3)

    # --- squad table ------------------------------------------------------------------
    rows = sorted(
        data.rows,
        key=lambda r: (r.squad_number is None, r.squad_number or 0, r.player.display_name),
    )
    played_n = len(data.played)
    min_apps = min((r.appearances for r in rows), default=0)
    pdf.label(f"Squad  ·  {len(rows)} players")
    award_codes = [a.award_type_code for a in rows[0].awards] if rows else []
    # columns: #, Player, Pos, Apps, Goals, Assists, awards..., Avail, Start, Sub
    fixed = {"#": 8, "Apps": 13, "Goals": 11, "Assists": 13, "Avail": 14}
    award_w = 26  # wide enough for "COACHES' POTM" with breathing room
    name_w = W - sum(fixed.values()) - award_w * len(award_codes) - 14  # 14 = Pos
    headers = (
        ["#", "Player", "Pos", "Apps", "Goals", "Assists"]
        + [
            {"coaches_potm": "Coaches' POTM", "parents_potm": "Parents' POTM"}.get(
                c, c.split("_", 1)[-1][:8]
            )
            for c in award_codes
        ]
        + ["Avail"]
    )
    widths = (
        [fixed["#"], name_w, 14, fixed["Apps"], fixed["Goals"], fixed["Assists"]]
        + [award_w] * len(award_codes)
        + [fixed["Avail"]]
    )
    aligns = ["C", "L", "C", "C", "C", "C"] + ["C"] * len(award_codes) + ["C"]

    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*MUTED)
    for h, w, a in zip(headers, widths, aligns, strict=True):
        pdf.cell(w, 5.5, h.upper(), align=a)
    pdf.ln(5.5)
    pdf.rule()

    # Fill the page sensibly: roomier rows for a small squad, tighter for a big one.
    row_h = 7.5 if len(rows) <= 12 else 6.2 if len(rows) <= 15 else 5.4
    pdf.set_font("Helvetica", "", 9)
    positions = _positions(data)
    for r in rows:
        y = pdf.get_y()
        short = played_n > 0 and r.appearances == min_apps and r.appearances < played_n
        if short:  # fewest games so far - the fairness nudge
            pdf.set_fill_color(*TINT)
            pdf.rect(pdf.l_margin, y, W, row_h, style="F")
        pdf.set_text_color(*INK)
        cells = (
            [
                str(r.squad_number) if r.squad_number is not None else "",
                r.player.display_name,
                positions.get(r.player.id, ""),
                f"{r.appearances}/{played_n}" if played_n else "0",
                str(r.goals),
                str(r.assists),
            ]
            + [str(a.count) for a in r.awards]
            + [""]
        )
        for i, (c, w, a) in enumerate(zip(cells, widths, aligns, strict=True)):
            style = "B" if i == 1 else ""
            pdf.set_font("Helvetica", style, 9)
            pdf.cell(w, row_h, c, align=a)
        # one tick box: available this week
        x = pdf.l_margin + sum(widths[:-1])
        pdf.set_draw_color(150, 150, 150)
        pdf.set_line_width(0.25)
        pdf.rect(x + fixed["Avail"] / 2 - 1.8, y + row_h / 2 - 1.8, 3.6, 3.6)
        pdf.ln(row_h)
        pdf.rule()
    if played_n and any(r.appearances == min_apps and r.appearances < played_n for r in rows):
        pdf.set_font("Helvetica", "I", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 5, "Shaded = fewest appearances so far", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # --- plan box fills what's left ------------------------------------------------------
    pdf.label("Plan / team talk")
    box_top = pdf.get_y()
    box_bottom = pdf.h - pdf.b_margin
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.2)
    yy = box_top + 7
    while yy < box_bottom - 2:
        pdf.line(pdf.l_margin, yy, pdf.w - pdf.r_margin, yy)
        yy += 7

    return bytes(pdf.output())


def _positions(data: MatchdayData) -> dict[int, str]:
    return {
        m.player_id: (m.primary_position.code if m.primary_position else "")
        for m in data.team_season.squad_members
    }


def matchday_sheet(
    db: Session, access: Access, team_season_id: int, fixture_id: int | None
) -> tuple[bytes, str]:
    """Returns (pdf bytes, suggested filename)."""
    data = gather(db, access, team_season_id, fixture_id)
    slug = data.team_season.club_team.slug
    when = (
        data.fixture.kickoff_at.strftime("%Y-%m-%d")
        if data.fixture
        else data.generated_at.strftime("%Y-%m-%d")
    )
    return render(data), f"{slug}-matchday-{when}.pdf"
