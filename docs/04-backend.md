# 4. Backend code walkthrough

`backend/` is a `uv` project (Python 3.13). Entry point `app/main.py` → `create_app()`.

```
backend/
├── app/
│   ├── main.py             create_app(): CORS, AppError handler, routers, /api/health
│   ├── config.py           Settings (pydantic-settings), env prefix ABGFC_, production guard
│   ├── db/                 base.py (Base, naming convention, TimestampMixin), session.py
│   ├── models/             ORM, one module per aggregate; enums.py; __init__ imports all
│   ├── schemas/            Pydantic request/response models
│   ├── repositories/       every query; BaseRepository[Model] + one per aggregate
│   ├── services/           business rules; see below
│   ├── api/deps.py         DB, CurrentUser, Access dependencies
│   ├── api/routers/        auth, club, seasons, players, lookups, fixtures (+notes, selection), live, users, reports
│   └── assets/crest.png    used by the PDF
├── alembic/                env.py + versions/
├── scripts/                seed.py (migrate + seed), export_openapi.py
├── tests/                  pytest (in-memory SQLite per test)
└── pyproject.toml          deps, ruff (line length 100), pytest config
```

## Configuration (`app/config.py`)

`Settings` reads `ABGFC_*` environment variables and the repo-root `.env`.

| Setting | Default | Notes |
|---|---|---|
| `env` | `development` | `production` hides docs, forces Secure cookies, refuses dev secrets |
| `database_url` | `sqlite:///<repo>/data/abgfc.db` | production: `sqlite:////data/abgfc.db` |
| `media_dir` | `<repo>/data/media` | production: `/data/media` |
| `secret_key` | dev constant | ≥16 chars; signs session cookies; **refused in production** |
| `session_max_age_seconds` | 30 days | |
| `cookie_secure` | `None` | None = follow env (Secure in production) |
| `cors_origins` | `["http://localhost:3000"]` | irrelevant in production (same origin), set anyway |
| `coach_username` / `coach_password` | `coach` / dev constant | the seeded club admin; password **refused in production** |

`get_settings()` is `lru_cache`d; tests monkeypatch attributes on the cached instance.

## Database (`app/db/`)

- `make_engine(url)` — SQLite gets `check_same_thread=False` and a `connect` listener that
  runs `PRAGMA foreign_keys=ON`; an in-memory URL gets `StaticPool` so tests share one
  connection.
- `get_db()` — FastAPI dependency yielding a `Session` (`expire_on_commit=False`, so
  objects stay usable after a service commits).
- `Base.metadata` carries the naming convention; `TimestampMixin` adds the two
  timestamps with `func.now()` defaults.

## Models (`app/models/`)

| Module | Classes |
|---|---|
| `enums.py` | `CompetitionType`, `Venue`, `FixtureStatus`, `EventType`, `AwardScope`, `PositionCategory`, `MediaKind`, `UserRole` (with `.level`), `RoleScope`; `check_in()` builds the CHECK SQL |
| `club.py` | `Cohort` (`age_group_for`), `ClubTeam`, `TeamSeason` |
| `season.py` | `Season` |
| `player.py` | `Player` (`photo_key` property via a viewonly `profile_photo_link` relationship), `SquadMember` |
| `lookup.py` | `Position`, `Competition`, `AwardType` |
| `team.py` | `Team` (opposition) |
| `fixture.py` | `Fixture` (`effective_duration`), relationships to appearances/events/awards/match_notes with `delete-orphan` cascades |
| `match.py` | `Appearance`, `PlayerStint`, `MatchEvent` (self-referential `related_event`) |
| `award.py` | `Award` |
| `note.py` | `MatchNote` |
| `selection.py` | `FixtureSelection`, `SelectionPlayer` (pre-match availability) |
| `media.py` | `Media`, `MediaLink` |
| `user.py` | `User`, `UserRole` (exported as `UserRoleAssignment` to avoid clashing with the enum) |

Relationship targets are strings resolved through `models/__init__.py`, which imports
every module — import `app.models` (not a submodule) anywhere the mapper must be complete.

## Schemas (`app/schemas/`)

Two bases in `common.py`: `InputModel` (`extra="forbid"`, whitespace-stripped strings)
for requests and `ORMModel` (`from_attributes=True`) for responses. Naming: `XCreate`,
`XUpdate` (all-optional, `exclude_unset` in services), `XRead`, plus purpose-built shapes
(`FixtureDetail`, `ResultSubmit`, `MeRead`, `Leaderboard`, `CohortOverview`,
`MembershipRead`). Validators live on the input models (`GoalInput` checks scorer/assist
combinations, `ResultSubmit` rejects duplicate players, `TeamSeasonStart` requires exactly
one of season id/name).

## Repositories (`app/repositories/`)

`BaseRepository[ModelT]` gives `get`, `get_or_404` (raises `NotFoundError` with the
repo's `label`), `list_all`, `add` (flush), `delete`. Subclasses add scoped queries:

- `FixtureRepository.list_all(team_season_id, team_ids, competition_id, status)`,
  `get_detail` (eager-loads everything the detail page needs), `list_played`,
  `played_fixture_ids(team_season_id, competition_type)`, `next_match_number`.
- `StatsRepository` — bulk loads of appearances/events/awards for a set of fixture ids.
- `SquadRepository.list_for_team_season`, `get_member`, `memberships_for_player`.
- `ClubTeamRepository.list_all(ids=visible)`, `TeamSeasonRepository.get_current`,
  `set_current` (clears siblings), `list_for_team`, `list_for_season`.
- `AwardTypeRepository.list_all(active_only, club_team_id)` — club-wide plus that team's.
- `UserRepository` eager-loads roles.

## Services (`app/services/`)

Every service takes `(db, access)`; the access object is how scoping happens.

| Module | Responsibility |
|---|---|
| `access.py` | `Access.for_user(db, user)` resolves `user_roles` into club/cohort/team roles and the set of visible team ids; `require_team`, `require_team_season`, `require_cohort`, `require_player`, `require_club` raise `ForbiddenError`. See [Security](08-security.md). |
| `auth.py` | `authenticate` (argon2 verify, generic error), `get_user`, `change_password`. |
| `users.py` | Coach accounts: list/create/update/set_roles/set_password, each restricted to scopes the caller administers. |
| `club.py` | `CohortService`, `ClubTeamService` (slug generation with `-2` suffixing), `TeamSeasonService` (`start` = roll-over: create season if needed, derive age group, copy squad, make current). |
| `seasons.py` | Club-wide seasons; `get_or_create("2027/28")` derives Sept–May dates. |
| `players.py` | Players (cohort-scoped uniqueness of display name), squad upsert/remove, `move` between teams, `memberships`. |
| `lookups.py` | Competitions, opposition teams (delete refused while fixtures reference them), award types (per-team codes). |
| `fixtures.py` | CRUD with match-number uniqueness; `submit_result` — the transactional post-match write; `_to_detail` folds assists into goals and attaches `score_warnings`. |
| `live.py` | `LiveMatchService`: the same result written one tap at a time (start/squad/goals/against/finish/abandon) while `status=live`. |
| `notes.py` | Match notes CRUD. |
| `selections.py` | `SelectionService`: pre-match availability (get/put/delete, replaced whole) and `message()` for the parents' text. Editable while `scheduled`/`postponed`; 409 once played. |
| `messages.py` | Pure functions: `parents_message()` renders the house-style text from plain values; `arrival_time()` does kick-off minus lead in Europe/London; `format_kickoff` ("11am", "10.30am"), `kickoff_article` ("a"/"an"). No DB, so the exact text is unit-tested and a scheduled reminder can reuse it. |
| `media.py` | `PlayerPhotoService`: re-encode (EXIF stripped, orientation applied), two sizes, private storage, replace/remove. |
| `stats.py` | Pure functions + `StatsService` (summary, leaderboard, player row, cohort overview). See [Stats](07-stats.md). |
| `reports.py` | Matchday PDF (fpdf2). |
| `exports.py` | Season spreadsheet (openpyxl) in the original sheet's layout. |
| `bootstrap.py` | Seeds; the demo season is the stats oracle. |

### `submit_result` in detail

```python
fixture = self.get(id, UserRole.COACH)           # loads detail, checks coach access
# validate: every scorer/assister/award winner is in `appearances`; award types are
# match-scoped and visible to this team
fixture.appearances.clear(); fixture.events.clear(); fixture.awards.clear(); flush
fixture.our_score, their_score, status = ..., ..., PLAYED
for a in data.appearances: fixture.appearances.append(Appearance(**a))
for g in data.goals:                               # sequence numbers assigned here
    goal = MatchEvent(type=g.event_type, player_id=g.scorer_id, ...)
    if g.assisted_by_id: MatchEvent(type=ASSIST, related_event=goal, ...)
for aw in data.awards (deduped): fixture.awards.append(Award(...))
commit
```

It replaces the whole result atomically and is idempotent — resubmitting the same
payload yields the same rows — which is what makes it safe to queue offline later.

## API layer (`app/api/`)

`deps.py` defines the dependency aliases used in every route signature:

```python
DB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]   # cookie → user (401 otherwise)
Access = Annotated[AccessModel, Depends(get_access)]       # user → resolved roles
```

Routers are one file per resource and stay thin. `main.py` mounts them under `/api/v1`,
registers the `AppError` → JSON handler, adds CORS (for local dev) and `/api/health`.
In production `docs_url`/`openapi_url` are `None`.

## Adding a feature: the checklist

1. Model (+ `models/__init__.py` export) → `make migration m="…"` → review the file →
   `make migrate` → `uv run alembic check`.
2. Schemas: `XCreate`/`XUpdate`/`XRead`.
3. Repository queries if new ones are needed (with scope filters).
4. Service method(s): call `access.require_*` first, then do the work, then `commit`.
5. Router: one line per route, `response_model` set.
6. Tests: happy path, validation, **and a scoping test** (viewer can't write, other team
   can't read).
7. `make api-client` and commit the regenerated `frontend/lib/api/*` (CI fails otherwise).
8. Frontend hook usage: `$api.useQuery("get", "/api/v1/…")` / `$api.useMutation`.

## Testing (`tests/`)

- `conftest.py`: `db` (fresh in-memory engine, `create_all`), `demo` (the fictional
  season), `client` (app with `get_db` overridden), `auth_client` (logged in as the seeded
  club admin), helpers `make_user(db, name, (role, scope, id)...)` and `login_as`.
- `test_stats.py` — the arithmetic against the oracle; `test_api.py` — CRUD and the entry
  flow; `test_access.py` — scoping across roles; `test_config.py` — production guard;
  `test_reports.py`, `test_exports.py` (recalculates in LibreOffice when installed),
  `test_photos.py`, `test_notes.py`, `test_live.py` (live entry end to end + scoping),
  `test_selections.py` (availability, the message's exact text and variants, arrival arithmetic
  across midnight/DST, scoping, the PDF with a selection).
- Run `make test`; `uv run pytest -q tests/test_x.py -k name` for one.
