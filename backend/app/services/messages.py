"""The parents' message, in the club's house style. Pure functions over plain values so
the exact text is testable and a future scheduled reminder can reuse it.

    REDS are home against Haslemere Town Panthers
    This is an 11am kick off at Aldershot Park
    Please arrive at 10.30
    Adam & Dan coaching
    Squad
    Jackson
    ...

Lines with no data are omitted rather than printed blank; the only blank line is the one
before the coach's notes. No emoji.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.enums import Venue

# Fixtures store kick-off as naive UK wall-clock time (seeds, PDF and spreadsheet all
# read it that way). Arrival arithmetic goes through the real zone so that a kick-off
# just after midnight or on a clock-change morning still comes out right.
UK = ZoneInfo("Europe/London")


def arrival_time(kickoff: datetime, lead_minutes: int) -> datetime:
    """Kick-off minus the lead time, as naive UK wall-clock like `kickoff`."""
    aware = kickoff.replace(tzinfo=UK)
    # `fold` normalisation: an aware subtraction across a DST change is wall-clock-correct
    # once converted back through UTC.
    arrival = (aware.astimezone(ZoneInfo("UTC")) - timedelta(minutes=lead_minutes)).astimezone(UK)
    return arrival.replace(tzinfo=None)


def format_kickoff(dt: datetime) -> str:
    """'11am', '10.30am', '2pm' - no leading zero, minutes only when non-zero."""
    hour = dt.hour % 12 or 12
    suffix = "am" if dt.hour < 12 else "pm"
    return f"{hour}.{dt.minute:02d}{suffix}" if dt.minute else f"{hour}{suffix}"


def format_arrival(dt: datetime) -> str:
    """'10.30' or '10' - the way the example writes it, no am/pm."""
    hour = dt.hour % 12 or 12
    return f"{hour}.{dt.minute:02d}" if dt.minute else str(hour)


def kickoff_article(dt: datetime) -> str:
    """'an 11am kick off', 'an 8.15am kick off', but 'a 10.30am kick off'."""
    return "an" if dt.hour % 12 in (8, 11) else "a"


def format_date_line(dt: datetime) -> str:
    return f"{dt:%A} {dt.day} {dt:%B}"  # "Saturday 19 September"


@dataclass(frozen=True)
class SquadLine:
    name: str
    sub: bool = False


@dataclass(frozen=True)
class MessageInput:
    team_name: str
    venue: Venue
    opposition: str
    kickoff: datetime
    ground: str | None
    arrival: datetime
    coaching: str | None
    squad: list[SquadLine]
    notes: str | None


def parents_message(m: MessageInput, *, mark_subs: bool = False, date_line: bool = False) -> str:
    lines: list[str] = []
    if date_line:
        lines.append(format_date_line(m.kickoff))

    where = {
        Venue.HOME: "are home against",
        Venue.AWAY: "are away against",
        Venue.NEUTRAL: "are playing",
    }[Venue(m.venue)]
    lines.append(f"{m.team_name.upper()} {where} {m.opposition}")

    kick = f"This is {kickoff_article(m.kickoff)} {format_kickoff(m.kickoff)} kick off"
    if m.ground and m.ground.strip():
        kick += f" at {m.ground.strip()}"
    lines.append(kick)

    lines.append(f"Please arrive at {format_arrival(m.arrival)}")

    if m.coaching and m.coaching.strip():
        lines.append(f"{m.coaching.strip()} coaching")

    lines.append("Squad")
    for p in m.squad:
        lines.append(f"{p.name} (sub)" if mark_subs and p.sub else p.name)

    if m.notes and m.notes.strip():
        lines.append("")
        lines.append(m.notes.strip())

    return "\n".join(lines)
