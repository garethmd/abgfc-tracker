"""Reference data and a demo season with hand-checked totals.

Used by `scripts/seed.py` for local development and by the stats tests, so the numbers
the tests assert against are the numbers you see in the dev UI.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Appearance,
    Award,
    AwardScope,
    AwardType,
    Competition,
    CompetitionType,
    EventType,
    Fixture,
    FixtureStatus,
    MatchEvent,
    Player,
    Position,
    PositionCategory,
    Season,
    SquadMember,
    Team,
    User,
    UserRole,
    Venue,
)
from app.repositories.lookups import AwardTypeRepository, CompetitionRepository, PositionRepository

SQUAD = [
    "Alexander",
    "Archie",
    "Ayla",
    "Jack",
    "Kayson",
    "Max",
    "Noah",
    "Reece",
    "Stanley",
    "Teddy",
    "William",
]

POSITIONS = [
    ("GK", "Goalkeeper", PositionCategory.GK),
    ("DEF", "Defender", PositionCategory.DEF),
    ("MID", "Midfielder", PositionCategory.MID),
    ("FWD", "Forward", PositionCategory.FWD),
]

COMPETITIONS = [
    ("League", CompetitionType.LEAGUE),
    ("Cup", CompetitionType.CUP),
    ("Friendly", CompetitionType.FRIENDLY),
    ("Tournament", CompetitionType.TOURNAMENT),
]

AWARD_TYPES = [
    ("coaches_potm", "Coaches' Player of the Match"),
    ("parents_potm", "Parents' Player of the Match"),
]


def seed_reference_data(db: Session) -> None:
    """Idempotent: positions, competitions, award types."""
    positions = PositionRepository(db)
    existing = {p.code for p in positions.list_all()}
    for i, (code, name, category) in enumerate(POSITIONS):
        if code not in existing:
            db.add(Position(code=code, name=name, category=category, sort_order=i))

    competitions = CompetitionRepository(db)
    for name, ctype in COMPETITIONS:
        if competitions.get_by_name(name) is None:
            db.add(Competition(name=name, type=ctype))

    award_types = AwardTypeRepository(db)
    existing_codes = {a.code for a in award_types.list_all()}
    for i, (code, name) in enumerate(AWARD_TYPES):
        if code not in existing_codes:
            db.add(AwardType(code=code, name=name, scope=AwardScope.MATCH, sort_order=i))
    db.flush()


def seed_user(db: Session, username: str, password: str) -> User:
    from sqlalchemy import select

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(username=username, password_hash=hash_password(password), role=UserRole.ADMIN)
        db.add(user)
    else:
        user.password_hash = hash_password(password)
    db.flush()
    return user


def seed_real_season(db: Session) -> Season:
    """The actual 2026/27 season, transcribed from the coaches' Google Sheet
    (tabs: Fixtures, Match Stats, Appearances, Squad). Extend this as results come in
    until the app replaces the sheet entirely.

    The sheet records assists per player per match, not per goal; where a match has
    several goals the assist is attached to the first one.
    """
    seed_reference_data(db)
    comps = {c.name: c for c in CompetitionRepository(db).list_all()}
    award_types = {a.code: a for a in AwardTypeRepository(db).list_all()}

    season = Season(
        name="2026/27", start_date=date(2026, 9, 1), end_date=date(2027, 5, 31), is_current=True
    )
    db.add(season)
    db.flush()

    players: dict[str, Player] = {}
    for name in SQUAD:
        p = Player(first_name=name, display_name=name, joined_date=date(2026, 9, 1))
        db.add(p)
        db.flush()
        db.add(SquadMember(season_id=season.id, player_id=p.id))
        players[name] = p

    manor_colts = Team(name="Manor Colts")
    db.add(manor_colts)
    db.flush()

    # Match 1 — Sat 12 Sep 2026, League, Manor Colts, 2-2 (D), Aldershot Park
    m1 = Fixture(
        season_id=season.id,
        competition_id=comps["League"].id,
        opposition_team_id=manor_colts.id,
        match_number=1,
        kickoff_at=datetime(2026, 9, 12, 10, 0),
        venue=Venue.HOME,
        venue_notes="Aldershot Park",
        status=FixtureStatus.PLAYED,
        our_score=2,
        their_score=2,
    )
    db.add(m1)
    db.flush()
    for name in SQUAD:
        if name != "Kayson":
            db.add(Appearance(fixture_id=m1.id, player_id=players[name].id, started=True))
    goal1 = MatchEvent(
        fixture_id=m1.id, player_id=players["William"].id, event_type=EventType.GOAL, sequence=1
    )
    db.add(goal1)
    db.flush()
    db.add(
        MatchEvent(
            fixture_id=m1.id,
            player_id=players["Noah"].id,
            event_type=EventType.ASSIST,
            sequence=2,
            related_event_id=goal1.id,
        )
    )
    db.add(
        MatchEvent(
            fixture_id=m1.id, player_id=players["William"].id, event_type=EventType.GOAL, sequence=3
        )
    )
    db.add(
        Award(
            award_type_id=award_types["coaches_potm"].id,
            season_id=season.id,
            player_id=players["Noah"].id,
            fixture_id=m1.id,
        )
    )
    db.add(
        Award(
            award_type_id=award_types["parents_potm"].id,
            season_id=season.id,
            player_id=players["Ayla"].id,
            fixture_id=m1.id,
        )
    )

    # Remaining fixtures from the league site. Times of 08:00/00:00 are the site's
    # placeholders, kept as-is until real kick-offs are confirmed.
    for name, ctype in [
        ("Conference League", CompetitionType.LEAGUE),
        ("Zidane League", CompetitionType.LEAGUE),
    ]:
        if name not in comps:
            comps[name] = Competition(name=name, type=ctype)
            db.add(comps[name])
    db.flush()

    teams: dict[str, Team] = {"Manor Colts": manor_colts}
    for name, short in [
        ("Alton Youth Wildfire", "Alton Wildfire"),
        ("Haslemere Town Harriers", "Haslemere"),
        ("Grayshott Youth Bears", "Grayshott"),
        ("Crookham Rovers Rogues", "Crookham"),
        ("Aldershot B&G Blacks", "ABGFC Blacks"),
        ("Hook Pumas", "Hook"),
        ("Curley Park Rangers Cobras", "Curley Park Cobras"),
        ("Hawley Youth Falcons", "Hawley"),
        ("Camberley Town Razors", "Camberley"),
        ("Mytchett Athletic Ospreys", "Mytchett"),
        ("Churt Junior Heat", "Churt"),
        ("Hart Youth Ospreys", "Hart"),
        ("Curley Park Rangers Spitfires", "Curley Park Spitfires"),
    ]:
        teams[name] = Team(name=name, short_name=short)
        db.add(teams[name])
    db.flush()

    CONF, ZID = comps["Conference League"], comps["Zidane League"]
    H, A = Venue.HOME, Venue.AWAY
    upcoming = [
        # (match, date, time, opposition, venue, ground, competition)
        (2, (9, 19), (8, 0), "Alton Youth Wildfire", H, "Aldershot Park", CONF),
        (3, (9, 26), (0, 0), "Haslemere Town Harriers", A, "Camelsdale Recreation Ground #1", ZID),
        (4, (10, 3), (8, 0), "Grayshott Youth Bears", A, "Grayshott Youth ground", CONF),
        (5, (10, 10), (8, 0), "Crookham Rovers Rogues", A, "Cody Sports and Social Club 4", ZID),
        (6, (10, 17), (8, 0), "Aldershot B&G Blacks", A, "Aldershot Park", CONF),
        (7, (10, 24), (8, 0), "Hook Pumas", H, "Aldershot Park", ZID),
        (8, (11, 7), (8, 0), "Curley Park Rangers Cobras", H, "Aldershot Park", CONF),
        (9, (11, 14), (8, 0), "Hawley Youth Falcons", H, "Aldershot Park", ZID),
        (10, (11, 21), (8, 0), "Camberley Town Razors", H, "Aldershot Park", ZID),
        (11, (11, 28), (10, 0), "Mytchett Athletic Ospreys", A, "Holly Lodge Primary Academy", ZID),
        (12, (12, 5), (8, 0), "Churt Junior Heat", H, "Aldershot Park", ZID),
        (13, (12, 12), (8, 0), "Hart Youth Ospreys", A, "Zebon Copse Centre Pitch 1", ZID),
        (14, (12, 19), (8, 0), "Curley Park Rangers Spitfires", A, "Connaught Pavilion", ZID),
    ]
    for num, (month, day), (hh, mm), opp, venue, ground, comp in upcoming:
        db.add(
            Fixture(
                season_id=season.id,
                competition_id=comp.id,
                opposition_team_id=teams[opp].id,
                match_number=num,
                kickoff_at=datetime(2026, month, day, hh, mm),
                venue=venue,
                venue_notes=ground,
                status=FixtureStatus.SCHEDULED,
            )
        )
    db.flush()
    return season


@dataclass
class DemoSeason:
    season: Season
    players: dict[str, Player]
    competitions: dict[str, Competition]
    award_types: dict[str, AwardType]
    teams: dict[str, Team]
    fixtures: list[Fixture] = field(default_factory=list)


def seed_demo_season(db: Session) -> DemoSeason:
    """Six played fixtures, one scheduled, one postponed. Expected totals:

    Overall  P6 W2 D1 L3  GF12 GA12 GD0  win% 33.3   form (last 5) D L W L L
    League   P4 W2 D1 L1  GF11 GA6  GD5  win% 50.0

    Player    Apps  G  A  OG  Coaches  Parents   (league: apps/G/A)
    Archie      6   5  3   0     2        0         4/5/3
    Max         6   2  3   0     1        2         4/1/3
    Noah        6   2  2   0     1        2         4/2/1
    Jack        5   0  1   0     1        1         3/0/1
    Ayla        5   1  0   0     0        1         3/1/0
    Kayson      5   1  0   0     0        1         4/1/0
    Stanley     5   0  0   1     1        0         3/0/0
    Alexander   5   0  0   0     0        0         3/0/0
    William     5   0  0   0     0        0         3/0/0
    Reece       4   0  0   0     0        0         2/0/0
    Teddy       2   0  0   0     0        0         0/0/0

    Highlights: top scorer Archie (5); most assists Archie & Max (3);
    coaches' POTM Archie (2); parents' POTM Max & Noah (2).
    """
    seed_reference_data(db)
    comps = {c.name: c for c in CompetitionRepository(db).list_all()}
    award_types = {a.code: a for a in AwardTypeRepository(db).list_all()}
    fwd = next(p for p in PositionRepository(db).list_all() if p.code == "FWD")

    season = Season(
        name="2026/27", start_date=date(2026, 9, 1), end_date=date(2027, 5, 31), is_current=True
    )
    db.add(season)
    db.flush()

    players: dict[str, Player] = {}
    for i, name in enumerate(SQUAD, start=1):
        p = Player(first_name=name, display_name=name, joined_date=date(2026, 9, 1))
        db.add(p)
        db.flush()
        db.add(
            SquadMember(
                season_id=season.id,
                player_id=p.id,
                squad_number=i,
                primary_position_id=fwd.id if name == "Archie" else None,
            )
        )
        players[name] = p

    teams = {}
    for name in [
        "Farnborough Town Youth",
        "Fleet Spurs",
        "Camberley Town",
        "Hook Juniors",
        "Yateley United",
    ]:
        t = Team(name=name)
        db.add(t)
        teams[name] = t
    db.flush()

    demo = DemoSeason(season, players, comps, award_types, teams)
    P = players
    absent = lambda *names: [n for n in SQUAD if n not in names]  # noqa: E731

    def fixture(
        num,
        comp,
        opp,
        day,
        our,
        their,
        venue=Venue.HOME,
        status=FixtureStatus.PLAYED,
        played=None,
        goals=(),
        coaches=(),
        parents=(),
    ):
        f = Fixture(
            season_id=season.id,
            competition_id=comps[comp].id,
            opposition_team_id=teams[opp].id,
            match_number=num,
            kickoff_at=datetime(2026, day[0], day[1], 10, 0),
            venue=venue,
            status=status,
            our_score=our,
            their_score=their,
        )
        db.add(f)
        db.flush()
        for name in played or []:
            db.add(Appearance(fixture_id=f.id, player_id=P[name].id, started=True))
        seq = 0
        for scorer, assist in goals:
            seq += 1
            if scorer is None:  # opposition own goal
                db.add(MatchEvent(fixture_id=f.id, event_type=EventType.OPP_OWN_GOAL, sequence=seq))
                continue
            etype = EventType.OWN_GOAL if scorer.startswith("OG:") else EventType.GOAL
            g = MatchEvent(
                fixture_id=f.id,
                player_id=P[scorer.removeprefix("OG:")].id,
                event_type=etype,
                sequence=seq,
            )
            db.add(g)
            db.flush()
            if assist:
                seq += 1
                db.add(
                    MatchEvent(
                        fixture_id=f.id,
                        player_id=P[assist].id,
                        event_type=EventType.ASSIST,
                        sequence=seq,
                        related_event_id=g.id,
                    )
                )
        for name in coaches:
            db.add(
                Award(
                    award_type_id=award_types["coaches_potm"].id,
                    season_id=season.id,
                    player_id=P[name].id,
                    fixture_id=f.id,
                )
            )
        for name in parents:
            db.add(
                Award(
                    award_type_id=award_types["parents_potm"].id,
                    season_id=season.id,
                    player_id=P[name].id,
                    fixture_id=f.id,
                )
            )
        db.flush()
        demo.fixtures.append(f)
        return f

    fixture(
        1,
        "League",
        "Farnborough Town Youth",
        (9, 5),
        3,
        1,
        played=absent("Teddy", "William"),
        goals=[("Archie", "Max"), ("Archie", "Jack"), ("Noah", None)],
        coaches=["Archie"],
        parents=["Noah"],
    )
    fixture(
        2,
        "League",
        "Fleet Spurs",
        (9, 12),
        2,
        2,
        venue=Venue.AWAY,
        played=absent("Ayla", "Reece", "Stanley", "Teddy"),
        goals=[("Max", "Archie"), (None, None)],
        coaches=["Max"],
        parents=["Max"],
    )
    fixture(
        3,
        "Cup",
        "Camberley Town",
        (9, 19),
        0,
        4,
        played=absent("Kayson"),
        coaches=["Jack"],
        parents=["Jack"],
    )
    fixture(
        4,
        "League",
        "Hook Juniors",
        (9, 26),
        5,
        0,
        venue=Venue.AWAY,
        played=absent("Alexander", "Teddy"),
        goals=[
            ("Archie", "Max"),
            ("Archie", "Max"),
            ("Archie", None),
            ("Ayla", "Noah"),
            ("Kayson", "Archie"),
        ],
        coaches=["Archie"],
        parents=["Ayla", "Kayson"],
    )
    fixture(
        5,
        "Friendly",
        "Yateley United",
        (10, 3),
        1,
        2,
        played=SQUAD,
        goals=[("Max", "Noah"), ("OG:Stanley", None)],
        coaches=["Stanley"],
        parents=["Max"],
    )
    fixture(
        6,
        "League",
        "Farnborough Town Youth",
        (10, 10),
        1,
        3,
        venue=Venue.AWAY,
        played=absent("Jack", "Reece", "Teddy"),
        goals=[("Noah", "Archie")],
        coaches=["Noah"],
        parents=["Noah"],
    )
    fixture(7, "League", "Fleet Spurs", (10, 17), None, None, status=FixtureStatus.SCHEDULED)
    fixture(8, "Cup", "Hook Juniors", (10, 24), None, None, status=FixtureStatus.POSTPONED)
    db.flush()
    return demo
